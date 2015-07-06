import base64
import datetime
import json
import logging
import operator
import os
import pwd
import random
import string

from ..image.image import Image
from ..helper import KubeQuery, PrintOut


class KubeCtl(KubeQuery, PrintOut, object):
    """
    Class for managing KuberDock entities
    """

    def __init__(self, **args):
        """
        Constructor
        """
        for key, val in args.items():
            setattr(self, key, val)

    def get(self):
        """
        Gets a list of user pods and prints either all or one
        """
        self._WANTS_HEADER = True
        self._FIELDS = (('name', 32), ('images', 32), ('labels', 64), ('status', 10))
        data = self._unwrap(self._get('/api/podapi/'))
        if hasattr(self, 'name'):
            self._list([self._transform(i) for i in data if i['name'] == self.name])
        else:
            self._list([self._transform(i) for i in data])

    def describe(self):
        """
        Gets a list of user pods, filter out one of them by name and prints it
        """
        data = self._unwrap(self._get('/api/podapi/'))
        try:
            self._show([i for i in data if i['name'] == self.name][0])
        except IndexError:
            print "No such item"

    def delete(self):
        """
        Gets a list of user pods, filter out one of them by name and prints it
        """
        data = self._unwrap(self._get('/api/podapi/'))
        try:
            item = [i for i in data if i['name'] == self.name][0]
            self._del('/api/podapi/' + item['id'])
        except (IndexError, KeyError):
            print "No such item"

    @staticmethod
    def _transform(data):
        ready = ['name', 'status']
        out = dict([(k, v) for k, v in data.items() if k in ready])
        out['labels'] = ','.join(
            ['{0}={1}'.format(k, v) for k, v in data.get('labels', {}).items()])
        out['images'] = ','.join(
            [i.get('image', 'imageless') for i in data.get('containers', [])])
        return out


class KuberDock(KubeCtl):
    """
    Class for creating KuberDock entities
    """
    KUBEDIR = '.kube_containers'    #default directory for storing container configs
    EXT = '.kube'
    def __init__(self, **args):
        """Constructor"""
        # First we need to load possibly saved configuration for a new pod
        # and only after loading apply data
        self.containers = []
        self.volumes = []
        self._load(args)
        super(KuberDock, self).__init__(**args)

    def create(self):
        self.set()

    def set(self):
        if hasattr(self, 'image'):
            i = self._get_image()
            i.kubes = int(self.kubes)
            for attr in 'container_port', 'host_port', 'protocol', 'mount_path':
                try:
                    operator.methodcaller(
                        'set_' + attr, getattr(self, attr), self.index)(i)
                except AttributeError:
                    continue
            if i.ports:
                for k, v in enumerate(i.ports):
                    operator.methodcaller('set_public', self.set_public_ip, k)(i)

        if self.delete is None:
            self._save()
        else:
            self._delete_container_image()
            self._save()

    def save(self):
        """
        Sends POST request to KuberDock to save configured container
        """
        data = self._prepare()
        kubes = self._get_kubes()
        try:
            data['kube_type'] = int(kubes[data['kube_type']])
        except KeyError:
            raise SystemExit("Valid kube type must be set. "
                             "Run 'kuberdock kubes' to get available kube types")
        except (ValueError, TypeError):
            raise SystemExit("Invalid kube type. "
                             "Run 'kuberdock kubes' to get available kube types")
        try:
            res = self._post('/api/podapi/', json.dumps(data), True)
            if res.get('status') != 'error':
                self._clear()
            else:
                raise SystemExit(str(res))
        except TypeError, e:
            raise SystemExit(str(e))

    def list(self):
        """
        Lists all pending containers
        """
        names = []
        try:
            for f in os.listdir(self._kube_path):
                if not f.endswith(self.EXT):
                    continue
                names.append(f[:f.index(self.EXT)])
            self._list([{'name': base64.b64decode(i)} for i in names])
        except OSError:
            pass

    def kubes(self):
        """
        Returns list of user kubes
        """
        self._WANTS_HEADER = True
        self._FIELDS = (('id', 12), ('name', 32))
        data = self._get_kubes()
        self._list([{'name': k, 'id': v} for k, v in data.items()])

    def start(self):
        self._FIELDS = (('status', 32),)
        pod = self._get_pod()
        if pod['status'] == 'stopped':
            pod['command'] = 'start'
        res = self._unwrap(self._put('/api/podapi/'+pod['id'], json.dumps(pod)))
        if self.json:
            self._print_json(res)
        else:
            self._print(res)

    def stop(self):
        self._FIELDS = (('status', 32),)
        pod = self._get_pod()
        if pod['status'] in ['running', 'pending']:
            pod['command'] = 'stop'
        res = self._unwrap(self._put('/api/podapi/'+pod['id'], json.dumps(pod)))
        if self.json:
            self._print_json(res)
        else:
            self._print(res)

    def forget(self):
        """
        Deletes one or all pending containers
        """
        if self.name:
            return self._forget_one()
        return self._forget_all()

    def search(self):
        image = Image(vars(self))
        image.search()

    def image_info(self):
        image = Image(vars(self))
        image.get()

    def describe(self):
        if not os.path.exists(self._data_path):
            raise SystemExit("No such item")
        data = self._prepare()
        self._show(data)

    def _forget_all(self):
        """
        Deletes all pending containers
        """
        try:
            for f in os.listdir(self._kube_path):
                if not f.endswith(self.EXT):
                    continue
                _path = os.path.join(self._kube_path, f)
                os.unlink(_path)
        except OSError:
            pass

    def _forget_one(self):
        """
        Deletes a given pending container
        """
        if self._data_path:
            os.unlink(self._data_path)

    def _get_pod(self):
        data = self._unwrap(self._get('/api/podapi/'))
        item = [i for i in data if i['name'] == self.name]
        if item:
            return item[0]

    def _load(self, args):
        """
        Loads prevously saved pod data from a json file
        :param args: dict -> command line arguments
        """
        name = args.get('name', 'unnamed-1')
        self._resolve_data_path(name)
        try:
            with open(self._data_path) as data:
                for attr, val in json.load(data).items():
                    setattr(self, attr, val)
        except (IOError, ValueError, TypeError): # no file, no JSON
            pass

    def _save(self):
        """
        Saves current container as JSON file
        """
        if not hasattr(self, '_data_path') or self._data_path is None:
            raise SystemExit("No data path. No place to save to")

        # Trying to create the folder for storing configs.
        try:
            os.mkdir(self._kube_path)
        except OSError, e:
            if e.strerror != 'File exists':
                raise SystemExit(e.strerror)
        if not os.path.exists(self._data_path) and self.action == 'set':
            raise SystemExit("Use create command before setup pod")

        with open(self._data_path, 'w') as o:
            json.dump(self._prepare(), o)

    def _prepare(self):
        valid = set(['name', 'containers', 'volumes', 'service', 'replicationController',
                     'replicas', 'set_public_ip', 'kube_type', 'restartPolicy', 'public_ip'])
        self.replicationController = True
        self._prepare_volumes()
        self._prepare_ports()
        data = dict(filter((lambda x: x[0] in valid), vars(self).items()))

        return data

    def _prepare_volumes(self):
        """
        Makes names for volumeMount entries and populate 'volumes' with them
        :param data: dict -> data to process
        """
        for c in self.containers:
            if c.get('volumeMounts') is None:
                c['volumeMounts'] = []
                continue
            c['volumeMounts'] = [v for v in c['volumeMounts']
                                    if v.get('mountPath')]
            for vm in c['volumeMounts']:
                if not vm.get('name'):
                    vm['name'] = \
                    self._generate_image_name(vm['mountPath']).replace('/', '-')
                    vol = [v for v in self.volumes if v['name'] == vm['name']]
                    if not vol:
                        self.volumes.append({'name': vm['name'], 'emptyDir': {}})

    def _prepare_ports(self):
        """Checks if all necessary port entry data are set"""
        is_public_ip = []
        for c in self.containers:
            for p in c['ports']:
                is_public_ip.append(p.get('isPublic'))
        if True in is_public_ip:
            ip = self._get_free_host()
            if ip:
                self.public_ip = ip

    def _resolve_containers_directory(self):
        """
        Container configs are kept in a user homedir. Get the path to it
        """
        if hasattr(self, '_kube_path'):
            return
        uid = os.geteuid()
        homedir = pwd.getpwuid(uid).pw_dir
        self._kube_path = os.path.join(homedir, self.KUBEDIR)

    def _resolve_data_path(self, name):
        """
        Get the path of a pending container config
        :param name: string -> name of pening pod
        """
        if hasattr(self, '_data_path'):
            return
        self._resolve_containers_directory()
        encoded_name = base64.urlsafe_b64encode(name) + self.EXT
        self._data_path = os.path.join(self._kube_path, encoded_name)

    def _get_image(self):
        """
        Return image data from a previously saved image or create a new one
        and populate it with pulled data
        :param name: image name, i.e fedora/apache -- string
        """
        for item in self.containers:
            if item.get('image') == self.image:
                return Image(item)     # return once configured image

        _n = self._generate_image_name(self.image)    # new image
        image = {'image': self.image, 'name': _n}
        try:
            pulled = self._unwrap(
                self._post('/api/images/new', {'image': self.image}))
        except (AttributeError, TypeError):
            pulled = {}

        if 'volumeMounts' in pulled:
            pulled['volumeMounts'] = [{'mountPath': x}
                for x in pulled['volumeMounts']]
        if 'ports' in pulled:
            pulled['ports'] = [
                {'containerPort': x.get('number'), 'protocol': x.get('protocol')}
                    for x in pulled['ports']]

        image.update(pulled)
        self.containers.append(image)
        return Image(image)

    @staticmethod
    def _generate_image_name(name, length=10):
        random_sample = ''.join(random.sample(string.digits, length))
        try:
            return name[name.index('/')+1:] + random_sample
        except ValueError:
            return name + random_sample

    def _get_kubes(self):
        """
        Gets user kubes info from backend
        """
        return self._unwrap(self._get('/api/pricing/userpackage'))

    def _clear(self):
        """Deletes pending pod file"""
        os.unlink(self._data_path)

    def _get_free_host(self):
        """
        Gets free IP address from backend ippool
        """
        return self._unwrap(self._get('/api/ippool/getFreeHost'))

    def _delete_container_image(self):
        self.containers = [c for c in self.containers if c['image'] != self.delete]
