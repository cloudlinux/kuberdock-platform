import base64
import boto
import boto.ec2
import json
import time

from ConfigParser import ConfigParser
from fabric.api import run, settings, env, hide
from fabric.tasks import execute
from hashlib import md5
from StringIO import StringIO
from fabric.exceptions import CommandTimeout
from flask import current_app

from ..core import db
from ..nodes.models import Node, NodeFlagNames
from ..pods.models import Pod
from ..users.models import User
from ..usage.models import PersistentDiskState
from ..settings import SSH_KEY_FILENAME, CEPH, AWS
from . import pd_utils
from ..utils import APIError


NODE_COMMAND_TIMEOUT = 60

DEFAULT_FILESYSTEM = 'xfs'

class NodeCommandError(Exception):
    """Exceptions during execution commands on nodes."""
    pass

class NoNodesError(Exception):
    """Exception raises when there is no nodes for current storage backend."""
    pass


class PersistentStorage(object):
    storage_name = ''

    VOLUME_EXTENSION_KEY = ''

    def __init__(self):
        env.user = 'root'
        env.skip_bad_hosts = True
        env.key_filename = SSH_KEY_FILENAME
        self._cached_drives = None
        self._cached_node_ip = None

    def get_drives(self):
        """Returns cached drive list. At first call fills the cache by calling
        method _get_drives.
        """
        if self._cached_drives is None:
            try:
                self._cached_drives = self._get_drives()
            except NodeCommandError:
                current_app.logger.exception(
                    'Failed to get drive list from node')
                raise APIError('Remote command failed. '
                               'Can not retrieve drive list from remote host')
        return self._cached_drives

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
        self._bind_to_pod()
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
        self._bind_to_pod()
        # strip owner
        if device_id is None:
            return [dict([(k, v) for k, v in d.items() if k != 'owner'])
                        for d in self.get_drives() if d['owner'] == user.username]
        drives = [dict([(k, v) for k, v in d.items() if k != 'owner'])
                    for d in self.get_drives()
                        if d['owner'] == user.username and d['id'] == device_id]
        if drives:
            return drives[0]

    def get_unmapped_drives(self):
        """
        Returns unmapped drives
        :return: list -> list of dicts of unmapped drives
        """
        return [d for d in self.get_drives() if not d['in_use']]

    def get_user_unmapped_drives(self, user):
        """
        Returns unmapped drives of a user
        :return: list -> list of dicts of unmapped drives of a user
        """
        return [dict([(k, v) for k, v in d.items() if k != 'owner'])
                    for d in self.get_unmapped_drives()
                    if d['owner'] == user.username]

    def create(self, pd):
        """
        Creates a new drive for a user and returns its ID

        :param pd: kubedock.pods.models.PersistentDisk instance
        """
        try:
            rv_code = self._create_drive(pd.drive_name, pd.size)
        except NoNodesError:
            msg = 'Failed to create drive. '\
                  'There is no nodes to perform the operation'
            current_app.logger.exception(msg)
            raise APIError(msg)

        if rv_code == 0:
            data = pd.to_dict()
            if self._cached_drives is not None:
                self._cached_drives.append(data)
            return data
        msg = 'Failed to create drive. Remote command failed.'
        current_app.logger.exception(msg)
        raise APIError(msg)

    def delete(self, name, user):
        """
        Deletes a user drive
        :param name: string -> drive name
        :param user: object -> user object
        """
        drive_name = pd_utils.compose_pdname(name, user)
        rv = self._delete(drive_name)
        if rv is None:
            # drive name not found, try to delete by legacy name
            drive_name = pd_utils.compose_pdname_legacy(name, user)
            rv = self._delete(drive_name)
        if rv == 0 and self._cached_drives is not None:
            self._cached_drives = [
                d for d in self._cached_drives
                if d['name'] != name and d['owner'] != user.username
            ]
        return rv

    def makefs(self, pd, fs=DEFAULT_FILESYSTEM):
        """
        Creates a filesystem on the device

        :param pd: kubedock.pods.models.PersistentDisk instance
        :param fs: string -> fs type by default DEFAULT_FILESYSTEM
        """
        err_msg = u'Failed to make FS for "{}":'.format(pd.drive_name)
        try:
            return self._makefs(pd.drive_name, fs)
        except NodeCommandError:
            msg = err_msg + u' Remote command failed.'
            current_app.logger.exception(msg)
            raise APIError(msg)
        except NoNodesError:
            msg = err_msg + u' There is no nodes to perform the operation.'
            current_app.logger.exception(msg)
            raise APIError(msg)

    def delete_by_id(self, drive_id):
        """
        Deletes a user drive
        :param name: string -> drive id
        """
        rv = self._delete_by_id(drive_id)
        if rv == 0 and self._cached_drives:
            self._cached_drives = [
                d for d in self._cached_drives
                if d['id'] != drive_id
            ]
        return rv

    @staticmethod
    def start_stat(size, name=None, user=None, sys_drive_name=None):
        """
        Start counting usage statistics.

        You need to provide `name` and `user` or `sys_drive_name`
        :param size: int -> size in GB
        :param name: string -> user's drive name
        :param user: object -> user object
        :param sys_drive_name: string -> system drive name
        """
        if name is None or user is None:
            name, user = pd_utils.get_drive_and_user(sys_drive_name)
        PersistentDiskState.start(user.id, name, size)

    @staticmethod
    def end_stat(name=None, user=None, sys_drive_name=None):
        """
        Finish counting usage statistics.

        You need to provide `name` and `user` or `sys_drive_name`
        :param name: string -> user's drive name
        :param user: object -> user object
        :param sys_drive_name: string -> system drive name
        """
        if name is None or user is None:
            PersistentDiskState.end(sys_drive_name=sys_drive_name)
            return
        PersistentDiskState.end(user.id, name)

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

    def _get_pod_drives(self):
        """
        Pulls pod configs from DB and produces persistent drive -> pod name
        mappings if any.
        :return: dict -> 'drive name':'pod name' mapping
        """
        if hasattr(self, '_drives_from_db'):
            return self._drives_from_db
        self._drives_from_db = {}
        pods = db.session.query(Pod).filter(Pod.status != 'deleted')
        for pod in pods:
            try:
                drive_names = self._find_persistent(json.loads(pod.config))
                self._drives_from_db.update(dict.fromkeys(drive_names, pod.name))
            except (TypeError, ValueError):
                continue
        return self._drives_from_db

    @staticmethod
    def _find_persistent(config):
        """
        Iterates through 'volume' list and gets 'scriptableDisk' entries.
        Then base64-decodes them and returns
        :param config: dict -> pod config as dict
        :return: list -> list of names of persistent drives
        """
        data = []
        for v in config['volumes']:
            scriptable = v.get('scriptableDisk')
            if scriptable:
                data.append(base64.b64decode(scriptable['params']).split(';')[1])
        return data

    def _bind_to_pod(self):
        """
        If list of drives has mapped ones add pod it mounted to info
        """
        if not any(drive.get('in_use') for drive in self.get_drives()):
            return
        names = self._get_pod_drives()
        for d in self.get_drives():
            if not d.get('in_use'):
                continue
            user = User.query.filter_by(username=d['owner']).first()
            if not user:
                continue
            name = pd_utils.compose_pdname(d['name'], user)
            d['pod'] = names.get(name)

    def _get_drives(self):
        """
        To be overwritten by child classes
        """
        return []

    def _create_drive(self, drive_name, size):
        """
        To be overwritten by child classes
        """
        return 0

    def _delete(self, drive_name):
        """
        To be overwritten by child classes
        """
        return 0

    def _delete_by_id(self, drive_id):
        """
        To be overwritten by child classes
        """
        return 0

    def run_on_first_node(self, command, *args, **kwargs):
        ip = self.get_node_ip()
        return run_remote_command(ip, command, *args, **kwargs)


def execute_run(command, timeout=NODE_COMMAND_TIMEOUT, jsonresult=False):
    try:
        result = run(command, timeout=timeout)
    except CommandTimeout:
        raise NodeCommandError(
            'Timeout reached while execute remote command'
        )
    if result.return_code != 0:
        raise NodeCommandError(
            'Remote command execution failed (exit code = {})'.format(
                result.return_code
            )
        )
    if jsonresult:
        try:
            result = json.loads(result)
        except (ValueError, TypeError):
            raise NodeCommandError(
                u'Invalid json output of remote command: {}'.format(
                    result
            ))
    return result


def run_remote_command(host_string, command, timeout=NODE_COMMAND_TIMEOUT,
                       jsonresult=False):
    """Executes command on remote host via fabric run.
    Optionally timeout may be specified.
    If result of execution is expected in json format, then the output will
    be treated as json.
    """
    with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                  host_string=host_string,
                  warn_only=True):
        return execute_run(command, timeout=timeout, jsonresult=jsonresult)

def get_all_ceph_drives(host):
    drive_list = run_remote_command(host,
                                    'rbd list --long --format=json',
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


def _get_mapped_ceph_drives_for_node():
    rbd_mapped = execute_run('rbd showmapped --format=json',
                                jsonresult=True)
    if not isinstance(rbd_mapped, dict):
        raise NodeCommandError(
            'Unexpected answer format in "rbd showmapped"'
        )
    mapped_devices = {
        j['name']: {
            'pool': j['pool'],
            'device': j['device'],
        }
        for j in rbd_mapped.values()
    }
    return mapped_devices


def get_mapped_ceph_drives(hosts):
    """Returns dict of mapped drives, keys - host strings, values - results
    of _get_mapped_ceph_drives_for_node method execution.
    """
    with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                  warn_only=True):
        mapped_drives = execute(_get_mapped_ceph_drives_for_node,
                                hosts=hosts)
        return mapped_drives


class CephStorage(PersistentStorage):
    storage_name = 'CEPH'

    VOLUME_EXTENSION_KEY = 'rbd'

    def __init__(self):
        super(CephStorage, self).__init__()
        self._monitors = None

    def _get_first_node(self):
        return Node.all_with_flag_query(
            NodeFlagNames.CEPH_INSTALLED, 'true'
        ).first()

    def enrich_volume_info(self, volume, size, drive_name):
        """Adds storage specific attributes to volume dict.
        """
        volume[self.VOLUME_EXTENSION_KEY] = {
            'image': drive_name,
            'keyring': '/etc/ceph/ceph.client.admin.keyring',
            'fsType': DEFAULT_FILESYSTEM,
            'user': 'admin',
            'pool': 'rbd'
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
        res['drive_name'] = volume[self.VOLUME_EXTENSION_KEY].get('image')
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
        if self._is_mapped(drive):      # If defice is already mapped it means
            return None                 # it's in use. Exit
        dev = self._map_drive(drive)    # mapping drive
        if self._get_fs(dev):           # if drive already has filesystem
            return None                 # whatever it be return
        self._create_fs(dev, fs)        # make fs
        # sometimes immediate unmap after mkfs returns 16 exit code,
        # to prevent this just wait a little
        time.sleep(5)
        self._unmap_drive(dev)
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
        res = self.run_on_first_node(
            'rbd status {0} --format json'.format(drive),
            jsonresult=True
        )
        if isinstance(res, dict):
            return bool(res.get('watchers'))
        return False

    def _map_drive(self, drive):
        """
        Maps drive to a node
        :param drive: string -> drive name
        """
        res = self.run_on_first_node(
            'rbd map {0}'.format(drive)
        )
        return res

    def _unmap_drive(self, device):
        """
        Maps drive to a node
        :param drive: string -> drive name
        """
        res = self.run_on_first_node(
            'rbd unmap {0}'.format(device)
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
                'rbd create {0} --size={1}'.format(name, mb_size)
            )
        except NodeCommandError:
            return 1
        self.start_stat(size, sys_drive_name=name)
        return 0

    @staticmethod
    def _get_nodes(first_only=False):
        """
        Returns list of node ip -> hostname mappings from DB. If first only is
        True then takes the first node only
        :param first_only: boolean
        :return: dict -> dict of node ip -> hostname
        """
        query = Node.all_with_flag_query(NodeFlagNames.CEPH_INSTALLED, 'true')
        if not first_only:
            return {k: v for k, v in query.values(Node.ip, Node.hostname)}
        rv = query.first()
        if rv:
            return {rv.ip: rv.hostname}

    def _delete_by_id(self, drive_id):
        """
        Gets drive list from the first node in the list because all nodes have
        the same list of images. Then tries to delete it. If an image is mapped
        an error will occur.
        :param drive_id: string -> md5 hash of drive name
        """
        raw_drives = self._get_raw_drives(check_inuse=True)
        for name, data in raw_drives.iteritems():
            hashed = md5(name).hexdigest()
            if hashed != drive_id:
                continue
            self.end_stat(sys_drive_name=name)
            if data['in_use']:
                return 1
            try:
                self.run_on_first_node('rbd rm {0}'.format(name))
            except NodeCommandError:
                return 1
            return 0
        return None

    def _delete(self, drive_name):
        """
        Gets drive list. Then tries to delete given drive it.
        If an image is mapped an error will occur.
        :param drive_name: string -> drive name
        """
        raw_drives = self._get_raw_drives(check_inuse=True)
        if drive_name not in raw_drives:
            return None
        data = raw_drives[drive_name]
        self.end_stat(sys_drive_name=drive_name)
        if data['in_use']:
            return 1
        try:
            self.run_on_first_node('rbd rm {0}'.format(drive_name))
        except NodeCommandError:
            return 1
        return 0

    def _get_raw_drives(self, check_inuse=True):
        """
        Polls hosts and gets volume data from them
        :param check_inuse: if flag is specified, then every node will be
            checked for mapped volumes. Every mapped volume will be merked as
            'in_use' = True. If the flag is not specified, then the method will
            return list of drives without usage check.
        """
        try:
            all_drives = get_all_ceph_drives(self.get_node_ip())
        except NoNodesError:
            return {}

        if not check_inuse:
            return all_drives

        nodes = self._get_nodes(first_only=False)
        if not nodes:
            return {}

        mapped_drives = get_mapped_ceph_drives(nodes.keys())
        for node, drives in mapped_drives.iteritems():
            for name, data in drives.iteritems():
                if name not in all_drives:
                    continue
                entry = all_drives[name]
                nodes = entry.get('nodes') or []
                nodes.append(node)
                entry.update(data)
                entry['nodes'] = nodes
                entry['in_use'] = True
        return all_drives

    def _get_drives(self):
        raw_drives = self._get_raw_drives(check_inuse=True)
        drives = []
        for item, data in raw_drives.iteritems():   # iterate by drive names
            name, user = pd_utils.get_drive_and_user(item)
            if not user:
                # drive name does not contain separator. Skip it
                continue
            entry = {'name': name,
                     'drive_name': item,
                     'owner': user.username,
                     'size': int(data['size'] / 1073741824),
                     'id': md5(item).hexdigest(),
                     'in_use': data['in_use']}
            if data['in_use']:
                entry['device'] = data.get('device')
                entry['node'] = data['nodes'][0]
            drives.append(entry)
        return drives


class AmazonStorage(PersistentStorage):
    storage_name = 'AWS'

    VOLUME_EXTENSION_KEY = 'awsElasticBlockStore'

    def __init__(self):
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

    def extract_volume_info(self, volume):
        res = {}
        if self.VOLUME_EXTENSION_KEY not in volume:
            return res
        res['size'] = volume[self.VOLUME_EXTENSION_KEY].get('size')
        res['drive_name'] = volume[self.VOLUME_EXTENSION_KEY].get('drive')
        return res


    def _get_connection(self):
        if hasattr(self, '_conn'):
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
            self.start_stat(size, sys_drive_name=name)
            return 0

    def _get_raw_drives(self):
        """
        Gets and returns EBS volumes objects as list
        :return: list
        """
        if not hasattr(self, '_conn'):
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

    def _get_drives(self):
        drives = []
        raw_drives = self._get_raw_drives()
        for vol in raw_drives:
            item = vol.tags.get('Name', 'Nameless')
            name, user = pd_utils.get_drive_and_user(item)
            if not user:
                continue
            entry = {'name': name,
                     'drive_name': item,
                     'owner': user.username,
                     'size': vol.size,
                     'id': md5(item).hexdigest(),
                     'in_use': True if vol.status == 'in_use' else False}
            if vol.status == 'in_use':
                entry['node'] = vol.attach_data.instance_id
                entry['device'] = vol.attach_data.device
            drives.append(entry)
        return drives

    def _delete_by_id(self, drive_id):
        """
        Actually deletes amazon EBS by id
        :param drive_id: string -> md5 hash of drive name
        """
        raw_drives = self._get_raw_drives()
        for vol in raw_drives:
            name = vol.tags.get('Name', 'Nameless')
            if md5(name).hexdigest() == drive_id:
                self.end_stat(sys_drive_name=name)
                return 0 if vol.delete() else 1

    def _delete(self, drive_name):
        """
        Gets drive list from the first node in the list because all nodes have
        the same list of images. Then tries to delete it. If an image is mapped
        an error will occur.
        :param drive_name: string -> drive name
        """
        raw_drives = self._get_raw_drives()
        for vol in raw_drives:
            name = vol.tags.get('Name', 'Nameless')
            if name == drive_name:
                self.end_stat(sys_drive_name=drive_name)
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
        """
        Sends to node command to loop until state of /proc/partitions is changed
        :param device: string -> a block device, e.g. /dev/xvda
        :param to_be_attached: bool -> toggles checks to be taken: attached or detached
        :param timeout: int -> number of seconds to wait for state change
        """
        check = 'n' if to_be_attached else 'z'
        message = 'Device failed to switch to {} state'.format(
            'attached' if to_be_attached else 'detached')

        command = ('KDWAIT=0 && while [ "$KDWAIT" -lt {0} ];'
                   'do OUT=$(cat /proc/partitions|grep {1});'
                   'if [ -{2} "$OUT" ];then break;'
                   'else KDWAIT=$(($KDWAIT+1)) && $(sleep 1 && exit 1);'
                   'fi;done'.format(timeout, device.replace('/dev/', ''), check))
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
        :param attach: bool -> action to be taken: if True attach otherwise detach
        """
        action = self._conn.attach_volume if attach else self._conn.detach_volume
        message = 'An error occurred while drive being {0}: {{0}}'.format(
            'attached' if attach else 'detached')
        try:
            action(drive_id, instance_id, device)
        except boto.exception.EC2ResponseError, e:
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
        Gets current node xvdX devices, sorts'em and gets the last device letter.
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


def get_storage_class():
    """Returns storage class according to current settings
    """
    if CEPH:
        return CephStorage
    if AWS:
        return AmazonStorage
    return None


ALL_STORAGE_CLASSES = [CephStorage, AmazonStorage]

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
            return VOLUME_EXTENSION_TO_STORAGE_CLASS[key]
    return None
