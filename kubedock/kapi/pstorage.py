import boto
import boto.ec2
import json
import time
from contextlib import contextmanager
import os
from collections import defaultdict

from ConfigParser import ConfigParser
from fabric.api import run, settings, env, hide
from StringIO import StringIO
from fabric.exceptions import CommandTimeout, NetworkError
from flask import current_app

from ..core import db, ExclusiveLock, ConnectionPool
from ..exceptions import APIError
from ..nodes.models import Node, NodeFlagNames
from ..pods.models import PersistentDisk, PersistentDiskStatuses, Pod
from ..users.models import User
from ..usage.models import PersistentDiskState
from ..utils import send_event_to_role, atomic
from ..settings import (
    SSH_KEY_FILENAME, CEPH, AWS, CEPH_POOL_NAME, PD_NS_SEPARATOR,
    NODE_LOCAL_STORAGE_PREFIX, CEPH_CLIENT_USER, CEPH_KEYRING_PATH)
from ..kd_celery import celery, exclusive_task
from . import node_utils
from .pd_utils import compose_pdname
from ..billing.models import Kube


NODE_COMMAND_TIMEOUT = 60

DEFAULT_FILESYSTEM = 'xfs'


UNABLE_CREATE_PD_MSG = 'Unable to create persistent disk "{}"'


def check_namespace_exists(node_ip=None, namespace=None):
    """Checks existence of requests for namespace providing by storage backend.
    For CEPH namespace is equal to pool name, so it will check pool existence,
    and create it if the one is missed.
    """
    cls = get_storage_class()
    if cls:
        cls().check_namespace_exists(node_ip=node_ip, namespace=namespace)


class NodeCommandError(Exception):
    """Exceptions during execution commands on nodes."""
    pass


class NodeCommandWrongExitCode(NodeCommandError):
    """Special exception to catch specified exit codes for remote commands."""

    def __init__(self, code):
        super(NodeCommandWrongExitCode, self).__init__()
        self.code = code


class NoNodesError(Exception):
    """Exception raises when there is no nodes for current storage backend."""
    pass


class DriveIsLockedError(Exception):
    """Exception raises when drive is exclusively locked by some operation.
    Blocking operations: creation, making FS, deletion. We forbid
    simultaneous running more than one of that operations.
    """
    pass


def delete_drive_by_id(drive_id):
    """Marks drive in DB as deleted and asynchronously calls deletion from
    storage backend.
    """
    try:
        with drive_lock(drive_id=drive_id):
            pd = PersistentDisk.query.filter(
                PersistentDisk.id == drive_id
            ).first()
            if pd:
                PersistentStorage.end_stat(pd.name, pd.owner_id)
                new_pd = PersistentDisk.mark_todelete(drive_id)
                if new_pd:
                    update_pods_volumes(new_pd)
    except DriveIsLockedError as err:
        raise APIError(err.message)
    delete_persistent_drives_task.delay([drive_id], mark_only=False)


@atomic(nested=False)
def update_pods_volumes(pd):
    """Replaces volume info in configs of existing pods with new one pd.
    Will change volumes with the same owner and the same public volume name,
    as in the given pd.
    :param pd: object of PersistentDisk model
    """
    storage_cls = get_storage_class()
    for pod in Pod.query.filter(Pod.owner_id == pd.owner_id):
        if pod.is_deleted:
            continue
        try:
            config = pod.get_dbconfig()
        except (TypeError, ValueError):
            current_app.logger.exception('Invalid pod (%s) config: %s',
                                         pod.id, pod.config)
            continue
        vol = _get_pod_volume_by_pd_name(config, pd.name)
        current_app.logger.debug('Pod %s config: %s', pod.id, pod.config)
        current_app.logger.debug('Found volume: %s', vol)
        if not vol or not vol.get('name', None):
            continue
        volumes = config.get('volumes', [])
        changed = False
        for item in volumes:
            if item.get('name', '') != vol['name']:
                continue

            current_app.logger.debug('Updating volume: %s', item)
            storage_cls().enrich_volume_info(item, pd.size, pd.drive_name)
            changed = True
            break
        if changed:
            pod.set_dbconfig(config, save=False)


@celery.task()
@exclusive_task(60 * 60)
def delete_persistent_drives_task(pd_ids, mark_only=False):
    return delete_persistent_drives(pd_ids, mark_only=mark_only)


@contextmanager
def drive_lock(drivename=None, drive_id=None, ttl=None):
    """Context for locking drive to exclusively use by one operation.
    If lock for the drivename is already acquired, then raises
    DriveIsLockedError.
    Lock will be automatically released on exit from context.
    Lock will be valid for some time (TTL).
    """
    lock_name = drivename
    if not drivename and drive_id:
        pd = PersistentDisk.query.filter(
            PersistentDisk.id == drive_id
        ).first()
        if pd:
            lock_name = pd.drive_name
    if lock_name is None:
        raise APIError('Cant lock unknown drive')
    if ttl is None:
        # Calculate lock TTL as a sum of timeouts for remote operations
        # plus some additional time
        ttl = (NODE_COMMAND_TIMEOUT * 10 +  # FS creation
               NODE_COMMAND_TIMEOUT +       # FS status
               NODE_COMMAND_TIMEOUT * 2 +   # map & unmap
               10)  # some additional wait time
    lock = ExclusiveLock('PD.{}'.format(lock_name), ttl)
    if not lock.lock():
        raise DriveIsLockedError(
            'Persistent disk is exclusively locked by another operation. '
            'Wait some time and try again.'
        )
    try:
        yield lock
    finally:
        lock.release()


def delete_persistent_drives(pd_ids, mark_only=False):
    if not pd_ids:
        return
    pd_cls = get_storage_class()
    to_delete = []
    if pd_cls:
        for pd_id in pd_ids:
            try:
                rv = pd_cls().delete_by_id(pd_id)
            except DriveIsLockedError:
                # Skip deleting drives that is locked by another client
                continue
            if rv != 0:
                try:
                    if pd_cls().is_drive_exist(pd_id):
                        current_app.logger.warning(
                            u'Persistent Disk id:"{0}" is busy.'.format(pd_id)
                        )
                        continue
                    # If pd is not exist, then delete it from DB
                except NodeCommandError:
                    current_app.logger.warning(
                        u'Persistent Disk id:"{0}" is busy or '
                        u'does not exist.'.format(pd_id))
                    continue
            to_delete.append(pd_id)
    else:
        to_delete = pd_ids

    if not to_delete:
        return

    try:
        if mark_only:
            db.session.query(PersistentDisk).filter(
                PersistentDisk.id.in_(to_delete)
            ).update(
                {
                    PersistentDisk.state: PersistentDiskStatuses.DELETED,
                    PersistentDisk.node_id: None
                },
                synchronize_session=False
            )
        else:
            db.session.query(PersistentDisk).filter(
                PersistentDisk.id.in_(to_delete)
            ).delete(synchronize_session=False)
        db.session.commit()
    except:
        current_app.logger.exception(
            u'Failed to delete Persistent Disks from DB: "%s"',
            to_delete
        )


def remove_drives_marked_for_deletion():
    """Collects and deletes drives marked as deleted and deletes them."""
    ids = [item.id for item in PersistentDisk.get_todelete_query()]
    if ids:
        delete_persistent_drives(ids, mark_only=False)


class PersistentStorage(object):
    storage_name = ''

    VOLUME_EXTENSION_KEY = ''

    @classmethod
    def are_pod_volumes_compatible(cls, volumes, owner_id, pod_params):
        """Should check if volumes of one pod can be created."""
        return True

    @classmethod
    def is_volume_of_the_class(cls, vol):
        return cls.VOLUME_EXTENSION_KEY in vol

    def __init__(self):
        env.user = 'root'
        env.skip_bad_hosts = True
        env.key_filename = SSH_KEY_FILENAME
        self._cached_drives = None
        self._cached_node_ip = None

    def check_namespace_exists(self, node_ip=None, namespace=None):
        """Method ensures that configured namespace exists.
        If it not exists, then will create it.
        """
        return True

    def get_drives(self, user_id=None):
        """Returns cached drive list. At first call fills the cache by calling
        method _get_drives_from_db.
        """
        if self._cached_drives is None:
            self._cached_drives = self._get_drives_from_db(user_id=user_id)
        return self._cached_drives

    def _get_drives_from_db(self, user_id=None):
        query = PersistentDisk.get_all_query()
        if user_id is not None:
            query = query.filter(PersistentDisk.owner_id == user_id)
            users = {user_id: User.get(user_id)}
        else:
            users = {item.id: item for item in db.session.query(User)}
        query = query.order_by(PersistentDisk.name)
        res = [
            {
                'name': item.name,
                'drive_name': item.drive_name,
                'owner': users[item.owner_id].username,
                'owner_id': item.owner_id,
                'size': item.size,
                'id': item.id,
                'pod_id': item.pod_id,
                'pod_name': None if item.pod_id is None else item.pod.name,
                'in_use': item.pod_id is not None,
                'available': True,
                'node_id': None,
                'forbidDeletion': item.pod_id is not None,
            }
            for item in query
        ]
        res = self._add_pod_info_to_drive_list(res, user_id)
        return res

    def _add_pod_info_to_drive_list(self, drive_list, user_id=None):
        """Adds linked pod list to every drive in drive_list:
            drive['linkedPods'] = [{'podId': pod identifier, 'name': pod name}]
        May be extended in nested classes.
        :param drive_list: list of dicts, each dict is a drive information, as
        it filled in _get_drives_from_db method.
        :param user_id: optional user identifier - owner of drives in list and
            pods to be selected.
        :return: incoming drive_list where each element is extended with
            'linkedPods' field

        """
        drives_by_name = {
            (item['owner_id'], item['name']): item for item in drive_list
        }
        query = Pod.query
        if user_id:
            query = query.filter(Pod.owner_id == user_id)
        for pod in query:
            if pod.is_deleted:
                continue
            try:
                config = pod.get_dbconfig()
            except (TypeError, ValueError):
                current_app.logger.exception('Invalid pod (%s) config: %s',
                                             pod.id, pod.config)
                continue
            for item in config.get('volumes_public', []):
                name = item.get('persistentDisk', {}).get('pdName', '')
                key = (pod.owner_id, name)
                if key not in drives_by_name:
                    continue
                pod_list = drives_by_name[key].get('linkedPods', [])
                pod_list.append({'podId': pod.id, 'name': pod.name})
                drives_by_name[key]['linkedPods'] = pod_list

        for drive in drive_list:
            if 'linkedPods' not in drive:
                drive['linkedPods'] = []
        return drive_list

    def get_node_ip(self):
        if self._cached_node_ip is None:
            item = self._get_first_node()
            if item is None:
                raise NoNodesError(
                    'There is no nodes for "{}" storage'.format(
                        self.storage_name
                    )
                )
            self._cached_node_ip = item.ip
        return self._cached_node_ip

    def _get_first_node(self):
        return db.session.query(Node).first()

    def get(self, drive_id=None):
        """
        Returns list of all persistent storage data
        :return: list -> list of dicts
        """
        if drive_id is None:
            return self.get_drives()
        drives = [i for i in self.get_drives() if i['id'] == drive_id]
        if drives:
            return drives[0]

    def get_by_user(self, user, device_id=None):
        """
        Returns list of persistent drives of a certain user
        :param user: object -> user object got from SQLAlchemy
        :return: list -> list of dicts
        """
        if device_id is None:
            return self.get_drives(user_id=user.id)
        drives = [item for item in self.get_drives(user_id=user.id)
                  if item['id'] == device_id]
        if drives:
            return drives[0]

    def get_user_unmapped_drives(self, user):
        """
        Returns unmapped drives of a user
        :return: list -> list of dicts of unmapped drives of a user
        """
        return [d for d in self.get_drives(user.id) if not d['in_use']]

    def create(self, pd):
        """
        Tries to create a new persistent drive. Returns PersistentDisk
        structure serialized to json.
        If creating was failed, then return None.

        :param pd: kubedock.pods.models.PersistentDisk instance
        """
        try:
            with drive_lock(pd.drive_name):
                rv_code = self._create_drive(pd.drive_name, pd.size)
        except (NoNodesError, DriveIsLockedError) as e:
            current_app.logger.exception(UNABLE_CREATE_PD_MSG.format(pd.name))
            msg = '{}, reason: {}'.format(
                UNABLE_CREATE_PD_MSG.format(pd.drive_name), e.message)
            send_event_to_role('notify:error', {'message': msg}, 'Admin')
            raise APIError(UNABLE_CREATE_PD_MSG.format(pd.name))

        if rv_code != 0:
            return None
        self.start_stat(pd.size, pd.name, pd.owner.id)
        data = pd.to_dict()
        if self._cached_drives is not None:
            self._cached_drives.append(data)
        return data

    def makefs(self, pd, fs=DEFAULT_FILESYSTEM):
        """
        Creates a filesystem on the device

        :param pd: kubedock.pods.models.PersistentDisk instance
        :param fs: string -> fs type by default DEFAULT_FILESYSTEM
        """
        user_msg = UNABLE_CREATE_PD_MSG.format(pd.name)
        admin_msg = UNABLE_CREATE_PD_MSG.format(pd.drive_name)
        try:
            with drive_lock(pd.drive_name):
                return self._makefs(pd.drive_name, fs)
        except (DriveIsLockedError, NodeCommandError, NoNodesError) as e:
            current_app.logger.exception(admin_msg)
            notify_msg = "{}, reason: {}".format(admin_msg, e.message)
            send_event_to_role('notify:error', {'message': notify_msg}, 'Admin')
            raise APIError(user_msg)

    def _makefs(self, drive_name, fs):
        return None

    def delete_by_id(self, drive_id):
        """
        Deletes a user drive
        :param name: string -> drive id
        Raises DriveIsLockedError if drive is locked by another operation at
        the moment.
        """
        with drive_lock(drive_id=drive_id):
            pd = PersistentDisk.query.filter(
                PersistentDisk.id == drive_id
            ).first()
            if not pd:
                current_app.logger.warning(
                    'Unable to delete drive. '
                    'Unknown drive id: %s',
                    drive_id
                )
                return 1
            # self.end_stat(pd.name, pd.owner_id)
            rv = self._delete_pd(pd)
        if rv == 0 and self._cached_drives:
            self._cached_drives = [
                d for d in self._cached_drives
                if d['id'] != drive_id
            ]
        return rv

    def is_drive_exist(self, drive_id):
        """Checks if drive physically exists in storage backend.
        Returns True if drive exists, False if drive not exists.
        Raises exception if it's impossible now to check drive existance.
        """
        pd = PersistentDisk.query.filter(
            PersistentDisk.id == drive_id
        ).first()
        if not pd:
            return False
        return self._is_drive_exist(pd)

    def _is_drive_exist(self, pd):
        raise NotImplementedError()

    @staticmethod
    def start_stat(size, name=None, user_id=None):
        """
        Start counting usage statistics.

        You need to provide `name` and `user` or `sys_drive_name`
        :param size: int -> size in GB
        :param name: string -> user's drive name
        :param user_id: id of the drive owner
        """
        PersistentDiskState.start(user_id, name, size)

    @staticmethod
    def end_stat(name=None, user_id=None):
        """
        Finish counting usage statistics.

        You need to provide `name` and `user` or `sys_drive_name`
        :param name: string -> user's drive name
        :param user: object -> user object
        """
        PersistentDiskState.end(user_id, name)

    def enrich_volume_info(self, volume, size, drive_name):
        """Adds storage specific attributes to volume dict.
        Implement in nested classes if needed.
        """
        return volume

    def extract_volume_info(self, volume):
        """Should return a dictionary with fields 'size', 'drive_name', if it
        may be extracted from storage specific info.
        Redefine in nested classes if there is support for that.
        """
        return {}

    def _create_drive(self, drive_name, size):
        """
        To be overwritten by child classes
        """
        return 0

    def _delete_pd(self, pd):
        """
        To be overwritten by child classes
        """
        return 0

    def run_on_first_node(self, command, *args, **kwargs):
        ip = self.get_node_ip()
        return run_remote_command(ip, command, *args, **kwargs)

    def unlock_pd(self, pd):
        """Unlock PD, if it was locked by other node
        """
        pass

    @classmethod
    def check_node_is_locked(cls, node_id):
        """If some storage has KD node-aware dependency, then this method should
        check if the given node is free of storage, or if it is using by the
        storage.
        :return: tuple of lock_flag, reason - lock_flag True if the node is
        in-use, False, if the node is free. Reason will explain of lock reason
        if the node is not free.
        """
        return (False, None)

    @classmethod
    def drive_can_be_deleted(cls, persistent_disk_id):
        """Checks if the given persistent disk can be deleted.
        :param persistent_disk_id: identifier of PersistentDisk model
        :return: tuple of <allowed flag>, reason: allowed flag - True if the
        disk can be deleted. False if the disk can not be deleted. Reason -
        short description why the disk can't be deleted if allowed
        flag = False, Reason is None if allowed flad = True.
        """
        return (True, None)


def execute_run(command, timeout=NODE_COMMAND_TIMEOUT, jsonresult=False,
                catch_exitcodes=None):
    try:
        result = run(command, timeout=timeout)
    except (CommandTimeout, NetworkError):
        raise NodeCommandError(
            'Timeout reached while execute remote command'
        )
    if result.return_code != 0:
        if not catch_exitcodes or result.return_code not in catch_exitcodes:
            raise NodeCommandError(
                'Remote command execution failed (exit code = {})'.format(
                    result.return_code
                )
            )
        raise NodeCommandWrongExitCode(code=result.return_code)
    if jsonresult:
        try:
            result = json.loads(result)
        except (ValueError, TypeError):
            raise NodeCommandError(
                u'Invalid json output of remote command: {}'.format(result))
    return result


def run_remote_command(host_string, command, timeout=NODE_COMMAND_TIMEOUT,
                       jsonresult=False,
                       catch_exitcodes=None):
    """Executes command on remote host via fabric run.
    Optionally timeout may be specified.
    If result of execution is expected in json format, then the output will
    be treated as json.
    """
    with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                  host_string=host_string,
                  warn_only=True):
        return execute_run(command, timeout=timeout, jsonresult=jsonresult,
                           catch_exitcodes=catch_exitcodes)


def get_ceph_credentials():
    """Returns string with options for CEPH client authentication."""
    return '-n client.{0} --keyring={1}'.format(
        CEPH_CLIENT_USER, CEPH_KEYRING_PATH
    )


def get_all_ceph_drives(host):
    drive_list = run_remote_command(
        host,
        'rbd {} list --long --format=json'.format(get_ceph_credentials()),
        jsonresult=True)
    if not isinstance(drive_list, list):
        raise NodeCommandError('Unexpected answer format in "rbd list"')
    all_devices = {
        i['image']: {
            'size': i['size'],
            'in_use': False
        }
        for i in drive_list
    }
    return all_devices


def _get_mapped_ceph_devices_for_node(host):
    """Returns dict with device ('/dev/rbdN') as a key, and ceph image name
    in value.
    """
    rbd_mapped = run_remote_command(
        host,
        'rbd {} showmapped --format=json'.format(get_ceph_credentials()),
        jsonresult=True)
    if not isinstance(rbd_mapped, dict):
        raise NodeCommandError(
            'Unexpected answer format in "rbd showmapped"'
        )
    mapped_devices = {
        j['device']: {
            'pool': j['pool'],
            'name': j['name'],
        }
        for j in rbd_mapped.values()
    }
    return mapped_devices


REDIS_TEMP_MAPPED_HASH = 'kd.temp.rbd.mapped'


def mark_ceph_drive_as_temporary_mapped(drivename, dev, node):
    redis_con = ConnectionPool.get_connection()
    redis_con.hset(
        REDIS_TEMP_MAPPED_HASH, drivename,
        json.dumps({'node': node, 'dev': dev})
    )


def unmark_ceph_drive_as_temporary_mapped(drive):
    redis_con = ConnectionPool.get_connection()
    redis_con.hdel(REDIS_TEMP_MAPPED_HASH, drive)


@celery.task(ignore_result=True)
@exclusive_task(60 * 60)
def unmap_temporary_mapped_ceph_drives_task():
    unmap_temporary_mapped_ceph_drives()


def unmap_temporary_mapped_ceph_drives():
    redis_con = ConnectionPool.get_connection()
    drives = redis_con.hkeys(REDIS_TEMP_MAPPED_HASH)
    if not drives:
        return
    node_to_map = {}
    for drive in drives:
        data = redis_con.hget(REDIS_TEMP_MAPPED_HASH, drive)
        try:
            data = json.loads(data)
        except:
            continue
        node = data.get('node')
        device = data.get('dev')
        if not (node and device):
            continue
        if node not in node_to_map:
            try:
                mapped_drives = _get_mapped_ceph_devices_for_node(node)
                node_to_map[node] = {
                    key: PD_NS_SEPARATOR.join([value['pool'], value['name']])
                    for key, value in mapped_drives.iteritems()
                }
            except:
                current_app.logger.warn('Failed to get mapped devices')
                continue
        node_maps = node_to_map[node]
        try:
            with drive_lock(drive, ttl=NODE_COMMAND_TIMEOUT):
                try:
                    # Unmap drive from node if it is actually mapped.
                    # Clear redis entry if unmap was success. Also clear it if
                    # device is not mapped.
                    if device in node_maps and node_maps[device] == drive:
                        run_remote_command(
                            node,
                            'rbd {} unmap {}'.format(
                                get_ceph_credentials(), device
                            )
                        )
                    redis_con.hdel(REDIS_TEMP_MAPPED_HASH, drive)
                except:
                    current_app.logger.warn('Failed to unmap {}'.format(drive))
        except DriveIsLockedError:
            pass


def _get_ceph_pool_pgnum_by_osdnum(osdnum):
    """Calculates CEPH placement groups number depending on OSDs number.
    http://docs.ceph.com/docs/hammer/rados/operations/placement-groups/#a-preselection-of-pg-num

    """
    OSDNUM_TO_PGNUM = ((5, 128), (10, 512), (50, 4096))
    pgnum = 64
    for osds, pgn in OSDNUM_TO_PGNUM:
        if osdnum < osds:
            pgnum = pgn
            break
    return pgnum


class CephStorage(PersistentStorage):
    storage_name = 'CEPH'

    VOLUME_EXTENSION_KEY = 'rbd'

    CEPH_NOTFOUND_CODE = 2
    CMD_LIST_LOCKERS = "rbd " + get_ceph_credentials() + " lock ls {image} "\
                       "--pool {pool} --format=json"
    CMD_REMOVE_LOCKER = "rbd " + get_ceph_credentials() + " lock remove "\
                        "{image} {id} {locker} --pool {pool}"

    def __init__(self):
        super(CephStorage, self).__init__()
        self._monitors = None

    def get_drive_name_and_pool(self, pd_drive_name):
        """Split PD drive name to drive_name and pool.
        If no pool in PD drive name, return default ceph pool name.
        """
        pool = CEPH_POOL_NAME
        drive_name = pd_drive_name
        parts = pd_drive_name.split(PD_NS_SEPARATOR, 1)
        if len(parts) > 1:
            pool, drive_name = parts
        return pool, drive_name

    def check_namespace_exists(self, node_ip=None, namespace=None):
        """Method ensures that configured namespace exists.
        If it not exists, then will create it.
        For CEPH: namespace == pool name. It creates pool if it not exists.
        """
        if node_ip is None:
            node_ip = self.get_node_ip()
        if namespace is None:
            namespace = CEPH_POOL_NAME
        try:
            pools = run_remote_command(
                node_ip,
                'ceph {} osd lspools --format json'.format(
                    get_ceph_credentials()
                ),
                jsonresult=True
            )
        except:
            return False
        for item in pools:
            if item.get('poolname') == namespace:
                return True
        try:
            osd_stat = run_remote_command(
                node_ip,
                'ceph {} osd stat --format json'.format(
                    get_ceph_credentials()),
                jsonresult=True
            )
            osdnum = osd_stat.get('num_osds')
            pgnum = _get_ceph_pool_pgnum_by_osdnum(osdnum)
            run_remote_command(
                node_ip,
                'ceph {0} osd pool create {1} {2} {2}'.format(
                    get_ceph_credentials(), namespace, pgnum
                )
            )
        except:
            return False
        return True

    def _get_first_node(self):
        query = Node.all_with_flag_query(NodeFlagNames.CEPH_INSTALLED, 'true')
        nodes = query.all()
        for node in nodes:
            k8s_node = node_utils._get_k8s_node_by_host(node.hostname)
            status, _ = node_utils.get_status(node, k8s_node)
            if status == 'running':
                return node
        raise NoNodesError("Can't find node running with ceph")

    def _is_drive_exist(self, pd):
        pool, drive_name = self.get_drive_name_and_pool(pd.drive_name)
        try:
            res = self.run_on_first_node(
                'rbd {0} ls -p {1} --format json'.format(
                    get_ceph_credentials(), pool
                ),
                jsonresult=True,
                catch_exitcodes=[self.CEPH_NOTFOUND_CODE]
            )
        except NodeCommandWrongExitCode:
            # If the pool is absent, then the drive not exists.
            current_app.logger.exception('CEPH pool "%s" not found', pool)
            return False
        return drive_name in res

    def enrich_volume_info(self, volume, size, drive_name):
        """Adds storage specific attributes to volume dict.
        Converts drive name in form namespace/drivename to pool name and
        image name for kubernetes.
        """
        pool_name, image = self.get_drive_name_and_pool(drive_name)

        volume[self.VOLUME_EXTENSION_KEY] = {
            'image': image,
            'keyring': CEPH_KEYRING_PATH,
            'fsType': DEFAULT_FILESYSTEM,
            'user': CEPH_CLIENT_USER,
            'pool': pool_name
        }
        if size is not None:
            volume[self.VOLUME_EXTENSION_KEY]['size'] = size
        volume[self.VOLUME_EXTENSION_KEY]['monitors'] = self.get_monitors()
        return volume

    def extract_volume_info(self, volume):
        res = {}
        if self.VOLUME_EXTENSION_KEY not in volume:
            return res
        # TODO: Is it really needed?
        if not volume[self.VOLUME_EXTENSION_KEY].get('monitors'):
            volume[self.VOLUME_EXTENSION_KEY]['monitors'] = self.get_monitors()
        res['size'] = volume[self.VOLUME_EXTENSION_KEY].get('size')
        image = volume[self.VOLUME_EXTENSION_KEY].get('image')
        pool_name = volume[self.VOLUME_EXTENSION_KEY].get('pool')
        res['drive_name'] = pool_name + PD_NS_SEPARATOR + image
        return res

    def get_monitors(self):
        """
        Parse ceph config and return ceph monitors list
        :return: list -> list of ip addresses
        """
        if self._monitors is not None:
            return self._monitors
        try:
            from ..settings import MONITORS
            self._monitors = [i.strip() for i in MONITORS.split(',')]
        except ImportError:
            # We have no monitor predefined configuration
            conf = self._get_client_config()
            if not conf:
                return
            fo = StringIO(conf)
            cp = ConfigParser()
            try:
                cp.readfp(fo)
            except Exception:
                raise APIError("Cannot get CEPH monitors."
                               " Make sure your CEPH cluster is available"
                               " and KuberDock is configured to use CEPH")
            if not cp.has_option('global', 'mon_host'):
                self._monitors = ['127.0.0.1']
            else:
                self._monitors = [
                    i.strip() for i in cp.get('global', 'mon_host').split(',')
                ]
        return self._monitors

    def _get_client_config(self):
        """
        Returns a ceph-aware node ceph config
        """
        return self.run_on_first_node('cat /etc/ceph/ceph.conf')

    def _makefs(self, drive, fs=DEFAULT_FILESYSTEM):
        """
        Wrapper around checking drive status, mapper, fs creator and unmapper
        :param drive: string -> drive name
        :param fs: string -> desired filesystem
        :return: None or raise an exception in case of error
        """
        if self._is_mapped(drive):      # If device is already mapped it means
            return None                 # it's in use. Exit
        dev = self._map_drive(drive)    # mapping drive
        mark_ceph_drive_as_temporary_mapped(drive, dev, self._cached_node_ip)
        try:
            if self._get_fs(dev):           # if drive already has filesystem
                return None                 # whatever it be return
            self._create_fs(dev, fs)        # make fs
            # sometimes immediate unmap after mkfs returns 16 exit code,
            # to prevent this just wait a little
            time.sleep(5)
        finally:
            self._unmap_drive(dev)
            unmark_ceph_drive_as_temporary_mapped(drive)
        return None

    def _create_fs(self, device, fs=DEFAULT_FILESYSTEM):
        """
        Actually makes a filesystem
        :param fs: string -> fs type
        """
        # it may take a lot of time, so increase the timeout
        self.run_on_first_node(
            'mkfs.{0} {1} > /dev/null 2>&1'.format(fs, device),
            timeout=NODE_COMMAND_TIMEOUT * 10
        )

    def _is_mapped(self, drive):
        """
        The routine is checked if a device is mapped to any of nodes
        :param drive
        """
        try:
            res = self.run_on_first_node(
                'rbd {0} status {1} --format json'.format(
                    get_ceph_credentials(), drive
                ),
                jsonresult=True,
                catch_exitcodes=[self.CEPH_NOTFOUND_CODE]
            )
        except NodeCommandWrongExitCode:
            # Such error we catch when there are no specified drive in the
            # CEPH cluster. Also it means that the drive is not mapped.
            return False
        if isinstance(res, dict):
            return bool(res.get('watchers'))
        return False

    def _map_drive(self, drive):
        """
        Maps drive to a node
        :param drive: string -> drive name
        """
        res = self.run_on_first_node(
            'rbd {0} map {1}'.format(get_ceph_credentials(), drive)
        )
        return res

    def _unmap_drive(self, device):
        """
        Maps drive to a node
        :param drive: string -> drive name
        """
        self.run_on_first_node(
            'rbd {0} unmap {1}'.format(get_ceph_credentials(), device)
        )

    def _get_fs(self, device):
        """
        Tries to determine filesystem on mapped device
        :param device: string -> device name
        """
        try:
            res = self.run_on_first_node(
                'blkid -o value -s TYPE {0}'.format(device)
            )
            return res
        except NodeCommandError:
            return None

    def _create_drive(self, name, size):
        """
        Actually creates a ceph rbd image of a given size.
        :param name: string -> drive name
        :param size: int -> drive size in GB
        :return: int -> return code of 'run'
        """
        mb_size = 1024 * int(size)
        try:
            self.run_on_first_node(
                'rbd {0} create {1} --size={2}'.format(
                    get_ceph_credentials(), name, mb_size
                )
            )
        except NodeCommandError:
            current_app.logger.warning(
                u'Failed to create CEPH drive "%s", size = %s. '
                u'Possibly it already exists',
                name, size)
            return 1
        return 0

    def _delete_pd(self, pd):
        """
        Gets drive list from the first node in the list because all nodes have
        the same list of images. Then tries to delete it. If an image is mapped
        an error will occur.
        :param pd: Instance of PersistentDisk
        """
        if not self._is_mapped(pd.drive_name):
            try:
                self.run_on_first_node('rbd {0} rm {1}'.format(
                    get_ceph_credentials(), pd.drive_name
                ))
                return 0
            except NodeCommandError:
                return 1
        return 1

    def unlock_pd(self, pd):
        pool, image = self.get_drive_name_and_pool(pd.drive_name)
        try:
            cmd = self.CMD_LIST_LOCKERS.format(image=image, pool=pool)
            lock = self.run_on_first_node(cmd, jsonresult=True)
        except:
            current_app.logger.exception(
                "Can't get list of locker for drive {}".format(pd.drive_name))
            return
        for key in lock.keys():
            current_app.logger.debug(
                "try to unlock drive {}".format(pd.drive_name))
            try:
                cmd = self.CMD_REMOVE_LOCKER.format(
                    image=image, id=key, locker=lock[key]['locker'], pool=pool)
                self.run_on_first_node(cmd)
            except:
                current_app.logger.exception(
                    "Can't unlock drive {}".format(pd.drive_name))


class AmazonStorage(PersistentStorage):
    storage_name = 'AWS'

    VOLUME_EXTENSION_KEY = 'awsElasticBlockStore'

    def __init__(self):
        self._conn = None
        try:
            from ..settings import AVAILABILITY_ZONE, REGION, \
                                   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
            self._region = REGION
            self._availability_zone = AVAILABILITY_ZONE
            self._aws_access_key_id = AWS_ACCESS_KEY_ID
            self._aws_secret_access_key = AWS_SECRET_ACCESS_KEY
        except ImportError:
            self._region = None
            self._availability_zone = None
            self._aws_access_key_id = None
            self._aws_secret_access_key = None
        super(AmazonStorage, self).__init__()

    def enrich_volume_info(self, volume, size, drive_name):
        """Adds storage specific attributes to volume dict.
        """
        if self._availability_zone is None:
            return volume
        # volumeID: aws://<availability-zone>/<volume-id>
        volume[self.VOLUME_EXTENSION_KEY] = {
            'volumeID': 'aws://{0}/'.format(self._availability_zone),
            'fsType': DEFAULT_FILESYSTEM,
            'drive': drive_name,
        }
        if size is not None:
            volume[self.VOLUME_EXTENSION_KEY]['size'] = size
        return volume

    def _is_drive_exist(self, pd):
        raw_drives = self._get_raw_drives()
        exists = any(vol.tags.get('Name', 'Nameless') == pd.drive_name
                     for vol in raw_drives)
        return exists

    def extract_volume_info(self, volume):
        res = {}
        if self.VOLUME_EXTENSION_KEY not in volume:
            return res
        res['size'] = volume[self.VOLUME_EXTENSION_KEY].get('size')
        res['drive_name'] = volume[self.VOLUME_EXTENSION_KEY].get('drive')
        return res

    def _get_connection(self):
        if self._conn is not None:
            return
        self._conn = boto.ec2.connect_to_region(
            self._region,
            aws_access_key_id=self._aws_access_key_id,
            aws_secret_access_key=self._aws_secret_access_key)

    def _create_drive(self, name, size):
        """
        Actually creates an amazon EBS of a given size.
        :param name: string -> drive name
        :param size: int -> drive size in GB
        :return: int -> return code of 'run'
        """
        raw_drives = self._get_raw_drives()
        for vol in raw_drives:
            if vol.tags.get('Name', 'Nameless') == name:
                return 17   # errno.EEXIST
        vol = self._conn.create_volume(size, self._availability_zone)
        if vol:
            vol.add_tag('Name', name)
            while vol.status != 'available':
                time.sleep(1)
                vol.update()
            #  self.start_stat(size, sys_drive_name=name)
            return 0

    def _get_raw_drives(self):
        """
        Gets and returns EBS volumes objects as list
        :return: list
        """
        self._get_connection()
        return self._conn.get_all_volumes()

    def _get_raw_drive_by_name(self, name):
        """
        Returns EBS volume object filtered by tag 'Name' if any
        :param name: string -> drive name as EBS tag 'Name'
        :return: object -> boto EBS object
        """
        drives = self._get_raw_drives()
        for vol in drives:
            try:
                item = vol.tags.get('Name', 'Nameless')
                if item == name:
                    return vol
            except ValueError:
                continue
        raise APIError("Drive not found")

    def _delete_pd(self, pd):
        """
        Actually deletes amazon EBS by id
        :param pd: instance of PersistentDisk
        """
        raw_drives = self._get_raw_drives()
        for vol in raw_drives:
            name = vol.tags.get('Name', 'Nameless')
            if name == pd.drive_name:
                #  self.end_stat(sys_drive_name=name)
                return 0 if vol.delete() else 1

    def _makefs(self, drive_name, fs=DEFAULT_FILESYSTEM):
        """
        Wrapper around checking drive status, attacher, fs creator and detacher
        :param drive_name: string -> drive name
        :param fs: string -> desired filesystem
        """
        drive = self._get_raw_drive_by_name(drive_name)
        self._raise_if_attached(drive)
        iid = self._get_first_instance_id()
        device = self._get_next_drive()
        self._handle_drive(drive.id, iid, device)
        self._wait_until_ready(device)
        self._create_fs_if_missing(device, fs)
        self._handle_drive(drive.id, iid, device, False)
        self._wait_until_ready(device, to_be_attached=False)
        return drive.id

    def _wait_until_ready(self, device, to_be_attached=True, timeout=90):
        """Sends to node command to loop until
        state of /proc/partitions is changed
        :param device: string -> a block device, e.g. /dev/xvda
        :param to_be_attached: bool -> toggles checks to be taken: attached or
            detached
        :param timeout: int -> number of seconds to wait for state change
        """
        check = 'n' if to_be_attached else 'z'
        message = 'Device failed to switch to {} state'.format(
            'attached' if to_be_attached else 'detached')

        command = (
            'KDWAIT=0 && while [ "$KDWAIT" -lt {0} ];'
            'do OUT=$(cat /proc/partitions|grep {1});'
            'if [ -{2} "$OUT" ];then break;'
            'else KDWAIT=$(($KDWAIT+1)) && $(sleep 1 && exit 1);'
            'fi;done'.format(
                timeout, device.replace('/dev/', ''), check
            )
        )
        try:
            self.run_on_first_node(command)
        except NodeCommandError:
            raise APIError(message)
        return True

    def _handle_drive(self, drive_id, instance_id, device, attach=True):
        """
        Attaches or detaches a drive
        :param drive_id: string -> EBS volume ID
        :param instance_id: string -> EC2 instance ID
        :param device: string -> block device name, e.g. /dev/xvda
        :param attach: bool -> action to be taken: if True attach otherwise
            detach
        """
        action = (self._conn.attach_volume if attach
                  else self._conn.detach_volume)
        message = 'An error occurred while drive being {0}: {{0}}'.format(
            'attached' if attach else 'detached')
        try:
            action(drive_id, instance_id, device)
        except boto.exception.EC2ResponseError as e:
            raise APIError(message.format(str(e)))

    @staticmethod
    def _raise_if_attached(drive):
        """
        Raises the exception if drive is attached
        :param drive: object -> boto EBS volume object
        """
        if getattr(drive, 'status', None) == 'in-use':
            raise APIError("Drive already attached")

    def _get_first_instance_id(self):
        """
        Gets all instances and filters out by IP pulled from DB
        :return: string
        """
        reservations = self._conn.get_all_reservations()
        for r in reservations:
            for i in r.instances:
                if i.private_ip_address == self.get_node_ip():
                    return i.id
        raise APIError("Instance not found")

    def _get_next_drive(self):
        """
        Gets current node xvdX devices, sorts'em and gets the last device
            letter.
        Then returns next letter device name
        :return: string -> device (/dev/xvdX)
        """
        try:
            res = self.run_on_first_node(
                "ls -1 /dev/xvd*|awk -F '' '/xvd/ {print $9}'|sort"
            )
        except NodeCommandError:
            raise APIError("An error occurred while list of node "
                           "devices was being retrieved")

        last = res.splitlines()[-1]
        last_num = ord(last)
        if last_num >= 122:
            raise APIError("No free letters for devices")
        return '/dev/xvd{0}'.format(chr(last_num+1))

    def _create_fs_if_missing(self, device, fs=DEFAULT_FILESYSTEM):
        self.run_on_first_node(
            "blkid -o value -s TYPE {0} || mkfs.{1} {2}".format(
                device, fs, device
            ),
            timeout=NODE_COMMAND_TIMEOUT * 10
        )


class LocalStorage(PersistentStorage):
    """Handles local storage drives. It is kind of persistent drives, that is
    actually a directory in mounted node's disk.
    """
    storage_name = 'LOCAL'

    VOLUME_EXTENSION_KEY = 'hostPath'

    def __init__(self):
        super(LocalStorage, self).__init__()

    def _add_pod_info_to_drive_list(self, drive_list, user_id=None):
        """In addition to base class method sets flag 'forbidDeletion' to false
        to every drive in drive_list, if there are any pod in 'linkedPods' list
        of this drive. Params and return value are identical to the method
        of the parent class.
        """
        res = super(LocalStorage, self)._add_pod_info_to_drive_list(
            drive_list, user_id
        )
        for item in res:
            item['forbidDeletion'] = bool(item.get('forbidDeletion') or
                                          item.get('linkedPods', None))
        return res

    @classmethod
    def are_pod_volumes_compatible(cls, volumes, owner_id, pod_params):
        """Should check if volumes of one pod can be created.
        For local storage all volumes must be on one node.
        """
        if not volumes:
            return True
        node = None
        for vol in volumes:
            pd = vol.get('persistentDisk', {})
            if not pd:
                continue
            drive_name = pd.get('pdName', None)
            if not drive_name:
                continue
            drive_name = compose_pdname(drive_name, owner_id)
            persistent_disk = PersistentDisk.filter_by(
                drive_name=drive_name
            ).first()
            if not persistent_disk:
                continue
            if persistent_disk.node_id:
                if node is not None and node != persistent_disk.node_id:
                    return False
                node = persistent_disk.node_id
        if node is not None:
            node = Node.query.filter(Node.id == node).first()
            kube_type = pod_params.get(
                'kube_type', Kube.get_default_kube_type()
            )
            if kube_type != node.kube_id:
                return False
        return True

    def _is_drive_exist(self, pd):
        """Checks if directory of local storage exists on the node.
        Returns True if it exists, False otherwise.
        """
        command = 'test -d "{}"'.format(
            self._get_full_drive_path(pd.drive_name)
        )
        failed_test_code = 1
        try:
            res = self.run_on_pd_node(
                pd, command, catch_exitcodes=[failed_test_code]
            )
            if res is None:
                return False
        except NodeCommandWrongExitCode:
            return False
        return True

    @classmethod
    def is_volume_of_the_class(cls, vol):
        if cls.VOLUME_EXTENSION_KEY in vol:
            annotation = vol.get('annotation', {})
            return 'localStorage' in annotation
        return False

    @staticmethod
    def _get_full_drive_path(drive_name):
        path = os.path.join(NODE_LOCAL_STORAGE_PREFIX, drive_name)
        return path

    def enrich_volume_info(self, volume, size, drive_name):
        """Adds storae specific attributes to volume dict.
        """
        full_path = self._get_full_drive_path(drive_name)
        volume[self.VOLUME_EXTENSION_KEY] = {
            'path': full_path,
        }
        # annotation will be moved to 'annotations' section in pod.py
        # Here we will write there path and size for local storage, it will
        # be used by node_network_plugin to create local storage on node
        # and set fs limits for it. Also annotation with localStorage key means
        # that volume is a persistent disk with local storage backend.
        volume['annotation'] = {
            'localStorage': {
                'size': size,
                'path': full_path
            }
        }
        return volume

    def extract_volume_info(self, volume):
        res = {}
        drive_path = volume[self.VOLUME_EXTENSION_KEY].get('path', '')
        drive_name = os.path.basename(drive_path)
        res['drive_name'] = drive_name
        return res

    def _get_drives_from_db(self, user_id=None):
        res = super(LocalStorage, self)._get_drives_from_db(user_id)
        alive_nodes = _get_alive_nodes()
        for item in res:
            pd_node_id = db.session.query(PersistentDisk.node_id).filter(
                PersistentDisk.id == item['id']
            ).first().node_id
            item['available'] = pd_node_id in alive_nodes
            item['node_id'] = pd_node_id
        return res

    def run_on_pd_node(self, pd, command, *args, **kwargs):
        node = Node.query.filter(Node.id == pd.node_id).first()
        if not node:
            current_app.logger.debug(
                'There is no node to execute command: %s', command)
            return
        current_app.logger.debug(
            'Node %s execute command: %s', node.ip, command)
        return run_remote_command(
            node.ip,
            command,
            *args, **kwargs
        )

    def _delete_pd(self, pd):
        """Actually removes directory of the local storage on a node.
        """
        failed_rm_code = 1
        try:
            drive_path = self._get_full_drive_path(pd.drive_name)
            current_app.logger.debug('Deleting local storage: %s', drive_path)
            res = self.run_on_pd_node(
                pd,
                'rm -rf "{}"'.format(drive_path),
                catch_exitcodes=[failed_rm_code]
            )
            if res is None:
                return 1
        except NodeCommandWrongExitCode:
            return 1
        return 0

    @classmethod
    def check_node_is_locked(cls, node_id):
        """For local storage we assume that node is used if there is any PD on
        this node.
        """
        pd_list = PersistentDisk.get_by_node_id(node_id).filter(
            ~PersistentDisk.state.in_([
                PersistentDiskStatuses.TODELETE, PersistentDiskStatuses.DELETED
            ])
        ).all()
        if not pd_list:
            return (False, None)
        users = User.query.filter(
            User.id.in_(item.owner_id for item in pd_list)
        )
        user_id_to_name = {item.id: item.username for item in users}
        user_to_pd_list = defaultdict(list)
        for pd in pd_list:
            user_to_pd_list[user_id_to_name[pd.owner_id]].append(pd.name)
        return True, user_to_pd_list

    @classmethod
    def drive_can_be_deleted(cls, persistent_disk_id):
        """Local Storage disk can not be deleted if there is any not deleted
        pod linked to the disk.
        """
        pd = PersistentDisk.query.filter(
            PersistentDisk.id == persistent_disk_id
        ).one()
        pods = []
        for pod in Pod.query.filter(Pod.owner_id == pd.owner_id):
            if pod.is_deleted:
                continue
            try:
                config = pod.get_dbconfig()
            except (TypeError, ValueError):
                current_app.logger.exception('Invalid pod (%s) config: %s',
                                             pod.id, pod.config)
                continue
            vol = _get_pod_volume_by_pd_name(config, pd.name)
            if not vol:
                continue
            pods.append(pod)
        if not pods:
            return (True, None)
        return (
            False,
            'Persistent Disk is linked by pods: {}'.format(
                ', '.join('"{}"'.format(pod.name) for pod in pods)
            )
        )


def _get_pod_volume_by_pd_name(pod_config, pd_name):
    """Returns entry from volumes_public section of pod configuration
    with given persistent disk name.
    If there is no such an entry, then return None
    :param pod_config: dict of pod configuration which is stored in database
    :param pd_name: name of persistent disk

    """
    for item in pod_config.get('volumes_public', []):
        if item.get('persistentDisk', {}).get('pdName', '') == pd_name:
            return item
    return None


def _get_alive_nodes():
    """Returns node list which is now in running state in kubernetes in form:
        {node_id: node_ip}
    """
    nodes = node_utils.get_nodes_collection()
    return {
        item['id']: item['ip'] for item in nodes if item['status'] == 'running'
    }


def get_storage_class():
    """Returns storage class according to current settings
    """
    if CEPH:
        return CephStorage
    if AWS:
        return AmazonStorage
    return LocalStorage


ALL_STORAGE_CLASSES = [CephStorage, AmazonStorage, LocalStorage]

VOLUME_EXTENSION_TO_STORAGE_CLASS = {
    cls.VOLUME_EXTENSION_KEY: cls
    for cls in ALL_STORAGE_CLASSES
}


def get_storage_class_by_volume_info(volume):
    """Returns appropriate storage class for the given volume.
    Looks for storage specific key in volume dict.
    """
    for key in VOLUME_EXTENSION_TO_STORAGE_CLASS:
        if key in volume:
            cls = VOLUME_EXTENSION_TO_STORAGE_CLASS[key]
            if cls.is_volume_of_the_class(volume):
                return cls
    return None


def check_node_is_locked(node_id, cleanup=False):
    """Checks if node can't be deleted because of persistent storages on it.
    Optionally can delete from DB deleted PD's if they are binded to the node
    (cleanup flag).
    """
    storage_cls = get_storage_class()
    if not storage_cls:
        return (False, None)
    is_locked, reason = storage_cls.check_node_is_locked(node_id)
    if is_locked:
        pd_list = '\n'.join('{0}: {1}'.format(name, ', '.join(disks))
                            for name, disks in reason.iteritems())
        reason = ('users Persistent volumes located on the node \n'
                  'owner name: list of persistent disks\n' + pd_list)
    elif cleanup:
        clean_deleted_pd_binded_to_node(node_id)
    return (is_locked, reason)


def clean_deleted_pd_binded_to_node(node_id):
    """Removes (from DB) deleted and marked for deletion PDs binded to given
    node.
    It is needed when node is being deleted. We don't want to block node
    deletion if there are no active PD on it, but we have to delete
    all bindings to that node.
    """
    PersistentDisk.get_by_node_id(node_id).filter(
        PersistentDisk.state.in_(
            [PersistentDiskStatuses.TODELETE, PersistentDiskStatuses.DELETED]
        )
    ).delete(synchronize_session=False)


def drive_can_be_deleted(pd_id):
    storage_cls = get_storage_class()
    if not storage_cls:
        return (True, None)
    return storage_cls.drive_can_be_deleted(pd_id)
