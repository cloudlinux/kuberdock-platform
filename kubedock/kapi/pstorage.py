import base64
import boto
import boto.ec2
import json
import time

from ConfigParser import ConfigParser
from fabric.api import run, settings, env, hide
from fabric.tasks import execute
from hashlib import md5
from operator import itemgetter
from StringIO import StringIO

from ..core import db
from ..nodes.models import Node
from ..pods.models import Pod
from ..users.models import User
from ..usage.models import PersistentDiskState
from ..settings import PD_SEPARATOR, SSH_KEY_FILENAME
from ..utils import APIError


class PersistentStorage(object):

    def __init__(self):
        env.user = 'root'
        env.skip_bad_hosts = True
        env.key_filename = SSH_KEY_FILENAME

    def __getattr__(self, attr):
        if attr == '_first_node_ip':
            item = db.session.query(Node).first()
            if item is None:
                raise type('NodesNotFoundError', (Exception,), {})(
                    'Unable to get any node from database')
            self.__dict__['_first_node_ip'] = item.ip
            return item.ip
        raise AttributeError('No such attribute: {0}'.format(attr))

    def get(self, drive_id=None):
        """
        Returns list of all persistent storage data
        :return: list -> list of dicts
        """
        if not hasattr(self, '_drives'):
            self._get_drives()
        self._bind_to_pod()
        if drive_id is None:
            return self._drives
        drives = [i for i in self._drives if i['id'] == drive_id]
        if drives:
            return drives[0]

    def get_by_user(self, user, device_id=None):
        """
        Returns list of persistent drives of a certain user
        :param user: object -> user object got from SQLAlchemy
        :return: list -> list of dicts
        """
        if not hasattr(self, '_drives'):
            self._get_drives()
        self._bind_to_pod()
        # strip owner
        if device_id is None:
            return [dict([(k, v) for k, v in d.items() if k != 'owner'])
                        for d in self._drives if d['owner'] == user.username]
        drives = [dict([(k, v) for k, v in d.items() if k != 'owner'])
                    for d in self._drives
                        if d['owner'] == user.username and d['id'] == device_id]
        if drives:
            return drives[0]

    def get_unmapped_drives(self):
        """
        Returns unmapped drives
        :return: list -> list of dicts of unmapped drives
        """
        return [d for d in self._drives if not d['in_use']]

    def get_user_unmapped_drives(self, user):
        """
        Returns unmapped drives of a user
        :return: list -> list of dicts of unmapped drives of a user
        """
        return [dict([(k, v) for k, v in d.items() if k != 'owner'])
                    for d in self.get_unmapped_drives() if d['owner'] == user.username]

    def create(self, name, size, user):
        """
        Creates a new drive for a user and returns its ID
        :param name: string -> drive name
        :params size: int -> drive size in GB
        :param user: object -> user object
        """
        drive_name = '{0}{1}{2}'.format(name, PD_SEPARATOR, user.username)
        rv_code = self._create_drive(drive_name, size)
        if rv_code == 0:
            data = {
                'id'     : md5(drive_name).hexdigest(),
                'name'   : name,
                'owner'  : user.username,
                'size'   : size,
                'in_use' : False}
            if hasattr(self, '_drives'):
                self._drives.append(data)
            return data

    def delete(self, name, user):
        """
        Deletes a user drive
        :param name: string -> drive name
        :param user: object -> user object
        """
        drive_name = '{0}{1}{2}'.format(name, PD_SEPARATOR, user.username)
        rv = self._delete(drive_name)
        if rv == 0 and hasattr(self, '_drives'):
            self._drives = [d for d in self._drives
                if d['name'] != name and d['owner'] != user.username]
        return rv

    def makefs(self, drive, user, fs='ext4'):
        """
        Creates a filesystem on the device
        :param fs: string -> fs type by default ext4
        """
        drive_name = '{0}{1}{2}'.format(drive, PD_SEPARATOR, user.username)
        self._makefs(drive_name, fs)

    def delete_by_id(self, drive_id):
        """
        Deletes a user drive
        :param name: string -> drive id
        """
        rv = self._delete_by_id(drive_id)
        if rv == 0 and hasattr(self, '_drives'):
            self._drives = [d for d in self._drives
                if d['id'] != drive_id]
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
            name, username = sys_drive_name.rsplit(PD_SEPARATOR, 1)
            user = User.query.filter_by(username=username).one()
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

    def _get_pod_drives(self):
        """
        Pulls pod configs from DB and produces persistent drive -> pod name
        mappings if any.
        :return: dict -> 'drive name':'pod name' mapping
        """
        if hasattr(self, '_drives_from_db'):
            return self._drives_from_db
        self._drives_from_db = {}
        pods = db.session.query(Pod).filter(Pod.status!='deleted')
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
        if not any(map(itemgetter('in_use'), self._drives)):
            return
        names = self._get_pod_drives()
        for d in filter(itemgetter('in_use'), self._drives):
            name = '{0}{1}{2}'.format(d['name'], PD_SEPARATOR, d['owner'])
            d['pod'] = names.get(name)

    def _get_drives(self):
        """
        To be overwritten by child classes
        """
        self._drives = []

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

class CephStorage(PersistentStorage):

    def __init__(self):
        super(CephStorage, self).__init__()

    @staticmethod
    def _poll():
        """
        Gets all ceph images list and list of images mapped to a node
        Returns dict of all devices where mapped device entries
        have additional values
        :return: dict -> device name mapped to mapping info
        """
        all_devices = dict([(i['image'], {'size': i['size'], 'in_use': False})
            for i in json.loads(run('rbd list --long --format=json'))])
        mapped_devices = dict([
            (j['name'], {'pool': j['pool'], 'device': j['device'], 'in_use': True})
                for j in json.loads(run('rbd showmapped --format=json')).values()])
        for device in mapped_devices:
            all_devices[device].update(mapped_devices[device])
        return all_devices

    def get_monitors(self):
        """
        Parse ceph config and return ceph monitors list
        :return: list -> list of ip addresses
        """
        conf = self._get_client_config()
        if not conf:
            return
        fo = StringIO(conf)
        cp = ConfigParser()
        try:
            cp.readfp(fo)
        except Exception:
            raise APIError("Cannot get CEPH monitors")
        if not cp.has_option('global', 'mon_host'):
            return ['127.0.0.1']
        return [i.strip() for i in cp.get('global', 'mon_host').split(',')]

    def _get_client_config(self):
        """
        Returns a ceph-aware node ceph config
        """
        with settings(host_string=self._first_node_ip):
            with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                          warn_only=True):
                return run('cat /etc/ceph/ceph.conf')

    def _makefs(self, drive, fs='ext4'):
        """
        Wrapper around checking drive status, mapper, fs creator and unmapper
        :param drive: string -> drive name
        :param fs: string -> desired filesystem
        """
        if self._is_mapped(drive):      # If defice is already mapped it means
            return                      # it's in use. Exit
        dev = self._map_drive(drive)    # mapping drive
        if self._get_fs(dev):           # if drive already has filesystem
            return                      # whatever it be return
        self._create_fs(dev, fs)        # make fs
        self._unmap_drive(dev)
        return True

    def _create_fs(self, device, fs='ext4'):
        """
        Actually makes a filesystem
        :param fs: string -> fs type
        """
        with settings(host_string=self._first_node_ip):
            with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                          warn_only=True):
                rv = run('mkfs.{0} {1} > /dev/null 2>&1'.format(fs, device))
                if rv.return_code != 0:
                    raise type('NodeCommandError', (Exception,), {})(
                        'Node command returned non-zero status')


    def _is_mapped(self, drive):
        """
        The routine is checked if a device is mapped to any of nodes
        :param drive
        """
        with settings(host_string=self._first_node_ip):
            with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                          warn_only=True):
                rv = run('rbd info {0} --format json'.format(drive))
                if rv.return_code != 0:
                    raise type('NodeCommandError', (Exception,), {})(
                        'Node command returned non-zero status')
                try:
                    if json.loads(rv).get('watchers'):
                        return True
                    return False
                except (ValueError, TypeError):
                    raise type('NodeCommandError', (Exception,), {})(
                        'Node command returned unexpected result')

    def _map_drive(self, drive):
        """
        Maps drive to a node
        :param drive: string -> drive name
        """
        with settings(host_string=self._first_node_ip):
            with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                          warn_only=True):
                rv = run('rbd map {0}'.format(drive))
                if rv.return_code != 0:
                    raise type('NodeCommandError', (Exception,), {})(
                        'Could not map drive: non-zero status')
                return rv

    def _unmap_drive(self, device):
        """
        Maps drive to a node
        :param drive: string -> drive name
        """
        with settings(host_string=self._first_node_ip):
            with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                          warn_only=True):
                rv = run('rbd unmap {0}'.format(device))
                if rv.return_code != 0:
                    raise type('NodeCommandError', (Exception,), {})(
                        'Could not unmap drive: non-zero status')

    def _get_fs(self, device):
        """
        Tries to determine filesystem on mapped device
        :param device: string -> device name
        """
        with settings(host_string=self._first_node_ip):
            with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                          warn_only=True):
                rv = run('blkid -o value -s TYPE {0}'.format(device))
                if rv.return_code != 0:
                    return
                return rv

    def _create_drive(self, name, size):
        """
        Actually creates a ceph rbd image of a given size.
        :param name: string -> drive name
        :param size: int -> drive size in GB
        :return: int -> return code of 'run'
        """
        mb_size = 1024 * int(size)
        with settings(host_string=self._first_node_ip):
            with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                          warn_only=True):
                rv = run('rbd create {0} --size={1}'.format(name, mb_size))
                if rv.return_code == 0:
                    self.start_stat(size, sys_drive_name=name)
                return rv.return_code

    @staticmethod
    def _get_nodes(first_only=False):
        """
        Returns list of node ip -> hostname mappings from DB. If first only is
        True then takes the first node only
        :param first_only: boolean
        :return: dict -> dict of node ip -> hostname
        """
        if not first_only:
            return dict([(k, v)
                for k, v in db.session.query(Node).values(Node.ip, Node.hostname)])
        rv = db.session.query(Node).first()
        if rv:
            return {rv.ip: rv.hostname}

    def _delete_by_id(self, drive_id):
        """
        Gets drive list from the first node in the list because all nodes have
        the same list of images. Then tries to delete it. If an image is mapped
        an error will occur.
        :param drive_id: string -> md5 hash of drive name
        """
        raw_drives = self._get_raw_drives(first_only=True)
        for node in raw_drives:
            for name, data in raw_drives[node].items():
                hashed = md5(name).hexdigest()
                if hashed == drive_id:
                    self.end_stat(sys_drive_name=name)
                    if data['in_use']:
                        return
                    with settings(host_string=node):
                        with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                                      warn_only=True):
                            rv = run('rbd rm {0}'.format(name))
                            return rv.return_code

    def _delete(self, drive_name):
        """
        Gets drive list from the first node in the list because all nodes have
        the same list of images. Then tries to delete it. If an image is mapped
        an error will occur.
        :param drive_name: string -> drive name
        """
        raw_drives = self._get_raw_drives(first_only=True)
        for node in raw_drives:
            for name, data in raw_drives[node].items():
                if name == drive_name:
                    self.end_stat(sys_drive_name=drive_name)
                    if data['in_use']:
                        return
                    with settings(host_string=node):
                        with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                                      warn_only=True):
                            rv = run('rbd rm {0}'.format(name))
                            return rv.return_code

    def _get_raw_drives(self, first_only=False):
        """
        Polls hosts and gets volume data from them
        """
        nodes = self._get_nodes(first_only)

        # Got dict: node ip -> node data
        with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                      warn_only=True):
            return execute(self._poll, hosts=nodes.keys())

    def _get_drives(self):
        if hasattr(self, '_drives'):
            return
        raw_drives = self._get_raw_drives()
        drives = {}
        for node in raw_drives: # iterate by node ip addresses or names
            for item in raw_drives[node]:   # iterate by drive names
                try:
                    drive, user = item.rsplit(PD_SEPARATOR, 1)
                except ValueError:  # drive name does not contain separator. Skip it
                    continue
                entry = {'name'  : drive,
                         'owner' : user,
                         'size'  : int(raw_drives[node][item]['size'] / 1073741824),
                         'id'    : md5(item).hexdigest(),
                         'in_use': raw_drives[node][item]['in_use']}
                if raw_drives[node][item]['in_use']:
                    entry['device'] = raw_drives[node][item].get('device')
                    entry['node'] = node
                if item not in drives:
                    drives[item] = entry
                elif item in drives and not drives[item]['in_use']:
                    drives[item].update(entry)
        self._drives = drives.values()


class AmazonStorage(PersistentStorage):

    def __init__(self):
        try:
            from ..settings import AVAILABILITY_ZONE, REGION, \
                                   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
            self._region = REGION
            self._availability_zone = AVAILABILITY_ZONE
            self._aws_access_key_id = AWS_ACCESS_KEY_ID
            self._aws_secret_access_key = AWS_SECRET_ACCESS_KEY
        except ImportError:
            pass
        super(AmazonStorage, self).__init__()

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
        if hasattr(self, '_drives'):
            return
        self._drives = []
        raw_drives = self._get_raw_drives()
        for vol in raw_drives:
            try:
                item = vol.tags.get('Name', 'Nameless')
                drive, user = item.rsplit(PD_SEPARATOR, 1)
            except ValueError:
                continue
            entry = {'name'  : drive,
                     'owner' : user,
                     'size'  : vol.size,
                     'id'    : md5(item).hexdigest(),
                     'in_use': True if vol.status == 'in_use' else False}
            if vol.status == 'in_use':
                entry['node'] = vol.attach_data.instance_id
                entry['device'] = vol.attach_data.device
            self._drives.append(entry)

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

    def _makefs(self, drive_name, fs='ext4'):
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

        with settings(host_string=self._first_node_ip):
            with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                          warn_only=True):
                rv = run(command)
                if rv.return_code == 0:
                    return True
        raise APIError(message)

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
                if i.private_ip_address == self._first_node_ip:
                    return i.id
        raise APIError("Instance not found")

    def _get_next_drive(self):
        """
        Gets current node xvdX devices, sorts'em and gets the last device letter.
        Then returns next letter device name
        :return: string -> device (/dev/xvdX)
        """
        with settings(host_string=self._first_node_ip):
            with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                          warn_only=True):
                rv = run("ls -1 /dev/xvd*|awk -F '' '/xvd/ {print $9}'|sort")
                if rv.return_code != 0:
                    raise APIError("An error occurred while list of node devices was being retrieved")
                last = rv.splitlines()[-1]
                last_num = ord(last)
                if last_num >= 122:
                    raise APIError("No free letters for devices")
                return '/dev/xvd{0}'.format(chr(last_num+1))


    def _create_fs_if_missing(self, device, fs='ext4'):
        with settings(host_string=self._first_node_ip):
            with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                          warn_only=True):
                run("blkid -o value -s TYPE {0} || mkfs.{1} {2}".format(
                    device, fs, device))
