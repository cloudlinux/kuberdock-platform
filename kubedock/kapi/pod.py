import json
import os
import shlex
from copy import deepcopy
from uuid import uuid4

from .helpers import KubeQuery, ModelQuery, Utilities, APIError
from .images import Image
from .pstorage import get_storage_class
from ..billing import kubes_to_limits
from ..billing.models import Kube
from ..pods.models import db, PersistentDisk, Pod as DBPod
from ..settings import KUBE_API_VERSION, KUBERDOCK_INTERNAL_USER, \
    NODE_LOCAL_STORAGE_PREFIX
from ..users.models import User
from ..utils import POD_STATUSES

ORIGIN_ROOT = 'originroot'
OVERLAY_PATH = u'/var/lib/docker/overlay/{}/root'


class Pod(KubeQuery, ModelQuery, Utilities):
    def __init__(self, data=None):
        if data is not None:
            for c in data['containers']:
                if len(c.get('args', [])) == 1:
                    # it seems the args has been changed
                    # or may be its length is only 1 item
                    c['args'] = self._parse_cmd_string(c['args'][0])
            for k, v in data.items():
                setattr(self, k, v)

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
            container_statuses = status.get('containerStatuses', [])
            if container_statuses:
                for pod_item in container_statuses:
                    if pod_item['name'] == 'POD':
                        continue
                    for container in pod.containers:
                        if container['name'] == pod_item['name']:
                            state, stateDetails = pod_item.pop(
                                'state').items()[0]
                            pod_item['state'] = state
                            pod_item['startedAt'] = stateDetails.get(
                                'startedAt')
                            if state == 'terminated':
                                pod_item['exitCode'] = stateDetails.get(
                                    'exitCode')
                                pod_item['finishedAt'] = stateDetails.get(
                                    'finishedAt')
                            container_id = pod_item.get(
                                'containerID',
                                container['name'])
                            pod_item['containerID'] = _del_docker_prefix(
                                container_id)
                            image_id = pod_item.get(
                                'imageID',
                                container['image'])
                            pod_item['imageID'] = _del_docker_prefix(image_id)
                            container.update(pod_item)
            else:
                for container in pod.containers:
                    container['state'] = pod.status
                    container['containerID'] = None
                    container['imageID'] = None
        else:
            pod._forge_dockers(status=pod.status)
        return pod

    def as_dict(self):
        # unneeded fields in API output
        hide_fields = ['node', 'labels', 'namespace', 'secrets', 'owner']
        data = vars(self).copy()
        data['volumes'] = data.pop('volumes_public', [])
        for container in data.get('containers', ()):
            new_volumes = []
            for volume_mount in container.get('volumeMounts', ()):
                mount_path = volume_mount.get('mountPath', '')
                # Skip origin root mountPath
                if ORIGIN_ROOT in mount_path:
                    continue
                # strip Z option from mountPath
                if mount_path[-2:] in (':Z', ':z'):
                    volume_mount['mountPath'] = mount_path[:-2]
                new_volumes.append(volume_mount)
            container['volumeMounts'] = new_volumes

        for field in hide_fields:
            if field in data:
                del data[field]
        return data

    def as_json(self):
        return json.dumps(self.as_dict())

    def compose_persistent(self):
        if not getattr(self, 'volumes', False):
            self.volumes_public = []
            return
        # volumes - k8s api, volumes_public - kd api
        self.volumes_public = deepcopy(self.volumes)
        clean_vols = set()
        for volume, volume_public in zip(self.volumes, self.volumes_public):
            if 'persistentDisk' in volume:
                self._handle_persistent_storage(volume, volume_public)
            elif 'localStorage' in volume:
                self._handle_local_storage(volume)
            else:
                name = volume.get('name', None)
                clean_vols.add(name)
        if clean_vols:
            self.volumes = [item for item in self.volumes
                            if item['name'] not in clean_vols]

    def _handle_persistent_storage(self, volume, volume_public):
        """Prepare volume with persistent storage

        :params volume: volume for k8s api
            (storage specific attributes will be added)
        :params volume_public: volume for kuberdock api
            (all missing fields will be filled)
        """
        pd = volume.pop('persistentDisk')
        name = pd.get('pdName')

        persistent_disk = PersistentDisk.filter_by(owner_id=self.owner.id,
                                                   name=name).first()
        if persistent_disk is None:
            persistent_disk = PersistentDisk(name=name, owner_id=self.owner.id,
                                             size=pd.get('pdSize', 1))
            db.session.add(persistent_disk)
        if volume_public['persistentDisk'].get('pdSize') is None:
            volume_public['persistentDisk']['pdSize'] = persistent_disk.size
        pd_cls = get_storage_class()
        if not pd_cls:
            return
        pd_cls().enrich_volume_info(volume, persistent_disk.size,
                                    persistent_disk.drive_name)

    def _handle_local_storage(self, volume):
        # TODO: cleanup localStorage volumes. It is now used only for pods of
        # internal user.
        local_storage = volume.pop('localStorage')
        if not local_storage:
            return
        if isinstance(local_storage, dict) and 'path' in local_storage:
            path = local_storage['path']
        else:
            path = os.path.join(NODE_LOCAL_STORAGE_PREFIX, self.id,
                                volume['name'])
        volume['hostPath'] = {'path': path}

    # We can't use pod's ports from spec because we strip hostPort from them
    def _dump_ports(self):
        return json.dumps([c.get('ports', []) for c in self.containers])

    def _dump_kubes(self):
        return json.dumps(
            {c.get('name'): c.get('kubes', 1) for c in self.containers})

    def extract_volume_annotations(self, volumes):
        if not volumes:
            return []
        res = [vol.pop('annotation') for vol in volumes if 'annotation' in vol]
        return res

    def prepare(self):
        kube_type = getattr(self, 'kube_type', Kube.get_default_kube_type())
        volumes = getattr(self, 'volumes', [])
        secrets = getattr(self, 'secrets', [])
        kuberdock_resolve = ''.join(getattr(self, 'kuberdock_resolve', []))
        volume_annotations = self.extract_volume_annotations(volumes)

        # Extract volumeMounts for missing volumes
        # missing volumes may exist if there some 'Container' storages, as
        # described in https://cloudlinux.atlassian.net/browse/AC-2492
        existing_vols = {item['name'] for item in volumes}
        containers = []
        for container in self.containers:
            container = deepcopy(container)
            container['volumeMounts'] = [
                item for item in container.get('volumeMounts', [])
                if item['name'] in existing_vols]
            containers.append(
                self._prepare_container(container, kube_type, volumes)
            )

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
                            "kuberdock-pod-uid": self.id,
                            "kuberdock-user-uid": str(self.owner.id),
                        },
                        "annotations": {
                            "kuberdock_resolve": kuberdock_resolve,
                            "kuberdock-pod-ports": self._dump_ports(),
                            "kuberdock-container-kubes": self._dump_kubes(),
                            "kuberdock-volume-annotations": json.dumps(
                                volume_annotations
                            )
                        }
                    },
                    "spec": {
                        "volumes": volumes,
                        "containers": containers,
                        "restartPolicy": getattr(self, 'restartPolicy',
                                                 'Always'),
                        "imagePullSecrets": [{"name": secret}
                                             for secret in secrets]
                    }
                }
            }
        }
        pod_config = config['spec']['template']

        # Internal services may run on any nodes, do not care of kube type of
        # the node. All other kube types must be binded to the appropriate
        # nodes
        if Kube.is_node_attachable_type(kube_type):
            pod_config['spec']['nodeSelector'] = {
                "kuberdock-kube-type": "type_{0}".format(kube_type)
            }
        else:
            pod_config['spec']['nodeSelector'] = {}
        if hasattr(self, 'node') and self.node:
            pod_config['spec']['nodeSelector']['kuberdock-node-hostname'] = \
                self.node
        if hasattr(self, 'public_ip'):
            pod_config['metadata']['labels']['kuberdock-public-ip'] = \
                self.public_ip
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
        data = deepcopy(data)
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
        else:  # if we create pod, not start stopped
            data.update(kubes_to_limits(kubes, kube_type))

        wd = data.get('workingDir', '.')
        if type(wd) is list:
            data['workingDir'] = ','.join(data['workingDir'])

        for p in data.get('ports', []):
            p['protocol'] = p.get('protocol', 'TCP').upper()
            p.pop('isPublic', None)  # Non-kubernetes param

        if self.owner != KUBERDOCK_INTERNAL_USER:
            for p in data.get('ports', []):
                p.pop('hostPort', None)

        self.add_origin_root(data, volumes)
        self.add_securety_labels(data, volumes)

        data['imagePullPolicy'] = 'Always'
        return data

    def add_origin_root(self, container, volumes):
        """If there are lifecycle in container, then mount origin root from
        docker overlay path. Need this for container hooks.
        """
        if 'lifecycle' in container:
            image = Image(container['image'])
            image_id = image.get_id()
            volume_name = '-'.join([container['name'], ORIGIN_ROOT])
            volumes.append(
                {u'hostPath': {u'path': OVERLAY_PATH.format(image_id)},
                 u'name': volume_name})
            container['volumeMounts'].append(
                {u'readOnly': True, u'mountPath': u'/{}'.format(ORIGIN_ROOT),
                 u'name': volume_name})

    def add_securety_labels(self, container, volumes):
        """Add SELinuxOptions to volumes. For now, just add docker `:Z` option
        to mountPath.
        """
        # TODO: after k8s 1.2 version, use
        # `pod.Spec.SecurityContext.SELinuxOptions`
        for volume_mount in container.get('volumeMounts', ()):
            for volume in volumes:
                if ('rbd' in volume and
                        volume.get('name') == volume_mount.get('name')):

                    mountPath = volume_mount.get('mountPath', '')
                    if mountPath and mountPath[-2:] not in (':Z', ':z'):
                        volume_mount['mountPath'] += ':Z'

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

    def check_name(self):
        pod = DBPod.query.filter(DBPod.name == self.name,
                                 DBPod.owner_id == self.owner.id,
                                 DBPod.id != self.id).first()
        if pod:
            raise APIError('Pod with name "{0}" already exists. '
                           'Try another name.'.format(self.name),
                           status_code=409, type='PodNameConflict')

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
