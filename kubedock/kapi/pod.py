import json
import os
import shlex
from uuid import uuid4
from copy import deepcopy
from flask import current_app
from .helpers import KubeQuery, ModelQuery, Utilities

from .pstorage import CephStorage, AmazonStorage
from ..billing import kubes_to_limits
from ..billing.models import Kube
from ..settings import KUBE_API_VERSION, KUBERDOCK_INTERNAL_USER, \
                        AWS, CEPH, NODE_LOCAL_STORAGE_PREFIX
from ..utils import POD_STATUSES
from ..pods.models import PersistentDisk


class Pod(KubeQuery, ModelQuery, Utilities):
    def __init__(self, data=None):
        if data is not None:
            for c in data['containers']:

                # At least one kube per container expected so we can make it
                # defaults to 1 if not set
                if 'kubes' not in c:
                    c['kubes'] = 1

                if len(c.get('args', [])) == 1:
                    # it seems the args has been changed
                    # or may be its length is only 1 item
                    c['args'] = self._parse_cmd_string(c['args'][0])
            for k, v in data.items():
                setattr(self, k, v)

    @staticmethod
    def create(data):
        data = data.copy()
        owner = data.pop('owner', None)
        # TODO delete this because 'owner' will appear in api response
        data['owner'] = None if owner is None else owner.username
        data.setdefault('status', POD_STATUSES.stopped)
        pod = Pod(data)
        pod._check_pod_name(owner)
        pod._make_uuid_if_missing()
        pod.sid = str(uuid4())
        return pod

    @staticmethod
    def populate(data):
        """
        Create Pod object using Pod from Kubernetes
        """
        pod = Pod()
        metadata = data.get('metadata', {})
        status = data.get('status', {})
        spec = data.get('spec', {})

        pod.sid = metadata.get('name')
        pod.namespace = metadata.get('namespace')
        pod.labels = metadata.get('labels', {})
        pod.id = pod.labels.get('kuberdock-pod-uid')

        pod.status = status.get('phase', POD_STATUSES.pending).lower()

        pod.host = spec.get('nodeName')
        pod.kube_type = spec.get('nodeSelector', {}).get('kuberdock-kube-type')
        pod.node = spec.get('nodeSelector', {}).get('kuberdock-node-hostname')
        pod.volumes = spec.get('volumes', [])
        pod.containers = spec.get('containers', [])
        pod.restartPolicy = spec.get('restartPolicy')

        if pod.status in (POD_STATUSES.running, POD_STATUSES.succeeded,
                          POD_STATUSES.failed):
            for pod_item in status.get('containerStatuses', []):
                if pod_item['name'] == 'POD':
                    continue
                for container in pod.containers:
                    if container['name'] == pod_item['name']:
                        state, stateDetails = pod_item.pop('state').items()[0]
                        pod_item['state'] = state
                        pod_item['startedAt'] = stateDetails.get('startedAt')
                        if state == 'terminated':
                            pod_item['exitCode'] = stateDetails.get('exitCode')
                            pod_item['finishedAt'] = stateDetails.get('finishedAt')
                        container_id = pod_item.get('containerID', container['name'])
                        pod_item['containerID'] = _del_docker_prefix(container_id)
                        image_id = pod_item.get('imageID', container['image'])
                        pod_item['imageID'] = _del_docker_prefix(image_id)
                        container.update(pod_item)
        else:
            pod._forge_dockers(status=pod.status)
        return pod

    def as_dict(self):
        data = vars(self).copy()
        for field in ('namespace', 'secrets'):
            data.pop(field, None)
        data['volumes'] = data.pop('volumes_original', [])
        return data

    def as_json(self):
        return json.dumps(self.as_dict())

    def _make_uuid_if_missing(self):
        if hasattr(self, 'id'):
            return
        self.id = str(uuid4())

    def compose_persistent(self, owner):
        if not getattr(self, 'volumes', False):
            return
        self.volumes_original = deepcopy(self.volumes)
        for volume in self.volumes:
            if 'persistentDisk' in volume:
                self._handle_persistent_storage(volume, owner)
            elif 'localStorage' in volume:
                self._handle_local_storage(volume)

    @staticmethod
    def _handle_persistent_storage(volume, owner):
        pd = volume.pop('persistentDisk')
        name = pd.get('pdName')

        persistent_disk = PersistentDisk.filter_by(owner_id=owner.id,
                                                   name=name).first()
        if persistent_disk is None:
            persistent_disk = PersistentDisk(name=name, owner_id=owner.id,
                                             size=pd.get('pdSize', 1)).save()

        if CEPH:
            volume['rbd'] = {
                'image': persistent_disk.drive_name,
                'keyring': '/etc/ceph/ceph.client.admin.keyring',
                'fsType': 'xfs',
                'user': 'admin',
                'pool': 'rbd',
                'size': persistent_disk.size,
                'monitors': CephStorage().get_monitors(),
            }
        elif AWS:
            try:
                from ..settings import AVAILABILITY_ZONE
            except ImportError:
                return
            # volumeID: aws://<availability-zone>/<volume-id>
            volume['awsElasticBlockStore'] = {
                'volumeID': 'aws://{0}/'.format(AVAILABILITY_ZONE),
                'fsType': 'xfs',
                'drive': persistent_disk.drive_name,
                'size': persistent_disk.size,
            }

    def _handle_local_storage(self, volume):
        local_storage = volume.pop('localStorage')
        if not local_storage:
            return
        if isinstance(local_storage, dict) and 'path' in local_storage:
            path = local_storage['path']
        else:
            path = os.path.join(NODE_LOCAL_STORAGE_PREFIX, self.id, volume['name'])
        volume['hostPath'] = {'path': path}

    def prepare(self):
        kube_type = getattr(self, 'kube_type', Kube.get_default_kube_type())
        volumes = getattr(self, 'volumes', [])
        secrets = getattr(self, 'secrets', [])

        config = {
            "kind": "ReplicationController",
            "apiVersion": KUBE_API_VERSION,
            "metadata": {
                "name": self.sid,
                "namespace": self.namespace,
                "labels": {
                    "kuberdock-pod-uid": self.id
                }
            },
            "spec": {
                "replicas": getattr(self, 'replicas', 1),
                "selector": {
                    "kuberdock-pod-uid": self.id
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "kuberdock-pod-uid": self.id
                        }
                    },
                    "spec": {
                        "volumes": volumes,
                        "containers": [self._prepare_container(c, kube_type, volumes)
                                       for c in self.containers],
                        "restartPolicy": getattr(self, 'restartPolicy', 'Always'),
                        "imagePullSecrets": [{"name": secret}
                                             for secret in secrets]
                    }
                }
            }
        }
        pod_config = config['spec']['template']

        # Internal services may run on any nodes, do not care of kube type of
        # the node. All other kube types must be binded to the appropriate nodes
        if Kube.is_node_attachable_type(kube_type):
            pod_config['spec']['nodeSelector'] = {
                "kuberdock-kube-type": "type_{0}".format(kube_type)
            }
        else:
            pod_config['spec']['nodeSelector'] = {}
        if hasattr(self, 'node') and self.node:
            pod_config['spec']['nodeSelector']['kuberdock-node-hostname'] = self.node
        if hasattr(self, 'public_ip'):
            pod_config['metadata']['labels']['kuberdock-public-ip'] = self.public_ip
        return config

    def _update_volume_path(self, name, vid):
        if vid is None:
            return
        for vol in getattr(self, 'volumes', []):
            if vol.get('name') != name:
                continue
            try:
                vol['awsElasticBlockStore']['volumeID'] += vid
            except KeyError:
                continue

    def _prepare_container(self, data, kube_type=None, volumes=None):
        # Strip non-kubernetes params
        data.pop('sourceUrl', None)

        if kube_type is None:
            kube_type = Kube.get_default_kube_type()

        if not data.get('name'):
            data['name'] = self._make_name_from_image(data.get('image', ''))

        if volumes is None:
            volumes = []

        try:
            kubes = int(data.pop('kubes'))
        except (KeyError, ValueError):
            pass
        else:   # if we create pod, not start stopped
            data.update(kubes_to_limits(kubes, kube_type))

        wd = data.get('workingDir', '.')
        if type(wd) is list:
            data['workingDir'] = ','.join(data['workingDir'])

        for p in data.get('ports', []):
            p['protocol'] = p.get('protocol', 'TCP').upper()
            p.pop('isPublic', None)     # Non-kubernetes param

        if self.owner != KUBERDOCK_INTERNAL_USER:
            for p in data.get('ports', []):
                p.pop('hostPort', None)

        if self._has_rbd(data.get('volumeMounts', []), volumes):
            data['securityContext'] = {'privileged': True}

        data['imagePullPolicy'] = 'Always'
        return data

    @staticmethod
    def _has_rbd(volume_mounts, volumes):
        """
        Returns true if one of volumeMounts has a correspondent one in
        volumes of type 'rbd'
        :param volume_mounts: list -> list of mount dicts
        :param volumes: list -> list of volume dicts
        :return: bool
        """
        return any([[i for i in
                   [v for v in volumes if v.get('name') == vm.get('name')]
                   if 'rbd' in i] for vm in volume_mounts])

    def _parse_cmd_string(self, cmd_string):
        lex = shlex.shlex(cmd_string, posix=True)
        lex.whitespace_split = True
        lex.commenters = ''
        lex.wordchars += '.'
        try:
            return list(lex)
        except ValueError:
            self._raise('Incorrect cmd string')

    def _forge_dockers(self, status='stopped'):
        for container in self.containers:
            container.update({
                'containerID': container['name'],
                'imageID': container['image'],
                'lastState': {},
                'ready': False,
                'restartCount': 0,
                'state': status,
                'startedAt': None,
            })

    def __repr__(self):
        name = getattr(self, 'name', '').encode('ascii', 'replace')
        return "<Pod ('id':{0}, 'name':{1})>".format(self.id, name)


def _del_docker_prefix(value):
    """Removes 'docker://' from container or image id returned from kubernetes
    API.

    """
    if not value:
        return value
    return value.split('docker://')[-1]
