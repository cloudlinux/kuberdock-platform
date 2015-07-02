import base64
import boto.ec2
import json

from fabric.api import run, settings, env, hide
from fabric.tasks import execute
from hashlib import md5
from operator import itemgetter

from ..core import db
from ..nodes.models import Node
from ..pods.models import Pod
from ..settings import PD_SEPARATOR


class PersistentStorage(object):

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
        env.user = 'root'
        env.skip_bad_hosts = True
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

    def _create_drive(self, name, size):
        """
        Actually creates a ceph rbd image of a given size.
        :param name: string -> drive name
        :param size: int -> drive size in GB
        :return: int -> return code of 'run'
        """
        ip = db.session.query(Node).first().ip
        mb_size = int(1024 * size)
        with settings(host_string=ip):
            with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                          warn_only=True):
                rv = run('rbd create {0} --size={1}'.format(name, mb_size))
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
            return 0

    def _get_raw_drives(self):
        if not hasattr(self, '_conn'):
            self._get_connection()
        return self._conn.get_all_volumes()

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
                return 0 if vol.delete() else 1