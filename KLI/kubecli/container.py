import base64
import datetime
import json
import logging
import operator
import os
import pwd
import random
import string
import yaml

from .image import Image
from .utils import kubeQuery, PrintOut

try:
    from logging import NullHandler
except ImportError:
    from .utils import NullHandler


class Container(kubeQuery, PrintOut, object):
    """
    Class for creating JSON structure for passing to KuberDock API
    """
    KUBEDIR = '.kube_containers'    #default directory for storing container configs
    LISTFILE = 'kubelist.json'      #filename to keep list of containers

    def __init__(self, **kw):
        """
        Constructor.
        """
        log = logging.getLogger(__name__)
        log.addHandler(NullHandler())
        
        self.containers = []
        self.volumes = []
        self.in_json = True

        self._kube_path = self._resolve_directory()
        self._preprocess(kw)

        for key, value in kw.items():
            setattr(self, key, value)

    def _preprocess(self, kw):
        """
        Applies previously set values before attributes
        """
        if kw.get('action') == 'set':
            self._get_container(kw.get('name', 'Unnamed 1'))

    def set_container(self):
        if hasattr(self, 'image'):
            i = self.get_image()
            for attr in 'container_port', 'host_port', 'protocol':
                try:
                    operator.methodcaller(
                        'set_' + attr, getattr(self, attr), self.port_index)(i)
                except AttributeError:
                    continue

        if self.run:
            data = self._prepare()
            try:
                res = self.post('/api/pods/', json.dumps(data), True)
                if 'status' in res:
                    if self.json:
                        print json.dumps(res['status'])
                    else:
                        print res['status']
                else:
                    print res
            except (TypeError, ValueError):
                pass
        self.save()

    def _get_container(self, name):
        """
        Encodes name as base64-urlsafe string and searches file with that name
        and extension '.kube'. If found return its contents as dict otherwise
        returns empty dict with the only name key
        """
        encoded_name = base64.urlsafe_b64encode(name) + '.kube'
        self._data_path = os.path.join(self._kube_path, encoded_name)
        try:
            with open(self._data_path) as data:
                for attr, val in json.load(data).items():
                    setattr(self, attr, val)
        except (IOError, ValueError): # no file, no JSON
            pass

    def _resolve_directory(self):
        """
        Container configs are kept in a user homedir. Get the path to it
        """
        uid = os.geteuid()
        homedir = pwd.getpwuid(uid).pw_dir
        return os.path.join(homedir, self.KUBEDIR)

    def _get_image(self):
        """
        Return image data from a previously saved image or create a new one
        and populate it with pulled data
        :param name: image name, i.e fedora/apache -- string
        """
        for item in self.containers:
            if item['image'] == self.image:
                return item     # return once configured image

        _n = self._generate_image_name(self.image)    # new image
        new_image = {'image': self.image, 'name': _n}
        try:
            pulled_data = self.post('/api/images/new', {'image': self.image})['data']
        except (AttributeError, TypeError):
            pulled_data = {}

        if 'volumeMounts' in pulled_data:
            pulled_data['volumeMounts'] = map(
                (lambda x: {'mountPath': x}), pulled_data['volumeMounts'])
        if 'ports' in pulled_data:
            pulled_data['ports'] = map(
                (lambda x: {'containerPort': int(x)}), pulled_data['ports'])
        new_image.update(pulled_data)
        self.containers.append(new_image)
        return new_image

    def get_image(self):
        """
        Return image wrapped with object
        :param name: image name, i.e fedora/apache -- string:param name:
        """
        item = self._get_image()
        return Image(item)

    @staticmethod
    def _generate_image_name(name, length=10):
        random_sample = ''.join(random.sample(string.digits, length))
        try:
            return name[name.index('/')+1:] + random_sample
        except ValueError:
            return name + random_sample

    def save(self):
        """
        Saves current container as JSON
        """
        if not hasattr(self, '_data_path'):
            raise SystemExit("No data path. No place to save to")

        # Try to create the folder for storing configs.
        try:
            os.mkdir(self._kube_path)
        except OSError, e:
            if e.strerror != 'File exists':
                raise SystemExit(e.strerror)

        with open(self._data_path, 'w') as o:
            json.dump(self._prepare(), o)

    def _prepare(self):
        """
        Filter out unnecessary attributes and make dict from restartPolicy
        """
        valid = set(['name', 'containers', 'volumes', 'service', 'cluster',
                     'replicas', 'set_public_ip', 'save_only', 'restartPolicy'])

        data = dict(filter((lambda x: x[0] in valid), vars(self).items()))

        if type(data['restartPolicy']) is not dict:
            data['restartPolicy'] = {data['restartPolicy']: {}}

        self._filter_out_nameless_volumes(data)
        return data

    @staticmethod
    def _filter_out_nameless_volumes(data):
        """
        Delete from images 'volumeMounts' nameless entries
        """
        for c in data['containers']:
            if c.get('volumeMounts') is None:
                return
            c['volumeMounts'] = filter((lambda x: 'name' in x), c['volumeMounts'])

    def list_containers(self):
        if getattr(self, 'pending', False):
            self._list_pending_containers()
        else:
            self._list_containers()

    def _list_containers(self):
        self.fields = ['name', 'status']
        self.DIVIDER = '>'
        self.out(self._unwrap(self.get('/api/pods/')))

    def _list_pending_containers(self):
        for item in os.listdir(self._kube_path):
            try:
                expansionless_name = item[:item.index('.kube')]
                print base64.urlsafe_b64decode(expansionless_name)
            except ValueError:
                continue
    
    def show_container(self):
        pulled_data = self._unwrap(self.get('/api/pods/'))
        try:
            container = filter((lambda x: x['name'] == self.name), pulled_data)[0]
            if self.json:
                print json.dumps(container)
            else:
                excessive = ['cluster', 'service', 'replicas', 'dockers',
                             'id', 'sid']
                container = dict(filter((lambda item: item[0] not in excessive),
                    container.items()))
                print yaml.safe_dump(container)
        except (IndexError, TypeError):
            if self.json:
                print json.dumps({'status': 'No such container'})
            else:
                print "No such container"
    
    def _pick_container(self):
        try:
            return filter(
                (lambda x: x['name'] == self.name),
                self._pull_containers())[0]
        except IndexError:
            return None
    
    def delete_container(self):
        container = self._pick_container()
        if container is None:
            raise SystemExit("No such container")
        print self.delete('/api/pods/{0}'.format(container['id']))
        
    def _send_command(self, command):
        container = self._pick_container()
        if container is None:
            raise SystemExit("No such container")
        container['command'] = command
        print container
        return self.put('/api/pods/{0}'.format(container['id']), json.dumps(container))
        
    def start_container(self):
        print self._send_command('start')
        
    def stop_container(self):
        print self._send_command('stop')

def main(**kw):
    c = Container(**kw);

    dispatcher = {
        'set': c.set_container,
        'show': c.show_container,
        'list': c.list_containers,
        'delete': c.delete_container,
        'start': c.start_container,
        'stop': c.stop_container}

    dispatcher.get(kw['action'], 'list')()
