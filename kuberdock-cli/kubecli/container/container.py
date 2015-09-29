import base64
#import datetime
import json
#import logging
import operator
import os
import pwd
import random
import re
import string
import subprocess
import warnings

from ..image.image import Image
from ..helper import KubeQuery, PrintOut
from ..api_common import (PODAPI_PATH, AUTH_TOKEN_PATH, PSTORAGE_PATH,
    IMAGES_PATH, PRICING_PATH, POD_CREATE_API_PATH)


# Some common error messages
ERR_NO_SUCH_ITEM = "No such item"
ERR_INVALID_KUBE_TYPE = "Valid kube type must be set. "\
                        "Run 'kuberdock kubes' to get available kube types"
ERR_SPECIFY_IMAGE_OPTION = "You must specify an image with option "\
                           "'-C|--container'"

class KubeCtl(object):
    """
    Class for managing KuberDock entities
    """

    def __init__(self, **args):
        """
        Constructor
        """
        self._args = args
        self.as_json = args.get('json', False)
        self.query = KubeQuery(jsonify_errors=self.as_json, **args)
        for key, val in args.iteritems():
            setattr(self, key, val)

    def _get_pod(self):
        data = self.query.unwrap(self.query.get(PODAPI_PATH))
        with warnings.catch_warnings(): # Restore default behaviour on __exit__
            # make warnings to raise the exception
            warnings.simplefilter('error', UnicodeWarning)
            for i in data:
                try:
                    if i['name'] == self.name:
                        return i
                except UnicodeWarning:
                    if i['name'].encode('UTF-8') == self.name:
                        return i

    def get(self):
        """
        Gets a list of user pods and prints either all or one
        """
        printout = PrintOut(
            wants_header=True,
            fields=(('name', 32), ('images', 32),
                    ('labels', 64), ('status', 10)),
            as_json=self.as_json)
        data = self.query.unwrap(self.query.get(PODAPI_PATH))
        if hasattr(self, 'name'):
            printout.show_list([self._transform(i) for i in data if i['name'] == self.name])
        else:
            printout.show_list([self._transform(i) for i in data])

    def describe(self):
        """
        Gets a list of user pods, filter out one of them by name and prints it
        """
        pod = self._get_pod()
        if pod:
            printout = PrintOut(as_json=self.as_json)
            printout.show(pod)
        else:
            raise SystemExit(ERR_NO_SUCH_ITEM)

    def delete(self):
        """
        Gets a list of user pods, filter out one of them by name and deletes it.
        """
        data = self.query.unwrap(self.query.get(PODAPI_PATH))
        try:
            item = [i for i in data if i['name'] == self.name][0]
            self.query.delete(PODAPI_PATH + item['id'])
        except (IndexError, KeyError):
            raise SystemExit(ERR_NO_SUCH_ITEM)
        self._set_delayed()

    def create(self):
        """Creates user pod by yaml specification."""
        yaml_content = self.filename.read()
        if not yaml_content:
            raise SystemExit('Empty file content')
        # API expects yaml file as a string in json structure:
        # {"data": yaml_as_a_string}
        answer = self.query.post(POD_CREATE_API_PATH, {'data': yaml_content})
        if answer and answer.get('status', None) != 'OK':
            raise SystemExit('Failed To create pod: {}'.format(str(answer)))

    def postprocess(self):
        if os.geteuid() != 0:
            raise SystemExit('The postprocess expects superuser privileges')
        if not hasattr(self, 'uid'):
            raise SystemExit('User UID is expected')

        data = self.query.unwrap(self.query.get(PODAPI_PATH))
        pod = [i for i in data if i['name'] == self.name]
        if pod:
            service_ip = pod[0].get('podIP')
            if service_ip is None:
                return
            params = ['/sbin/iptables', '-t', 'nat', '-C', 'OUTPUT', '-d', service_ip,
                      '-m', 'owner', '!', '--uid-owner', self.uid, '-j', 'DNAT',
                      '--to-destination', '233.252.0.254']
            try:
                subprocess.check_call(params, stdout=open('/dev/null', 'a'),
                                      stderr=open('/dev/null', 'a'))
            except subprocess.CalledProcessError:
                params[3] = '-I'
                subprocess.call(params, stdout=open('/dev/null', 'a'),
                                stderr=open('/dev/null', 'a'))
        else:
            existing_ips = [i['podIP'] for i in data if 'podIP' in i]
            params = ['/sbin/iptables', '-t', 'nat', '-L', 'OUTPUT', '-n',
                      '--line-numbers']
            rv = subprocess.Popen(params, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
            o, e = rv.communicate()
            rules = o.splitlines()
            patt = re.compile(r'!\sowner\sUID\smatch\s(?P<uid>\d+)')
            for i in reversed(rules[2:]):
                fields = i.split(None, 6)
                m = patt.match(fields[6])
                if m is None:
                    continue
                if m.group('uid') != self.uid:
                    continue
                if fields[5] not in existing_ips:
                    params = ['/sbin/iptables', '-t', 'nat', '-D', 'OUTPUT',
                              fields[0]]
                    try:
                        subprocess.check_call(params,
                                              stdout=open('/dev/null', 'a'),
                                              stderr=open('/dev/null', 'a'))
                    except subprocess.CalledProcessError:
                        print "Could not delete rule for uid {0} ({1})".format(
                            self.uid, fields[5])

    @staticmethod
    def _transform(data):
        """ Converts json data of a pod to dict with fields "name", "status",
        "labels", "images".
        We expect here a dict with fields:
            {
              "name": name of the pod,
              "status": status of the pod,
              "labels": dict for some labels, for example {"name": "mypod"},
              "containers": list of containers in the pod, each container is
                 a dict, here we're extracting only "image" field - name
                 of image in the container
            }
        Name and status will be returned as is, labels will be joined to
        one string. Image names of container also will be joined to one string.

        """
        ready = ['name', 'status']
        out = {k: data.get(k, '???') for k in ready}
        out['labels'] = u','.join(
            [u'{0}={1}'.format(k, v)
             for k, v in data.get('labels', {}).iteritems()]
        )
        out['images'] = u','.join(
            [i.get('image', 'imageless') for i in data.get('containers', [])]
        )
        return out

    def _set_delayed(self):
        """Delayed change of iptables rules (postprocess method).
        After deleting/creation of pod we should change iptables rules, but
        we don't know if the operation actually have been performed. So, wait
        for 2 minutes and call postprocess method as superuser (via suid
        binary 'suidwrap').

        """
        data = self.query.get(AUTH_TOKEN_PATH)
        try:
            fmt = """echo /usr/libexec/suidwrap '"{0}"' {1} |at now + 2 minute > /dev/null 2>&1"""
            subprocess.check_call([fmt.format(data['token'], self.name)], shell=True)
        except (KeyError, TypeError, subprocess.CalledProcessError):
            return


class KuberDock(KubeCtl):
    """
    Class for creating KuberDock entities
    """
    KUBEDIR = '.kube_containers'    #default directory for storing container configs
    EXT = '.kube'

    def __init__(self, **args):
        """Creates empty parameters for container configuration.
        TODO: separate field sets of cli parameters and container configuration
        """
        # First we need to load possibly saved configuration for a new pod
        # and only after loading apply data
        self.containers = []
        self.volumes = []
        # Container configs path
        self._kube_path = None
        # pending container path
        self._data_path = None
        self._load(args)
        super(KuberDock, self).__init__(**args)

    def create(self):
        self.set()

    def set(self):
        """Creates or updates temporary pod configuration on the local host"""
        if hasattr(self, 'image'):
            i = self._get_image()
            i.data['kubes'] = int(self.kubes)

        if self.delete is None:
            self._save()
        else:
            self._delete_container_image()
            self._save()

    def save(self):
        """
        Sends POST request to KuberDock to save configured container
        """
        data = self._prepare(final=True)
        kubes = self._get_kubes()
        try:
            data['kube_type'] = int(kubes[data['kube_type']])
        except (KeyError, ValueError, TypeError):
            raise SystemExit(ERR_INVALID_KUBE_TYPE)
        try:
            res = self.query.post(PODAPI_PATH, json.dumps(data), True)
            if res.get('status') != 'error':
                self._clear()
            else:
                raise SystemExit(str(res))
        except TypeError, e:
            raise SystemExit(str(e))

    def list(self):
        """
        Lists all pending pods
        """
        names = []
        printout = PrintOut(as_json=self.as_json)
        try:
            for f in os.listdir(self._kube_path):
                if not f.endswith(self.EXT):
                    continue
                names.append(f[:f.index(self.EXT)])
            printout.show_list([{'name': base64.b64decode(i)} for i in names])
        except OSError:
            pass

    def kubes(self):
        """
        Returns list of user kubes
        """
        printout = PrintOut(wants_header=True,
                            fields=(('id', 12), ('name', 32)),
                            as_json=self.as_json)
        data = self._get_kubes()
        printout.show_list([{'name': k, 'id': v} for k, v in data.iteritems()])

    def drives(self):
        """
        Persistent drives related actions
        """
        {'list': self.list_drives,
         'add': self.add_drive,
         'delete': self.delete_drive}.get(self.pdaction, self.list_drives)()

    def list_drives(self):
        """
        Returns list of user persistent drives
        """
        printout = PrintOut(
            wants_header=True,
            fields=(('id', 48), ('name', 32), ('size', 12), ('in_use', 12)),
            as_json=self.as_json
        )
        printout.show_list(self._get_drives())

    def add_drive(self):
        """
        Creates a persistent drive for a user
        """
        self.query.post(PSTORAGE_PATH, {'name': self.name, 'size': self.size})

    def delete_drive(self):
        """
        Deletes a user persistent drive
        """
        drives = self._get_drives()
        filtered = [d for d in drives if d.get('name') == self.name]
        if not filtered:
            raise SystemExit('No such drive')
        self.query.delete(PSTORAGE_PATH + filtered[0]['id'])

    def start(self):
        """Starts a pod with specified name"""
        printout = PrintOut(
            fields=(('status', 32),),
            as_json=self.as_json
        )
        pod = self._get_pod()
        if not pod:
            raise SystemExit('Pod "{}" not found'.format(self.name))
        command = {}
        if pod['status'] == 'stopped':
            # Is this correct? In previous version was pod['command'] = 'stop',
            # But API for start/stop takes only 'command' parameter from request
            # body
            command['command'] = 'start'
        res = self.query.unwrap(self.query.put(PODAPI_PATH + pod['id'],
                                              json.dumps(command)))
        printout.show(res)
        self._set_delayed()

    def stop(self):
        """Stops a pod with specified name"""
        printout = PrintOut(
            fields=(('status', 32),),
            as_json=self.as_json
        )
        pod = self._get_pod()
        command = {}
        if pod['status'] in ['running', 'pending']:
            command['command'] = 'stop'
        res = self.query.unwrap(self.query.put(PODAPI_PATH + pod['id'],
                                          json.dumps(command)))
        printout.show_list(res)

    def forget(self):
        """
        Deletes one or all pending containers
        """
        if self.name:
            return self._forget_one()
        return self._forget_all()

    def search(self):
        """Searches for images with specified name. Optionally there may be
        defined url for a registry where the search should be performed.
        """
        image = Image(vars(self), **self._args)
        image.search()

    def image_info(self):
        """Prints out information about image specified in 'image' parameter"""
        image = Image(vars(self), **self._args)
        image.get()

    def describe(self):
        """Describes pending pod."""
        if not os.path.exists(self._data_path):
            raise SystemExit(ERR_NO_SUCH_ITEM)
        printout = PrintOut(as_json=self.as_json, fields=None)
        data = self._prepare()
        printout.show(data)

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
        if self._data_path is None:
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

    def _prepare(self, final=False):
        valid = set([
            'name', 'containers', 'volumes', 'service', 'replicationController',
            'replicas', 'set_public_ip', 'kube_type', 'restartPolicy',
            'public_ip'
        ])
        self.replicationController = True
        self._prepare_volumes(final)
        self._prepare_ports()
        self._prepare_env()
        data = {key: value for key, value in vars(self).iteritems()
                if key in valid}

        return data

    def _prepare_volumes(self, final=False):
        """
        Makes names for volumeMount entries and populate 'volumes' with them
        Prepares 'volumeMounts' fields in items of self.containers list,
        also prepares self.volumes list.
        """
        for c in self.containers:
            if c.get('volumeMounts') is None:
                c['volumeMounts'] = []
                continue

            if final:   # We cannot send volumeMount if has no match in volumes
                c['volumeMounts'] = [v for v in c['volumeMounts']
                                    if v.get('mountPath') and v.get('name')]
                continue

            c['volumeMounts'] = [v for v in c['volumeMounts']
                                if v.get('mountPath')]

            if hasattr(self, 'persistent_drive'):
                if getattr(self, 'image', None) != c['image']:
                    continue

                if not hasattr(self, 'mount_path'):
                    raise SystemExit('"--mount-path" option is expected')

                curr = filter((lambda i: i['name'] == self.persistent_drive),
                              self._get_drives())
                if not curr and not hasattr(self, 'size'):
                    raise SystemExit(
                        'Drive not found. To set a new drive option '
                        '"--size" is expected')

                mount_paths = [i for i in c['volumeMounts']
                               if i['mountPath'] == self.mount_path]
                if mount_paths:
                    mount_path = mount_paths[0]
                else:
                    mount_path = {'mountPath': self.mount_path}
                    c['volumeMounts'].append(mount_path)

                if not mount_path.get('name'):
                    mount_path['name'] = self._generate_image_name(
                        self.mount_path.lstrip('/').replace('/', '-'))

                vols = [v for v in self.volumes
                        if v.get('name') == mount_path['name']]
                if vols:
                    vol = vols[0]
                else:
                    vol = {'name': mount_path['name']}
                    self.volumes.append(vol)
                vol['persistentDisk'] = {
                    'pdName': self.persistent_drive,
                    'pdSize': getattr(self, 'size', None)}


    def _prepare_ports(self):
        """Checks if all necessary port entry data are set"""
        if not hasattr(self, 'container_port'):
            return
        if not hasattr(self, 'image'):
            # 'image' is defined by --container option
            raise SystemExit(ERR_SPECIFY_IMAGE_OPTION)

        # We are expecting here
        # something like +1234:567:tcp
        #                ^is public flag (optional)
        #                 ^container port
        #                      ^host port (optional)
        #                          ^protocol (tcp|udp) (optional)
        patt = re.compile(
            "^(?P<public>\+)?(?P<container_port>\d+)\:?(?P<host_port>\d+)?\:?"\
            "(?P<protocol>tcp|udp)?$"
        )
        ports = []
        is_public_ip = False

        min_port = 1
        max_port = 2**16

        right_format_error_message = \
            "Wrong port format. "\
            "Example: +453:54:udp where '+' is a public IP, "\
            "453 - container port, 54 - pod port, 'udp' - protocol (tcp or udp)"

        for p in getattr(self, 'container_port').strip().split(','):
            m = patt.match(p)
            if m:
                public = bool(m.group('public'))
                container_port = int(m.group('container_port'))
                host_port = m.group('host_port')
                host_port = int(host_port) if host_port else container_port
                protocol = m.group('protocol') if m.group('protocol') else 'tcp'
                if any([container_port < min_port,
                        container_port >= max_port,
                        host_port < min_port,
                        host_port >= max_port,
                        protocol not in ('tcp', 'udp')]):
                    raise SystemExit(right_format_error_message)

                if public:
                    is_public_ip = True
                ports.append({
                    'isPublic': public,
                    'containerPort': container_port,
                    'hostPort': host_port,
                    'protocol': protocol,
                })
            else:
                raise SystemExit(right_format_error_message)

        for c in self.containers:
            if c['image'] != self.image:
                continue
            c['ports'] = ports

        self.set_public_ip = is_public_ip

    def _prepare_env(self):
        """
        Add container environment variables
        """
        if not hasattr(self, 'env'):
            return
        if not hasattr(self, 'image'):
            raise SystemExit(ERR_SPECIFY_IMAGE_OPTION)
        for c in self.containers:
            if c['image'] != self.image:
                continue
            if 'env' not in c:
                c['env'] = []
            existing = {item['name'] for item in c['env']}
            data_to_add = [dict(zip(['name', 'value'], item.strip().split(':')))
                        for item in self.env.strip().split(',')
                        if len(item.split(':')) == 2]
            for i in c['env']:
                for j in data_to_add:
                    if i['name'] == j['name']:
                        i['value'] = j['value']
                        break
            c['env'].extend(filter((lambda x: x['name'] not in existing), data_to_add))

    def _resolve_containers_directory(self):
        """
        Container configs are kept in a user homedir. Get the path to it
        """
        if self._kube_path is not None:
            return
        uid = os.geteuid()
        homedir = pwd.getpwuid(uid).pw_dir
        self._kube_path = os.path.join(homedir, self.KUBEDIR)

    def _resolve_data_path(self, name):
        """
        Get the path of a pending container config
        :param name: string -> name of pening pod
        """
        if self._data_path is not None:
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
                return Image(item, **self._args)   # return once configured image

        _n = self._generate_image_name(self.image)    # new image
        image = {'image': self.image, 'name': _n}
        try:
            pulled = self.query.unwrap(
                self.query.post(IMAGES_PATH + 'new', {'image': self.image}))
        except (AttributeError, TypeError):
            pulled = {}

        if 'volumeMounts' in pulled:
            pulled['volumeMounts'] = [{'mountPath': x}
                for x in pulled['volumeMounts']]
        if 'ports' in pulled:
            pulled['ports'] = [
                {
                    'isPublic': False,
                    'containerPort': x.get('number'),
                    'hostPort': x.get('number'),
                    'protocol': x.get('protocol')
                } for x in pulled['ports']
            ]
        image.update(pulled)
        self.containers.append(image)
        return Image(image, **self._args)

    @staticmethod
    def _generate_image_name(name, length=10):
        random_sample = ''.join(random.sample(string.digits, length))
        try:
            return name[name.index('/') + 1:] + random_sample
        except ValueError:
            return name + random_sample

    def _get_kubes(self):
        """
        Gets user kubes info from backend
        """
        return self.query.unwrap(self.query.get(PRICING_PATH + 'userpackage'))

    def _get_drives(self):
        """
        Gets user drives info from backend
        """
        return self.query.unwrap(self.query.get(PSTORAGE_PATH))

    def _clear(self):
        """Deletes pending pod file"""
        os.unlink(self._data_path)

    def _delete_container_image(self):
        self.containers = [c for c in self.containers if c['image'] != self.delete]
