import base64
import json
import shlex
from uuid import uuid4
from flask import current_app
from .helpers import KubeQuery, ModelQuery, Utilities

from ..billing import kubes_to_limits
from ..settings import KUBE_API_VERSION, PD_SEPARATOR, KUBERDOCK_INTERNAL_USER, AWS, CEPH

class Pod(KubeQuery, ModelQuery, Utilities):

    def __init__(self, data=None):
        if data is not None:
            for k, v in data.items():
                setattr(self, k, v)

    @staticmethod
    def create(data):
        set_public_ip = data.pop('set_public_ip', None)
        public_ip = data.pop('freeHost', None)
        owner = data.pop('owner', None)
        pod = Pod(data)
        pod._check_pod_name(owner)
        if set_public_ip and public_ip:
            pod.public_ip = public_ip
        pod._make_uuid_if_missing()
        pod.sid = pod._make_sid()
        return pod

    @staticmethod
    def populate(data):
        pod = Pod()
        metadata = data.get('metadata', {})
        status = data.get('status', {})
        spec = data.get('spec', {})
        pod.sid        = metadata.get('name')
        pod.id         = metadata.get('uid')
        pod.name       = metadata.get('labels', {}).get('name')
        pod.namespace  = metadata.get('namespace')
        pod.cluster    = False
        pod.replicas   = 1
        pod.status     = status.get('phase', 'pending').lower()
        pod.podIP      = status.get('podIP', '')
        pod.host       = spec.get('host')
        pod.kube_type  = spec.get('nodeSelector', {}).get('kuberdock-kube-type')
        pod.node       = spec.get('nodeSelector', {}).get('kuberdock-node-hostname')
        pod.volumes    = spec.get('volumes', [])
        pod.labels     = metadata.get('labels')
        pod.containers = spec.get('containers', [])
        pod.dockers    = []

        # TODO refactor this ugly part
        for c in pod.containers:
            try:
                c['imageID'] = [
                    i for i in status.get('containerStatuses', [])
                        if c['name'] == i['name']][0]['imageID']
            except (IndexError, KeyError):
                c['imageID'] = 'docker://'
        if pod.status == 'running':
            for pod_item in status.get('containerStatuses', []):
                if pod_item['name'] == 'POD':
                    continue
                pod.dockers.append({
                    'host': pod.host,
                    'info': pod_item,
                    # 'podIP': pod.podIP
                })
        return pod

    def as_dict(self):
        return dict([(k, v) for k, v in vars(self).items()])

    def as_json(self):
        return json.dumps(self.as_dict())

    def _make_uuid_if_missing(self):
        if hasattr(self, 'id'):
            return
        self.id = str(uuid4())

    def compose_persistent(self, username):
        if not getattr(self, 'volumes', False):
            return
        path = 'pd.sh'
        for volume in self.volumes:
            try:
                pd = volume.pop('persistentDisk')
                name = volume['name']
                device = '{0}{1}{2}'.format(
                    pd.get('pdName'), PD_SEPARATOR, username)
                size = pd.get('pdSize')
                if size is None:
                    array = ['mount', device, name]
                else:
                    array = ['create', device, name, size]
                    if AWS:
                        try:
                            from ..settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
                            array.extend([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY])
                        except ImportError:
                            pass
                fmt = ';'.join(['{{{0}}}'.format(i) for i in range(len(array))])
                params = base64.b64encode(fmt.format(*array))

                volume['scriptableDisk'] = {
                    'pathToScript': path,
                    'params': params
                }
            except KeyError:
                continue

    def prepare(self):
        kube_type = getattr(self, 'kube_type', 0)
        if self.cluster:
            config = {
                "kind": "ReplicationController",
                "apiVersion": "v1beta3",
                "metadata": {
                    "name": self.sid,
                    "namespace": self.namespace,
                    "uid": self.id,
                    "labels": {
                        "name": self.name
                    }
                },
                "spec": {
                    "replicas": 1,
                    "selector": {
                        "name": self.name
                    },
                    "template": {
                        "metadata": {
                            "labels": {
                                "name": self.name
                            }
                        },
                        "spec": {
                            "volumes": getattr(self, 'volumes', []),
                            "containers": [
                                self._prepare_container(c, kube_type)
                                    for c in self.containers],
                            "nodeSelector": {
                                "kuberdock-kube-type": "type_{0}".format(kube_type)
                            },
                        }
                    }
                }
            }
            pod_config = config['spec']['template']
        else:
            config = {
                "kind": "Pod",
                "apiVersion": "v1beta3",
                "metadata": {
                    "name": self.sid,
                    "namespace": self.namespace,
                    "uid": self.id,
                    "labels": {
                        "name": self.name
                    }
                },
                "spec": {
                    "volumes": getattr(self, 'volumes', []),
                    "containers": [
                        self._prepare_container(c, kube_type)
                            for c in self.containers],
                    "restartPolicy": getattr(self, 'restartPolicy', 'Always'),
                    "nodeSelector": {
                        "kuberdock-kube-type": "type_{0}".format(kube_type)
                    },
                }
            }
            pod_config = config
        if hasattr(self, 'node') and self.node:
            pod_config['spec']['nodeSelector']['kuberdock-node-hostname'] = self.node
        if hasattr(self, 'public_ip'):
            pod_config['metadata']['labels']['kuberdock-public-ip'] = self.public_ip
        return config


    #def prepare(self, sid=None):
    #    if not self.cluster:
    #        return self._prepare_pod()
    #    sid = self._make_sid()
    #    return {
    #        'kind': 'ReplicationController',
    #        'apiVersion': KUBE_API_VERSION,
    #        'id': sid,
    #        'desiredState': {
    #            'replicas': self.replicas,
    #            'replicaSelector': {'name': self.name},
    #            'podTemplate': self._prepare_pod(sid=sid, separate=False),
    #        },
    #        'labels': {'name': self._make_dash() + '-cluster'}}
    #
    #def _prepare_pod(self, sid=None, separate=True):
    #    # separate=True means that this is just a pod, not replica
    #    # to insert config into replicas config set separate to False
    #    if sid is None:
    #        sid = self._make_sid()
    #    inner = {'version': 'v1beta3'}
    #    if separate:
    #        inner['id'] = sid
    #        inner['restartPolicy'] = getattr(self, 'restartPolicy', {'always': {}})
    #    inner['volumes'] = getattr(self, 'volumes', [])
    #    kube_type = getattr(self, 'kube_type', 0)
    #    inner['containers'] = [self._prepare_container(c, kube_type) for c in self.containers]
    #    outer = {}
    #    if separate:
    #        outer['kind'] = 'Pod'
    #        outer['apiVersion'] = KUBE_API_VERSION
    #        outer['id'] = sid
    #        outer['nodeSelector'] = {'kuberdock-kube-type': 'type_' + str(kube_type)}
    #    outer['desiredState'] = {'manifest': inner}
    #    if not hasattr(self, 'labels'):
    #        outer['labels'] = {'name': self.name}
    #        if hasattr(self, 'public_ip'):
    #            outer['labels']['kuberdock-public-ip'] = self.public_ip
    #    else:
    #        outer['labels'] = self.labels
    #    return outer

    def _prepare_container(self, data, kube_type=0):
        if not data.get('name'):
            data['name'] = self._make_name_from_image(data.get('image', ''))

        try:
            kubes = int(data.pop('kubes'))
        except (KeyError, ValueError):
            pass
        else:   # if we create pod, not start stopped
            data.update(kubes_to_limits(kubes, kube_type))

        wd = data.get('workingDir', '.')
        if type(wd) is list:
            data['workingDir'] = ','.join(data['workingDir'])

        if data['command']:
            data['command'] = self._parse_cmd_string(data['command'][0])
        if self.owner != KUBERDOCK_INTERNAL_USER:
            for p in data.get('ports', []):
                p.pop('hostPort', None)
        return data

    def _parse_cmd_string(self, cmd_string):
        lex = shlex.shlex(cmd_string, posix=True)
        lex.whitespace_split = True
        lex.commenters = ''
        lex.wordchars += '.'
        try:
            return list(lex)
        except ValueError:
            self._raise('Incorrect cmd string')

    @property
    def kind(self):
        if getattr(self, 'cluster', False):
            return 'replicationcontrollers'
        else:
            return 'pods'

    def __repr__(self):
        return "<Pod ('name':{0})>".format(self.name)