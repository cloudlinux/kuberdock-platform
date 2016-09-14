import json
import os
import shlex
import uuid
from copy import deepcopy

from flask import current_app

import pstorage
from . import helpers
from . import podutils
from .helpers import KubeQuery, K8sSecretsClient, K8sSecretsBuilder
from .images import Image
from .. import billing
from .. import settings
from ..billing.models import Kube
from ..exceptions import APIError, ServicePodDumpError
from ..pods.models import (db, PersistentDisk, PersistentDiskStatuses,
                           Pod as DBPod)
from ..utils import POD_STATUSES

ORIGIN_ROOT = 'originroot'
OVERLAY_PATH = u'/var/lib/docker/overlay/{}/root'
MOUNT_KDTOOLS_PATH = '/.kdtools'
HOST_KDTOOLS_PATH = '/usr/lib/kdtools'
SERVICE_ACCOUNT_STUB_PATH = '/var/run/secrets/kubernetes.io/serviceaccount'


class PodOwner(dict):
    """Inherited from dict so as it will be presented as dict in
    `as_dict` method.
    """
    def __init__(self, id, username):
        super(PodOwner, self).__init__(id=id, username=username)
        self.id = id
        self.username = username

    def is_internal(self):
        return self.username == settings.KUBERDOCK_INTERNAL_USER


class VolumeExists(APIError):
    message_template = u'Volume with name "{name}" already exists'
    status_code = 409

    def __init__(self, volume_name=None, volume_id=None):
        details = {'name': volume_name, 'id': volume_id}
        super(VolumeExists, self).__init__(details=details)


class Pod(object):
    """
    Represents related k8s resources: RC, Service and all replicas (Pods).

    TODO: document other attributes

    id - uuid4, id in db
    namespace - uuid4, for now it's the same as `id`
    name - kubedock.pods.models.Pod.name (name in UI)
    owner - PodOwnerTuple()
    podIP - k8s.Service.spec.clusterIP (appears after first start)
    service - k8s.Service.metadata.name (appears after first start)
    sid - uuid4, k8s.ReplicationController.metadata.name
    secrets - list of k8s.Secret.name
    kube_type - Kube Type id
    volumes_public - public volumes data
    volumes -
        before self.compose_persistent() -- see volumes_public
        after -- volumes spec prepared for k8s
    k8s_status - current status in k8s or None
    db_status - current status in db or None
    status - common status composed from k8s_status and db_status
    ...

    """

    def __init__(self, data=None):
        self.k8s_status = None
        owner = None
        if data is not None:
            for c in data['containers']:
                if len(c.get('args', [])) == 1:
                    # it seems the args has been changed
                    # or may be its length is only 1 item
                    c['args'] = self._parse_cmd_string(c['args'][0])
            if 'owner' in data:
                owner = data.pop('owner')
            for k, v in data.items():
                setattr(self, k, v)
        self.set_owner(owner)

    def set_owner(self, owner):
        """Set owner field as a named tuple with minimal necessary fields.
        It is needed to pass Pod object to async celery task, to prevent
        DetachedInstanceError, because of another session in celery task.
        :param owner: object of 'User' model

        """
        if owner is not None:
            self.owner = PodOwner(id=owner.id, username=owner.username)
        else:
            self.owner = PodOwner(None, None)

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
        pod.k8s_status = pod.status
        pod.hostIP = status.get('hostIP')

        # TODO why we call this "pod.host" instead of "pod.nodeName" ?
        # rename it
        pod.host = spec.get('nodeName')
        pod.kube_type = spec.get('nodeSelector', {}).get('kuberdock-kube-type')
        # TODO we should use nodeName or hostIP instead, and rename this attr
        pod.node = spec.get('nodeSelector', {}).get('kuberdock-node-hostname')
        pod.volumes = spec.get('volumes', [])
        pod.containers = spec.get('containers', [])
        pod.restartPolicy = spec.get('restartPolicy')
        pod.dnsPolicy = spec.get('dnsPolicy')
        pod.serviceAccount = spec.get('serviceAccount', False)

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
            pod.forge_dockers(status=pod.status)

        pod.ready = all(container.get('ready')
                        for container in pod.containers)
        return pod

    def dump(self):
        """Get full information about pod.
        ATTENTION! Do not use it in methods allowed for user! It may contain
        secret information. FOR ADMINS ONLY!
        """
        if self.owner.is_internal():
            raise ServicePodDumpError

        pod_data = self.as_dict()
        owner = self.owner
        k8s_secrets = self.get_secrets()
        volumes_map = self.get_volumes()

        rv = {
            'pod_data': pod_data,
            'owner': owner,
            'k8s_secrets': k8s_secrets,
            'volumes_map': volumes_map,
        }

        return rv

    def get_volumes(self):
        vols = (vol for vol in getattr(self, 'volumes', [])
                if 'name' in vol and 'hostPath' in vol)
        return {vol['name']: vol['hostPath']['path'] for vol in vols}

    def get_secrets(self):
        """Retrieve secrets of type '.dockercfg' from kubernetes.

        Returns dict {secret_name: parsed_secret_data, ...}.
        Structure of parsed_secret_data see in :class:`K8sSecretsBuilder`.
        """
        secrets_client = K8sSecretsClient(KubeQuery())

        try:
            resp = secrets_client.list(namespace=self.namespace)
        except secrets_client.ErrorBase as e:
            raise APIError('Cannot get k8s secrets due to: %s' % e.message)

        parse = K8sSecretsBuilder.parse_secret_data

        rv = {x['metadata']['name']: parse(x['data'])
              for x in resp['items']
              if x['type'] == K8sSecretsClient.SECRET_TYPE}

        return rv

    def _as_dict(self):
        data = vars(self).copy()

        data['volumes'] = data.pop('volumes_public', [])
        for container in data.get('containers', ()):
            new_volumes = []
            for volume_mount in container.get('volumeMounts', ()):
                mount_path = volume_mount.get('mountPath', '')
                # Skip origin root mountPath
                hidden_volumes = [
                    ORIGIN_ROOT, MOUNT_KDTOOLS_PATH, SERVICE_ACCOUNT_STUB_PATH]
                if any(item in mount_path for item in hidden_volumes):
                    continue
                # strip Z option from mountPath
                if mount_path[-2:] in (':Z', ':z'):
                    volume_mount['mountPath'] = mount_path[:-2]
                new_volumes.append(volume_mount)
            container['volumeMounts'] = new_volumes

            # Filter internal variables
            container['env'] = [var for var in container.get('env', [])
                                if var['name'] not in ('KUBERDOCK_SERVICE',)]

        if data.get('edited_config') is not None:
            data['edited_config'] = Pod(data['edited_config']).as_dict()

        return data

    def as_dict(self):
        # unneeded fields in API output
        hide_fields = ['node', 'labels', 'namespace', 'secrets', 'owner']

        data = self._as_dict()

        for field in hide_fields:
            if field in data:
                del data[field]

        return data

    def as_json(self):
        return json.dumps(self.as_dict())

    def compose_persistent(self, reuse_pv=True):
        if not getattr(self, 'volumes', False):
            self.volumes_public = []
            return
        # volumes - k8s api, volumes_public - kd api
        self.volumes_public = deepcopy(self.volumes)
        clean_vols = set()
        for volume, volume_public in zip(self.volumes, self.volumes_public):
            if 'persistentDisk' in volume:
                self._handle_persistent_storage(
                    volume, volume_public, reuse_pv)
            elif 'localStorage' in volume:
                self._handle_local_storage(volume)
            else:
                name = volume.get('name', None)
                clean_vols.add(name)
        if clean_vols:
            self.volumes = [item for item in self.volumes
                            if item['name'] not in clean_vols]

    def _handle_persistent_storage(self, volume, volume_public, reuse_pv):
        """Prepare volume with persistent storage

        :param volume: volume for k8s api
            (storage specific attributes will be added).
        :param volume_public: volume for kuberdock api
            (all missing fields will be filled).
        :param reuse_pv: if True then reuse existed persistent volumes,
            otherwise raise VolumeExists on name conflict.
        """
        pd = volume.pop('persistentDisk')
        name = pd.get('pdName')

        persistent_disk = PersistentDisk.filter_by(owner_id=self.owner.id,
                                                   name=name).first()
        if persistent_disk is None:
            persistent_disk = PersistentDisk(name=name, owner_id=self.owner.id,
                                             size=pd.get('pdSize', 1))
            db.session.add(persistent_disk)
        else:
            if persistent_disk.state == PersistentDiskStatuses.DELETED:
                persistent_disk.size = pd.get('pdSize', 1)
            elif not reuse_pv:
                raise VolumeExists(persistent_disk.name, persistent_disk.id)
            persistent_disk.state = PersistentDiskStatuses.PENDING
        if volume_public['persistentDisk'].get('pdSize') is None:
            volume_public['persistentDisk']['pdSize'] = persistent_disk.size
        pd_cls = pstorage.get_storage_class()
        if not pd_cls:
            return
        pd_cls().enrich_volume_info(volume, persistent_disk)

    def _handle_local_storage(self, volume):
        # TODO: cleanup localStorage volumes. It is now used only for pods of
        # internal user.
        local_storage = volume.pop('localStorage')
        if not local_storage:
            return
        if isinstance(local_storage, dict) and 'path' in local_storage:
            path = local_storage['path']
        else:
            path = os.path.join(settings.NODE_LOCAL_STORAGE_PREFIX, self.id,
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
        service_account = getattr(self, 'serviceAccount', False)
        service = getattr(self, 'service', '')

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
        add_kdtools(containers, volumes)
        add_kdenvs(containers, [
            ("KUBERDOCK_SERVICE", service),
        ])
        if not service_account:
            add_serviceaccount_stub(containers, volumes)

        config = {
            "kind": "ReplicationController",
            "apiVersion": settings.KUBE_API_VERSION,
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
                            ),
                        }
                    },
                    "spec": {
                        "securityContext": {'seLinuxOptions': {}},
                        "volumes": volumes,
                        "containers": containers,
                        "restartPolicy": getattr(self, 'restartPolicy',
                                                 'Always'),
                        "dnsPolicy": getattr(self, 'dnsPolicy',
                                             'ClusterFirst'),
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
        if hasattr(self, 'public_ip') and self.public_ip:
            pod_config['metadata']['labels']['kuberdock-public-ip'] = \
                self.public_ip
        if hasattr(self, 'domain'):
            pod_config['metadata']['labels']['kuberdock-domain'] = self.domain
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
            data['name'] = podutils.make_name_from_image(data.get('image', ''))

        if volumes is None:
            volumes = []

        try:
            kubes = int(data.pop('kubes'))
        except (KeyError, ValueError):
            pass
        else:  # if we create pod, not start stopped
            data.update(billing.kubes_to_limits(kubes, kube_type))

        wd = data.get('workingDir', '.')
        if type(wd) is list:
            data['workingDir'] = ','.join(data['workingDir'])

        for p in data.get('ports', []):
            p['protocol'] = p.get('protocol', 'TCP').upper()
            p.pop('isPublic', None)  # Non-kubernetes param

        if isinstance(self.owner, basestring):
            current_app.logger.warning('Pod owner field is a string type - '
                                       'possibly refactoring problem')
            owner_name = self.owner
        else:
            owner_name = self.owner.username
        if owner_name != settings.KUBERDOCK_INTERNAL_USER:
            for p in data.get('ports', []):
                p.pop('hostPort', None)

        self.add_origin_root(data, volumes)

        data['imagePullPolicy'] = 'Always'
        return data

    def add_origin_root(self, container, volumes):
        """If there are lifecycle in container, then mount origin root from
        docker overlay path. Need this for container hooks.
        """
        if 'lifecycle' not in container:
            # No container hooks defined for container
            return

        volume_name = '-'.join([container['name'], ORIGIN_ROOT])

        # Make sure we remove previous info, to handle case when image changes
        origin_root_vol = filter(lambda v: v['name'] == volume_name,
                                 volumes)
        if origin_root_vol:
            volumes.remove(origin_root_vol[0])
        origin_root_mnt = filter(lambda m: m['name'] == volume_name,
                                 container['volumeMounts'])
        if origin_root_mnt:
            container['volumeMounts'].remove(origin_root_mnt[0])

        image = Image(container['image'])
        image_id = image.get_id()
        volumes.append(
            {u'hostPath': {u'path': OVERLAY_PATH.format(image_id)},
             u'name': volume_name})
        container['volumeMounts'].append(
            {u'readOnly': True, u'mountPath': u'/{}'.format(ORIGIN_ROOT),
             u'name': volume_name})

    def _parse_cmd_string(self, cmd_string):
        lex = shlex.shlex(cmd_string, posix=True)
        lex.whitespace_split = True
        lex.commenters = ''
        lex.wordchars += '.'
        try:
            return list(lex)
        except ValueError:
            podutils.raise_('Incorrect cmd string')

    def forge_dockers(self, status='stopped'):
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
            raise APIError(
                u'Pod with name "{0}" already exists.'.format(self.name),
                status_code=409, type='PodNameConflict',
                details={'id': pod.id, 'name': pod.name}
            )

    def set_status(self, status, send_update=False, force=False):
        """Updates pod status in database"""
        # We can't be sure the attribute is already assigned, because
        # attributes of Pod class not defined in __init__.
        # For example attr 'status' will not be defined if we just
        # create Pod object from db config of model Pod.
        if getattr(self, 'status', None) == POD_STATUSES.unpaid and not force:
            # TODO: remove  status "unpaid", use separate field/flag,
            # then remove this block
            raise APIError('Not allowed to change "unpaid" status.',
                           type='NotAllowedToChangeUnpaidStatus')

        db_pod = DBPod.query.get(self.id)
        # We shouldn't change pod's deleted status.
        if db_pod.status == POD_STATUSES.deleted:
            raise APIError('Not allowed to change "deleted" status.',
                           type='NotAllowedToChangeDeletedStatus')

        helpers.set_pod_status(self.id, status, send_update=send_update)
        self.status = status

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


def add_kdtools(containers, volumes):
    """Adds volume to mount kd tools for every container.
    That tools contains statically linked binaries to provide ssh access
    into containers.

    """
    prefix = 'kdtools-'
    volume_name = prefix + uuid.uuid4().hex
    # Make sure we remove previous info, to handle case when image changes
    kdtools_vol = filter(lambda v: v['name'].startswith(prefix), volumes)
    if kdtools_vol:
        volumes.remove(kdtools_vol[0])
    volumes.append({
        u'hostPath': {u'path': HOST_KDTOOLS_PATH},
        u'name': volume_name})
    for container in containers:
        kdtools_mnt = filter(lambda m: m['name'].startswith(prefix),
                             container['volumeMounts'])
        if kdtools_mnt:
            container['volumeMounts'].remove(kdtools_mnt[0])
        container['volumeMounts'].append({
            u'readOnly': True,
            u'mountPath': MOUNT_KDTOOLS_PATH,
            u'name': volume_name
        })


def add_serviceaccount_stub(containers, volumes):
    """
    Add Service Account stub for Pods that do not needed it.
    It's a workaround to prevent access from non-service pods to k8s services.
    TODO: Probably there is a better way to do this.
    See: http://kubernetes.io/docs/admin/service-accounts-admin/
    http://kubernetes.io/docs/user-guide/service-accounts/

    :param containers: Pod Containers
    :type containers: list
    :param volumes: Pod Volumes
    :type volumes: list

    TODO: Why do we need this?

    """

    volume_name = 'serviceaccount-stub-' + uuid.uuid4().hex
    volumes.append({
        'emptyDir': {},
        'name': volume_name
    })
    for container in containers:
        container['volumeMounts'].append({
            'mountPath': SERVICE_ACCOUNT_STUB_PATH,
            'name': volume_name
        })


def add_kdenvs(containers, envs):
    """
    Add KuberDock related Environment Variables to Pod Containers

    :param containers: Pod Containers
    :type containers: list
    :param envs: Environment Variables to be added
    :type envs: list
    """

    for container in containers:
        env = container.get('env', [])

        # TODO: What if such var already exists in list ? We should have
        # unittests for this function
        for name, value in envs:
            env.insert(0, {'name': name, 'value': value})
        if env:
            container['env'] = env
