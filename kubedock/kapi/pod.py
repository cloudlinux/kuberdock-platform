import base64
import json
from uuid import uuid4
from flask import current_app
from .helpers import KubeQuery, ModelQuery, Utilities

from ..billing import kubes_to_limits
from ..settings import KUBE_API_VERSION, PD_SEPARATOR

class Pod(KubeQuery, ModelQuery, Utilities):

    def __init__(self, data=None):
        if data is not None:
            for k, v in data.items():
                setattr(self, k, v)

    @staticmethod
    def create(data, owner):
        set_public_ip = data.pop('set_public_ip', None)
        public_ip = data.pop('freeHost', None)
        pod = Pod(data)
        pod._check_pod_name()
        pod.owner = owner
        if set_public_ip and public_ip:
            pod.public_ip = public_ip
        pod._make_uuid_if_missing()
        pod._check_container_commands()
        pod._compose_persistent()
        return pod

    @staticmethod
    def populate(data):
        pod = Pod()
        manifest = data.get('desiredState', {}).get('manifest', {})
        curstate = data.get('currentState', {})
        info = curstate.get('info', {})

        pod.id         = data.get('uid')
        pod.name       = data.get('labels', {}).get('name')
        pod.namespace  = data.get('namespace', 'default')
        pod.sid        = data.get('id')
        pod.cluster    = False
        pod.replicas   = 1
        pod.status     = curstate.get('status', 'unknown').lower()
        pod.volumes    = manifest.get('volumes', [])
        pod.labels     = data.get('labels')
        pod.containers = manifest.get('containers', [])
        pod.dockers    = []

        for c in pod.containers:
            c['imageID'] = info.get(c['name'], {}).get('imageID')

        if pod.status == 'running':
            for pod_name, pod_info in info.items():
                if pod_name == 'POD':
                    continue
                pod.dockers.append({
                    'host': curstate.get('host'),
                    'info': pod_info,
                    'podIP': curstate.get('podIP', '')})
        return pod

    def as_dict(self):
        return dict([(k, v) for k, v in vars(self).items()])

    def as_json(self):
        return json.dumps(self.as_dict())

    def save(self):
        # we should think twice what to do with that owner
        data = dict([(k, v) for k, v in vars(self).items() if k != 'owner'])
        self._save_pod(data, self.owner)
        data.update({'owner': self.owner.username})
        return data

    def _make_uuid_if_missing(self):
        if hasattr(self, 'id'):
            return
        self.id = str(uuid4())

    def _check_container_commands(self):
        for c in getattr(self, 'containers', []):
            if c.get('command'):
                c['command'] = self._parse_cmd_string(c['command'][0])

    def _compose_persistent(self):
        if not getattr(self, 'volumes', False):
            return
        path = 'pd.sh'
        for volume in self.volumes:
            try:
                pd = volume['source']['persistentDisk']
                name = '{0}{1}{2}'.format(
                    pd.get('pdName'), PD_SEPARATOR, self.owner.username)
                size = pd.get('pdSize')
                if size is None:
                    params = base64.b64encode("{0};{1}".format('mount', name))
                else:
                    params = base64.b64encode("{0};{1};{2}".format('create', name, size))
                volume['source'] = {'scriptableDisk': {
                    'pathToScript': path, 'params': params}}
            except KeyError:
                continue

    def prepare(self, sid=None):
        if not self.cluster:
            return self._prepare_pod()
        sid = self._make_sid()
        return {
            'kind': 'ReplicationController',
            'apiVersion': KUBE_API_VERSION,
            'id': sid,
            'desiredState': {
                'replicas': self.replicas,
                'replicaSelector': {'name': self.name},
                'podTemplate': self._prepare_pod(sid=sid, separate=False),
            },
            'labels': {'name': self._make_dash() + '-cluster'}}

    def _prepare_pod(self, sid=None, separate=True):
        # separate=True means that this is just a pod, not replica
        # to insert config into replicas config set separate to False
        if sid is None:
            sid = self._make_sid()
        inner = {'version': KUBE_API_VERSION}
        if separate:
            inner['id'] = sid
            inner['restartPolicy'] = getattr(self, 'restartPolicy', {'always': {}})
        inner['volumes'] = getattr(self, 'volumes', [])
        kube_type = getattr(self, 'kube_type', 0)
        inner['containers'] = [self._prepare_container(c, kube_type) for c in self.containers]
        outer = {}
        if separate:
            outer['kind'] = 'Pod'
            outer['apiVersion'] = KUBE_API_VERSION
            outer['id'] = sid
            outer['nodeSelector'] = {'kuberdock-kube-type': 'type_' + str(kube_type)}
        outer['desiredState'] = {'manifest': inner}
        if not hasattr(self, 'labels'):
            outer['labels'] = {'name': self.name}
            if hasattr(self, 'public_ip'):
                outer['labels']['kuberdock-public-ip'] = self.public_ip
        else:
            outer['labels'] = self.labels
        return outer

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
        return data

    def __repr__(self):
        return "<Pod ('name':{0})>".format(self.name)