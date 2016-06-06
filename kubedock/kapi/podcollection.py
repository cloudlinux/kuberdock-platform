import ipaddress
import json
from os import path
import time
from uuid import uuid4
from base64 import urlsafe_b64encode, urlsafe_b64decode
from collections import defaultdict
from flask import current_app

from . import pd_utils
from .pod import Pod
from .images import Image
from .pstorage import (get_storage_class_by_volume_info, get_storage_class,
                       delete_drive_by_id)
from .helpers import KubeQuery, ModelQuery, Utilities
from .licensing import is_valid as license_valid
from ..core import db
from ..billing import repr_limits
from ..exceptions import APIError
from ..kd_celery import celery
from ..pods.models import (
    PersistentDisk, PodIP, IPPool, Pod as DBPod, PersistentDiskStatuses)
from ..usage.models import IpState
from ..system_settings.models import SystemSettings
from ..utils import POD_STATUSES, atomic, update_dict, send_event_to_user, retry
from ..settings import (KUBERDOCK_INTERNAL_USER, TRIAL_KUBES, KUBE_API_VERSION,
                        DEFAULT_REGISTRY, AWS)
DOCKERHUB_INDEX = 'https://index.docker.io/v1/'
UNKNOWN_ADDRESS = 'Unknown'


def get_user_namespaces(user):
    return {pod.namespace for pod in user.pods if not pod.is_deleted}


class NoFreeIPs(APIError):
    message = 'There are no free public IP-addresses, contact KuberDock administrator'


class PodNotFound(APIError):
    message = 'Pod not found'
    status_code = 404


class PodCollection(KubeQuery, ModelQuery, Utilities):

    def __init__(self, owner=None):
        """
        :param owner: User model instance
        """
        # Original names of pods in k8s {'metadata': 'name'}
        # Pod class store it in 'sid' field, but here it will be replaced with
        # name of pod in replication controller.
        self.pod_names = None
        self.owner = owner
        namespaces = self._get_namespaces()
        self._get_pods(namespaces)
        self._merge()

    def add(self, params, skip_check=False):  # TODO: celery
        if not skip_check and not license_valid():
            raise APIError("Action forbidden. Please contact support.")

        # TODO: with cerberus 0.10 use "default" normalization rule
        for container in params['containers']:
            container.setdefault('sourceUrl',
                                 Image(container['image']).source_url)
            container.setdefault('kubes', 1)
        params.setdefault('volumes', [])

        secrets = sorted(extract_secrets(params['containers']))
        fix_relative_mount_paths(params['containers'])

        storage_cls = get_storage_class()
        if storage_cls:
            persistent_volumes = [vol for vol in params['volumes']
                                  if 'persistentDisk' in vol]
            if not storage_cls.are_pod_volumes_compatible(
                    persistent_volumes, self.owner.id, params):
                raise APIError("Invalid combination of persistent disks")

        if not skip_check:
            self._check_trial(params)
            Image.check_containers(params['containers'], secrets)

        params['namespace'] = params['id'] = str(uuid4())
        params['sid'] = str(uuid4())  # TODO: do we really need this field?
        params['owner'] = self.owner

        billing_type = SystemSettings.get_by_name('billing_type').lower()
        if (not skip_check and billing_type != 'no billing' and
                self.owner.fix_price):
            # All pods created by fixed-price users initially must have status
            # "unpaid". Status may be changed later (using command "set").
            params['status'] = POD_STATUSES.unpaid
        params.setdefault('status', POD_STATUSES.stopped)

        pod = Pod(params)
        pod.check_name()
        # create PD models in db and change volumes schema in config
        pod.compose_persistent()
        self._make_namespace(pod.namespace)
        # create secrets in k8s and add IDs in config
        pod.secrets = [self._make_secret(pod.namespace, *secret)
                       for secret in secrets]

        set_public_ip = self.needs_public_ip(params)
        db_pod = self._save_pod(pod, set_public_ip)
        if set_public_ip:
            if getattr(db_pod, 'public_ip', None):
                pod.public_ip = db_pod.public_ip
            if getattr(db_pod, 'public_aws', None):
                pod.public_aws = db_pod.public_aws
        pod._forge_dockers()
        return pod.as_dict()

    def get(self, pod_id=None, as_json=True):
        if pod_id is None:
            if self.owner is None:
                pods = [p.as_dict() for p in self._collection.values()]
            else:
                pods = [p.as_dict() for p in self._collection.values()
                        if getattr(p, 'owner', '') == self.owner]
        else:
            pods = self._get_by_id(pod_id).as_dict()
        if as_json:
            return json.dumps(pods)
        return pods

    def _get_by_id(self, pod_id):
        try:
            if self.owner is None:
                pod = (p for p in self._collection.values()
                       if p.id == pod_id).next()
            else:
                pod = (p for p in self._collection.values()
                       if p.id == pod_id and
                       getattr(p, 'owner', '') == self.owner).next()
        except StopIteration:
            raise PodNotFound()
        return pod

    @staticmethod
    def needs_public_ip(conf):
        """
        Return true of pod needs public ip
        """
        for c in conf.get('containers', []):
            for port in c.get('ports', []):
                if port.get('isPublic', False):
                    return True
        return False

    @staticmethod
    @atomic()
    def _set_public_ip(pod):
        """Assign some free IP address to the pod."""
        conf = pod.get_dbconfig()
        if AWS:
            conf.setdefault('public_aws', UNKNOWN_ADDRESS)
        else:
            ip_address = IPPool.get_free_host(as_int=True)
            if ip_address is None:
                raise NoFreeIPs()
            network = IPPool.get_network_by_ip(ip_address)
            if pod.ip is None:
                db.session.add(PodIP(pod=pod, network=network.network,
                                     ip_address=ip_address))
            else:
                current_app.logger.warning('PodIP {0} is already allocated'
                                           .format(pod.ip.to_dict()))
            conf['public_ip'] = pod.public_ip = str(pod.ip)
            IpState.start(pod.id, pod.ip)
        pod.set_dbconfig(conf, save=False)

    @atomic()
    def _set_entry(self, pod, data):
        """Immediately set fields "status", "name", "postDescription" in DB."""
        db_pod = DBPod.query.get(pod.id)
        commandOptions = data['commandOptions']
        if commandOptions.get('status'):
            if pod.status in (POD_STATUSES.stopped, POD_STATUSES.unpaid):
                pod.status = db_pod.status  # only if not in k8s
            db_pod.status = commandOptions['status']
        if commandOptions.get('name'):
            pod.name = commandOptions['name']
            pod.check_name()
            db_pod.name = pod.name
        if 'postDescription' in commandOptions:
            pod.postDescription = commandOptions['postDescription']
            config = dict(db_pod.get_dbconfig(),
                          postDescription=pod.postDescription)
            db_pod.set_dbconfig(config, save=False)
        return pod.as_dict()

    @staticmethod
    @atomic()
    def _remove_public_ip(pod_id=None, ip=None):
        """Free ip (remove PodIP from database and change pod config).

        Needed for suspend user feature. When user is suspended all his pods
        will be stopped and IP must be freed.
        We remove `public_ip` and `isPublic` flags, but mark that this pod had
        public IP (and public ports) before, to be able to "unsuspend" user
        without any damage to his pods.

        :param pod_id: pod id
        :param ip: ip as a string (u'1.2.3.4'), number (16909060),
            or PodIP instance
        """
        if not isinstance(ip, PodIP):
            query = PodIP.query
            if pod_id:
                query = query.filter_by(pod_id=pod_id)
            if ip:
                query = query.filter_by(
                    ip_address=int(ipaddress.ip_address(ip)))
            ip = query.first()
            if ip is None:
                return
        elif ip.pod.id != pod_id:
            return

        # TODO: AC-1662 unbind ip from nodes and delete service
        pod = ip.pod
        pod_config = pod.get_dbconfig()
        pod_config['public_ip_before_freed'] = pod_config.pop('public_ip',
                                                              None)
        for container in pod_config['containers']:
            for port in container['ports']:
                port['isPublic_before_freed'] = port.pop('isPublic', None)
        pod.set_dbconfig(pod_config, save=False)
        IpState.end(pod_id, ip.ip_address)
        db.session.delete(ip)

    @classmethod
    @atomic()
    def _return_public_ip(cls, pod_id):
        """
        If pod had public IP, and it was removed, return it back to the pod.

        For more info see `_remove_public_ip` docs.
        """
        pod = DBPod.query.get(pod_id)
        pod_config = pod.get_dbconfig()

        if pod_config.pop('public_ip_before_freed', None) is None:
            return

        for container in pod_config['containers']:
            for port in container['ports']:
                port['isPublic'] = port.pop('isPublic_before_freed', None)
        pod.set_dbconfig(pod_config, save=False)
        cls._set_public_ip(pod)

    @atomic()
    def _save_pod(self, obj, set_public_ip=False):
        """
        Save pod data to db.

        :param obj: kapi-Pod
        :param set_public_ip: Assign some free IP address to the pod.
        """
        template_id = getattr(obj, 'kuberdock_template_id', None)
        status = getattr(obj, 'status', POD_STATUSES.stopped)
        excluded = ('kuberdock_template_id',  # duplicates of model's fields
                    'owner', 'kube_type', 'status', 'id', 'name')
        data = {k: v for k, v in vars(obj).iteritems() if k not in excluded}
        pod = DBPod(name=obj.name, config=json.dumps(data), id=obj.id,
                    status=status, template_id=template_id,
                    kube_id=obj.kube_type, owner=self.owner)
        db.session.add(pod)
        if set_public_ip:
            self._set_public_ip(pod)
        return pod

    def update(self, pod_id, data):
        pod = self._get_by_id(pod_id)
        command = data.pop('command', None)
        if command is None:
            return
        dispatcher = {
            'start': self._start_pod,
            'stop': self._stop_pod,
            'redeploy': self._redeploy,
            'resize': self._resize_replicas,
            'change_config': self._change_pod_config,
            'set': self._set_entry,  # sets DB data, not pod config one
            # 'container_start': self._container_start,
            # 'container_stop': self._container_stop,
            # 'container_delete': self._container_delete,
        }
        if command in dispatcher:
            return dispatcher[command](pod, data)
        self._raise("Unknown command")

    def delete(self, pod_id, force=False):
        pod = self._get_by_id(pod_id)
        if pod.owner.username == KUBERDOCK_INTERNAL_USER and not force:
            self._raise('Service pod cannot be removed', 400)

        DBPod.query.get(pod_id).mark_as_deleting()

        PersistentDisk.free(pod.id)
        # we remove service also manually
        service_name = pod.get_config('service')
        if service_name:
            rv = self._del(['services', service_name], ns=pod.namespace)
            self._raise_if_failure(rv, "Could not remove a service")

        if hasattr(pod, 'public_ip'):
            self._remove_public_ip(pod_id=pod_id)
        # all deleted asynchronously, now delete namespace, that will ensure
        # delete all content
        self._drop_namespace(pod.namespace)
        self._mark_pod_as_deleted(pod_id)

    def check_updates(self, pod_id, container_name):
        """
        Check if image in registry differs from image in kubernetes

        :raise APIError: if pod not found or container not found in pod
            or image not found in registry
        """
        pod = self._get_by_id(pod_id)
        try:
            container = (c for c in pod.containers
                         if c['name'] == container_name).next()
        except StopIteration:
            raise APIError(
                'Container with id {0} not found'.format(container_name))
        image = container['image']
        image_id = container.get('imageID')
        if image_id is None:
            return False
        secrets = self._get_secrets(pod).values()
        image_id_in_registry = Image(image).get_id(secrets)
        if image_id_in_registry is None:
            raise APIError('Image not found in registry')
        return image_id != image_id_in_registry

    def update_container(self, pod_id, container_name):
        """
        Update container image by restarting the pod.

        :raise APIError: if pod not found or if pod is not running
        """
        pod = self._get_by_id(pod_id)
        self._stop_pod(pod, block=True)
        return self._start_pod(pod)

    def _make_namespace(self, namespace):
        data = self._get_namespace(namespace)
        if data is None:
            config = {
                "kind": "Namespace",
                "apiVersion": KUBE_API_VERSION,
                "metadata": {"name": namespace}}
            rv = self._post(['namespaces'], json.dumps(config), rest=True,
                            ns=False)
            # TODO where raise ?
            # current_app.logger.debug(rv)

    def _make_secret(self, namespace, username, password,
                     registry=DEFAULT_REGISTRY):
        # only index.docker.io in .dockercfg allowes to use
        # image url without the registry, like wncm/mynginx
        if registry.endswith('docker.io'):
            registry = DOCKERHUB_INDEX
        auth = urlsafe_b64encode('{0}:{1}'.format(username, password))
        secret = urlsafe_b64encode(
            '{{"{0}": {{"auth": "{1}", "email": "a@a.a" }}}}'.format(
                registry, auth))

        name = str(uuid4())
        config = {'apiVersion': KUBE_API_VERSION,
                  'kind': 'Secret',
                  'metadata': {'name': name, 'namespace': namespace},
                  'data': {'.dockercfg': secret},
                  'type': 'kubernetes.io/dockercfg'}

        rv = self._post(['secrets'], json.dumps(config), rest=True,
                        ns=namespace)
        if rv['kind'] == 'Status' and rv['status'] == 'Failure':
            raise APIError(rv['message'])
        return name

    def _get_secrets(self, pod):
        """
        Retrieve from kubernetes all secrets attached to the pod.

        :param pod: kubedock.kapi.pod.Pod
        :returns: mapping of secrets name to (username, password, registry)
        """
        secrets = {}
        for secret in pod.secrets:
            rv = self._get(['secrets', secret], ns=pod.namespace)
            if rv['kind'] == 'Status':
                raise APIError(rv['message'])
            dockercfg = json.loads(urlsafe_b64decode(
                str(rv['data']['.dockercfg'])))
            for registry, data in dockercfg.iteritems():
                username, password = urlsafe_b64decode(
                    str(data['auth'])).split(':', 1)
                # only index.docker.io in .dockercfg allowes to use image url
                # without the registry, like wncm/mynginx.
                # Replace it back to default registry
                if registry == DOCKERHUB_INDEX:
                    registry = DEFAULT_REGISTRY
                secrets[secret] = (username, password, registry)
        return secrets

    def _get_replicationcontroller(self, namespace, name):
        rc = self._get(['replicationcontrollers', name], ns=namespace)
        self._raise_if_failure(rc, "Couldn't find Replication Controller")
        return rc

    def _get_namespace(self, namespace):
        data = self._get(ns=namespace)
        if data.get('code') == 404:
            return None
        return data

    def _get_namespaces(self):
        data = self._get(['namespaces'], ns=False)
        namespaces = [i['metadata']['name'] for i in data.get('items', {})]
        if self.owner is None:
            return namespaces
        user_namespaces = get_user_namespaces(self.owner)
        return [ns for ns in namespaces if ns in user_namespaces]

    def _drop_namespace(self, namespace):
        rv = self._del(['namespaces', namespace], ns=False)
        self._raise_if_failure(rv, "Cannot delete namespace '{}'".format(
            namespace))
        return rv

    def _get_replicas(self, name=None):
        # TODO: apply namespaces here
        replicas = []
        data = self._get(['replicationControllers'])

        for item in data['items']:
            try:
                replica_item = {
                    'id': item['uid'],
                    'sid': item['id'],
                    'replicas': item['currentState']['replicas'],
                    'replicaSelector': item['desiredState']['replicaSelector'],
                    'name': item['labels']['kuberdock-pod-uid']}

                if name is not None and \
                        replica_item['replicaSelector'] != name:
                    continue
                replicas.append(replica_item)
            except KeyError:
                pass
        return replicas

    def _get_pods(self, namespaces=None):
        # current_app.logger.debug(namespaces)
        if not hasattr(self, '_collection'):
            self._collection = {}
        pod_index = set()

        data = []
        replicas_data = []

        if namespaces:
            for namespace in namespaces:
                data.extend(self._get(['pods'], ns=namespace)['items'])
                replicas = self._get(['replicationcontrollers'], ns=namespace)
                replicas_data.extend(replicas['items'])
        else:
            pods = self._get(['pods'])
            data.extend(pods.get('items', {}))
            replicas = self._get(['replicationcontrollers'])
            replicas_data.extend(replicas.get('items', {}))

        pod_names = defaultdict(set)

        for item in data:
            pod = Pod.populate(item)
            self.check_public_address(pod)
            pod_name = pod.sid

            for r in replicas_data:
                if self._is_related(item['metadata']['labels'],
                                    r['spec']['selector']):
                    # If replication controller manages more then one pod,
                    # _get_pods must return only one of them
                    # (we will filter by sid)
                    pod.sid = r['metadata']['name']
                    pod.replicas = r['spec']['replicas']
                    break
            else:
                pod.replicas = 1

            pod_names[pod.id, pod.namespace].add(pod_name)
            if pod.sid not in pod_index:
                self._collection[pod.id, pod.namespace] = pod
                pod_index.add(pod.sid)

        self.pod_names = pod_names

    @staticmethod
    def format_lbservice_name(pod_id):
        """Format name of service for LoadBalancer from pod id"""
        return "{}-lbservice".format(pod_id[:54])

    def check_public_address(self, pod):
        """Check if public address not set and try to get it from
        services. Update public address if found one.
        """
        if AWS:
            if getattr(pod, 'public_aws', UNKNOWN_ADDRESS) == UNKNOWN_ADDRESS:
                label_selector = 'name={}'.format(
                    self.format_lbservice_name(pod.id))
                services_list = self._get(['services'],
                                          {'labelSelector': label_selector},
                                          ns=pod.namespace)
                services = services_list['items']
                for service in services:
                    # For now, we just pick first service in list
                    # (it must be only one for AWS)
                    hostname = self.update_public_address(service, pod.id)
                    if hostname:
                        break

    @staticmethod
    def update_public_address(service, pod_id, send=False):
        """Try to get public address from service and if found update in DB
        and send event
        """
        if service['spec']['type'] == 'LoadBalancer':
            ingress = service['status']['loadBalancer'].get('ingress', [])
            if ingress and 'hostname' in ingress[0]:
                hostname = ingress[0]['hostname']
                pod = DBPod.query.get(pod_id)
                conf = pod.get_dbconfig()
                conf['public_aws'] = hostname
                pod.set_dbconfig(conf)
                if send:
                    send_event_to_user('pod:change', {'id': pod_id}, pod.owner_id)
                return hostname

    def _merge(self):
        """ Merge pods retrieved from kubernates api with data from DB """
        db_pods = self._fetch_pods(users=True)
        for db_pod in db_pods:
            db_pod_config = json.loads(db_pod.config)
            namespace = db_pod.namespace
            template_id = db_pod.template_id

            # exists in DB only
            if (db_pod.id, namespace) not in self._collection:
                pod = Pod(db_pod_config)
                pod.id = db_pod.id
                pod.status = getattr(db_pod, 'status', POD_STATUSES.stopped)
                pod._forge_dockers()
                self._collection[pod.id, namespace] = pod
            else:
                pod = self._collection[db_pod.id, namespace]
                pod.volumes_public = db_pod_config.get('volumes_public')
                pod.node = db_pod_config.get('node')
                pod.podIP = db_pod_config.get('podIP')
                pod.service = db_pod_config.get('service')

                if db_pod_config.get('public_ip'):
                    pod.public_ip = db_pod_config['public_ip']
                if db_pod_config.get('public_aws'):
                    pod.public_aws = db_pod_config['public_aws']

                pod.secrets = db_pod_config.get('secrets', [])
                a = pod.containers
                b = db_pod_config.get('containers')
                restore_fake_volume_mounts(a, b)
                pod.containers = self.merge_lists(a, b, 'name')
                restore_containers_host_ports_config(pod.containers, b)

            pod.name = db_pod.name
            pod.owner = db_pod.owner
            pod.template_id = template_id
            pod.kube_type = db_pod.kube_id

            if db_pod.status == 'deleting':
                pod.status = 'deleting'
            elif not hasattr(pod, 'status'):
                pod.status = POD_STATUSES.stopped

            for container in pod.containers:
                if container['state'] == 'terminated':
                    if container.get('exitCode') == 0:
                        container['state'] = 'succeeded'
                    else:
                        container['state'] = 'failed'
                container.pop('resources', None)
                container['limits'] = repr_limits(container['kubes'],
                                                  pod.kube_type)

    def ingress_public_ports(self, pod_id, namespace, ports):
        """Ingress public ports with cloudprovider specific methods
        """
        if AWS and ports:
            conf = {
                'kind': 'Service',
                'apiVersion': KUBE_API_VERSION,
                'metadata': {
                    'generateName': 'lbservice-',
                    'labels': {'name': self.format_lbservice_name(pod_id)},
                },
                'spec': {
                    'selector': {'kuberdock-pod-uid': pod_id},
                    'ports': ports,
                    'type': 'LoadBalancer',
                    'sessionAffinity': 'None'
                }
            }
            data = json.dumps(conf)
            rv = self._post(['services'], data, rest=True, ns=namespace)
            self._raise_if_failure(rv, "Could not ingress public ports")

    def _run_service(self, pod):
        ports = []
        public_ports = []
        for ci, c in enumerate(getattr(pod, 'containers', [])):
            for pi, p in enumerate(c.get('ports', [])):
                host_port = p.get('hostPort', None) or p.get('containerPort')
                port_name = 'c{0}-p{1}'.format(ci, pi)
                ports.append({
                    "name": port_name,
                    "port": host_port,
                    "protocol": p.get('protocol', 'TCP').upper(),
                    "targetPort": p.get('containerPort')})
                if p.get('isPublic', False):
                    public_ports.append({
                        "name": port_name,
                        "port": host_port,
                        "protocol": p.get('protocol', 'TCP').upper(),
                        "targetPort": p.get('containerPort')})
        conf = {
            'kind': 'Service',
            'apiVersion': KUBE_API_VERSION,
            'metadata': {
                'generateName': 'service-',
                'labels': {'name': pod.id[:54] + '-service'},
            },
            'spec': {
                'selector': {'kuberdock-pod-uid': pod.id},
                'ports': ports,
                'type': 'ClusterIP',
                'sessionAffinity': 'None'   # may be ClientIP is better
            }
        }
        if hasattr(pod, 'podIP') and pod.podIP:
            conf['spec']['clusterIP'] = pod.podIP
        self.ingress_public_ports(pod.id, pod.namespace, public_ports)
        data = json.dumps(conf)
        return self._post(['services'], data, rest=True, ns=pod.namespace)

    def _resize_replicas(self, pod, data):
        # FIXME: not working for now
        number = int(data.get('replicas', getattr(pod, 'replicas', 0)))
        replicas = self._get_replicas(pod.id)
        # TODO check replica numbers and compare to ones set in config
        for replica in replicas:
            rv = self._put(
                ['replicationControllers', replica.get('id', '')],
                json.loads({'desiredState': {'replicas': number}}))
            self._raise_if_failure(rv, "Could not resize a replica")
        return len(replicas)

    def _start_pod(self, pod, data=None):
        if pod.status == POD_STATUSES.unpaid:
            raise APIError("Pod is unpaid, we can't run it")
        if pod.status in (POD_STATUSES.running, POD_STATUSES.pending):
            raise APIError("Pod is not stopped, we can't run it")
        if pod.status == POD_STATUSES.succeeded or \
           pod.status == POD_STATUSES.failed:
            self._stop_pod(pod, block=True)
        self._make_namespace(pod.namespace)
        db_config = pod.get_config()

        self._process_persistent_volumes(pod, db_config.get('volumes', []))

        if not db_config.get('service'):
            for c in pod.containers:
                if len(c.get('ports', [])) > 0:
                    service_rv = self._run_service(pod)
                    self._raise_if_failure(service_rv,
                                           "Could not start a service")
                    db_config['service'] = service_rv['metadata']['name']
                    db_config['podIP'] = service_rv['spec']['clusterIP']
                    break

        self.replace_config(pod, db_config)

        config = pod.prepare()
        try:
            self._get_replicationcontroller(pod.namespace, pod.sid)
            rc = self._put(['replicationcontrollers', pod.sid],
                           json.dumps(config), ns=pod.namespace, rest=True)
        except APIError:
            rc = self._post(['replicationcontrollers'],
                            json.dumps(config), ns=pod.namespace, rest=True)
            self._raise_if_failure(rc, "Could not start '{0}' pod".format(
                pod.name.encode('ascii', 'replace')))

        for container in pod.containers:
            # TODO: create CONTAINER_STATUSES
            container['state'] = POD_STATUSES.pending
        pod.status = POD_STATUSES.pending
        return pod.as_dict()

    def _stop_pod(self, pod, data=None, raise_=True, block=False):
        # Call PD release in all cases. If the pod was already stopped and PD's
        # were not released, then it will free them. If PD's already free, then
        # this call will do nothing.
        PersistentDisk.free(pod.id)
        if pod.status not in (POD_STATUSES.stopped, POD_STATUSES.unpaid):
            if hasattr(pod, 'sid'):
                if block:
                    scale_replicationcontroller(pod.id)
                    wait_pod_status(pod.id, POD_STATUSES.stopped)
                else:
                    scale_replicationcontroller_task.apply_async((pod.id,))
                for container in pod.containers:
                    # TODO: create CONTAINER_STATUSES
                    container['state'] = POD_STATUSES.stopped
                pod.status = POD_STATUSES.stopped
                return pod.as_dict()
        elif raise_:
            raise APIError('Pod is already stopped')

    def _change_pod_config(self, pod, data):
        db_config = pod.get_config()
        update_dict(db_config, data)
        self.replace_config(pod, db_config)

        # get pod again after change
        pod = PodCollection()._get_by_id(pod.id)

        config = pod.prepare()
        rv = self._put(['replicationcontrollers', pod.sid], json.dumps(config),
                       rest=True, ns=pod.namespace)
        self._raise_if_failure(rv, "Could not change '{0}' pod".format(
            pod.name.encode('ascii', 'replace')))

        return pod.as_dict()

    def patch_running_pod(self, pod_id, data,
                          replace_lists=False, restart=False):
        """Patches spec of pod in RC.
        :param data: data part of pod's spec
        :param replace_lists: if true then lists in spec will be fully
            replaced with lists in 'data'. If False, then  lists will be
            appended.
        :param restart: If True, then after patching RC pods will be killed,
            so the RC will restart pods with patched config. If False, then
            pods will not be restarted.
        :return: Pod.as_dict()
        """
        pod = PodCollection()._get_by_id(pod_id)
        rcdata = json.dumps({'spec': {'template': data}})
        rv = self._patch(['replicationcontrollers', pod.sid], rcdata,
                         rest=True, ns=pod.namespace,
                         replace_lists=replace_lists)
        self._raise_if_failure(rv, "Could not change '{0}' pod RC".format(
            pod.name.encode('ascii', 'replace')))
        # Delete running pods, so the RC will create new pods with updated
        # spec.
        if restart:
            names = self.pod_names.get((pod_id, pod.namespace), [])
            for name in names:
                rv = self._del(['pods', name], ns=pod.namespace)
                self._raise_if_failure(rv, "Could not change '{0}' pod".format(
                    pod.name.encode('ascii', 'replace')))
        pod = PodCollection()._get_by_id(pod_id)
        return pod.as_dict()

    def _redeploy(self, pod, data):
        db_pod = DBPod.query.get(pod.id)
        # apply changes in config
        db_config = db_pod.get_dbconfig()
        containers = {c['name']: c for c in db_config['containers']}
        for container in data.get('containers', []):
            if container.get('kubes') is not None:
                containers[container['name']]['kubes'] = container.get('kubes')
        db_pod.set_dbconfig(db_config)

        finish_redeploy.delay(pod.id, data)
        # return updated pod
        return PodCollection(owner=self.owner).get(pod.id, as_json=False)

    # def _do_container_action(self, action, data):
    #     host = data.get('nodeName')
    #     if not host:
    #         return
    #     rv = {}
    #     containers = data.get('containers', '').split(',')
    #     for container in containers:
    #         command = 'docker {0} {1}'.format(action, container)
    #         status, message = run_ssh_command(host, command)
    #         if status != 0:
    #             self._raise('Docker error: {0} ({1}).'.format(
    #               message, status))
    #         if action in ('start', 'stop'):
    #             send_event('pull_pod_state', message)
    #         rv[container] = message or 'OK'
    #     return rv

    @staticmethod
    def _process_persistent_volumes(pod, volumes):
        """
        Processes preliminary persistent volume routines (create, attach, mkfs)
        :param pod: object -> a Pod instance
        :param volumes: list -> list of volumes
        """
        # extract PDs from volumes
        drives = {}
        for v in volumes:
            storage_cls = get_storage_class_by_volume_info(v)
            if storage_cls is None:
                continue
            storage = storage_cls()
            info = storage.extract_volume_info(v)
            drive_name = info.get('drive_name')
            if drive_name is None:
                raise APIError("Got no drive name")

            persistent_disk = PersistentDisk.filter_by(
                drive_name=drive_name
            ).first()
            if persistent_disk is None:
                raise APIError('Persistent Disk {0} not found'.format(
                                    drive_name),
                               404)
            drives[drive_name] = (storage, persistent_disk)
            if persistent_disk.state == PersistentDiskStatuses.TODELETE:
                # This status means that the drive is in deleting process now.
                # We can't be sure that drive exists or has been deleted at the
                # moment of starting pod.
                raise APIError(
                    'Persistent drive "{}" is deleting now. '
                    'Wait some time and try again later'.format(
                        persistent_disk.name
                    )
                )
            if persistent_disk.state != PersistentDiskStatuses.CREATED:
                persistent_disk.state = PersistentDiskStatuses.PENDING
        if not drives:
            return

        # check that pod can use all of them
        now_taken, taken_by_another_pod = PersistentDisk.take(
            pod.id, drives.keys()
        )
        # Flag points that persistent drives, binded on previous step, must be
        # unbind before exit.
        free_on_exit = False
        try:
            if taken_by_another_pod:
                free_on_exit = True
                raise APIError(
                    u'For now two pods cannot share one Persistent Disk. '
                    u'{0}. Stop these pods before starting this one.'
                    .format('; '.join('PD: {0}, Pod: {1}'.format(
                        item.name, item.pod.name)
                            for item in taken_by_another_pod
                        )
                    )
                )

            # prepare drives
            try:
                for drive_name, (storage,
                                 persistent_disk) in drives.iteritems():
                    storage.create(persistent_disk)
                    vid = storage.makefs(persistent_disk)
                    persistent_disk.state = PersistentDiskStatuses.CREATED
                    pod._update_volume_path(v['name'], vid)
            except:
                # free already taken drives in case of exception
                free_on_exit = True
                raise
        finally:
            if free_on_exit and now_taken:
                PersistentDisk.free_drives(now_taken)

    # def _container_start(self, pod, data):
    #     self._do_container_action('start', data)

    # def _container_stop(self, pod, data):
    #     self._do_container_action('stop', data)

    # def _container_delete(self, pod, data):
    #     self._do_container_action('rm', data)

    @staticmethod
    def _is_related(labels, selector):
        """
        Check that pod with labels is related to selector
        https://github.com/kubernetes/kubernetes/blob/master/docs/user-guide/
            labels.md#label-selectors
        """
        # TODO: what about Set-based selectors?
        if labels is None or selector is None:
            return False
        for key, value in selector.iteritems():
            if key not in labels or labels[key] != value:
                return False
        return True

    def _check_trial(self, params):
        if self.owner.is_trial():
            user_kubes = self.owner.kubes
            kubes_left = TRIAL_KUBES - user_kubes
            pod_kubes = sum(c['kubes'] for c in params['containers'])
            if pod_kubes > kubes_left:
                self._raise('Trial User limit is exceeded. '
                            'Kubes available for you: {0}'.format(kubes_left))


def wait_pod_status(pod_id, wait_status, interval=1, max_retries=10):
    """Keeps polling k8s api until pod status becomes as given"""
    def check_status():
        pod = PodCollection()._get_by_id(pod_id)
        if pod.status == wait_status:
            return pod

    return retry(
        check_status, interval, max_retries,
        APIError("Pod {0} did not become {1} after a given timeout. "
                 "It may become later.".format(pod_id, wait_status))
    )


def scale_replicationcontroller(pod_id, size=0, interval=1, max_retries=10):
    pc = PodCollection()
    pod = pc._get_by_id(pod_id)
    rc = pc._get_replicationcontroller(pod.namespace, pod.sid)
    rc['spec']['replicas'] = size
    rc = pc._put(['replicationcontrollers',
                  pod.sid], json.dumps(rc), ns=pod.namespace, rest=True)
    pc._raise_if_failure(rc, "Couldn't set replicas to {}".format(size))
    retry = 0
    while rc['status']['replicas'] != size and retry < max_retries:
        retry += 1
        rc = pc._get_replicationcontroller(pod.namespace, pod.sid)
        time.sleep(interval)
    if retry >= max_retries:
        current_app.logger.error("Can't scale rc: max retries exceeded")


@celery.task(ignore_results=True)
def scale_replicationcontroller_task(*args, **kwargs):
    scale_replicationcontroller(*args, **kwargs)


@celery.task(bind=True, ignore_results=True)
def finish_redeploy(self, pod_id, data, start=True):
    db_pod = DBPod.query.get(pod_id)
    pod_collection = PodCollection(db_pod.owner)
    pod = pod_collection._get_by_id(pod_id)
    pod_collection._stop_pod(pod, block=True)

    command_options = data.get('commandOptions') or {}
    if command_options.get('wipeOut'):
        for volume in pod.volumes_public:
            pd = volume.get('persistentDisk')
            if pd:
                pd = PersistentDisk.get_all_query().filter(
                    PersistentDisk.name == pd['pdName']
                ).first()
                delete_drive_by_id(pd.id)

    if start:  # start updated pod
        PodCollection(db_pod.owner).update(
            pod_id, {'command': 'start', 'commandOptions': command_options})


def restore_containers_host_ports_config(pod_containers, db_containers):
    """Updates 'hostPort' parameters in ports list of containers list.
    This parameters for usual pods (all users' pods) is not sending to
    kubernetes, it is treated as service port. So when we will get container
    list from kubernetes there will be no any 'hostPort' parameters.
    This function tries to restore that, so an user will see that parameters in
    client interface. 'hostPort' is stored in Pod's database config.
    If kubernetes will return 'hostPort' for some pods (it is explicitly set
    for internal service pods), then leave it as is.
    Matching of ports in ports lists will be made by 'containerPort' parameter.
    The function updates pod_containers items and return that changed list.

    """
    name_key = 'name'
    ports_key = 'ports'
    container_port_key = 'containerPort'
    host_port_key = 'hostPort'
    is_public_key = "isPublic"
    protocol_key = 'protocol'
    pod_conf = {item[name_key]: item for item in pod_containers}
    for db_container in db_containers:
        name = db_container[name_key]
        if name not in pod_conf:
            continue
        ports = pod_conf[name].get(ports_key)
        db_ports = db_container.get(ports_key)
        if not (ports and db_ports):
            continue
        container_ports_map = {
            item.get(container_port_key): item for item in ports
            if item.get(container_port_key)
        }
        for port in db_ports:
            container_port = port.get(container_port_key)
            src_port = container_ports_map.get(container_port)
            if not src_port:
                continue
            src_port[is_public_key] = port.get(is_public_key, False)
            if protocol_key in src_port:
                src_port[protocol_key] = src_port[protocol_key].lower()
            if src_port.get(host_port_key):
                continue
            if host_port_key in port:
                src_port[host_port_key] = port[host_port_key]
    return pod_containers


def restore_fake_volume_mounts(k8s_containers, kd_containers):
    """Just appends volumeMounts existing in KD and missed in k8s
    containers.
    """
    name_to_kd_containers = {item['name']: item for item in kd_containers}
    for container in k8s_containers:
        kd_container = name_to_kd_containers.get(container['name'], None)
        if kd_container is None:
            continue
        vol_mounts = container.get('volumeMounts', [])
        k8s_vm_names = {item['name'] for item in vol_mounts}
        for vm in kd_container.get('volumeMounts', []):
            if vm['name'] not in k8s_vm_names:
                vol_mounts.append(vm)
        if vol_mounts:
            container['volumeMounts'] = vol_mounts


def extract_secrets(containers):
    """Get set of secrets from list of containers."""
    secrets = set()  # each item is tuple: (username, password, full_registry)
    for container in containers:
        secret = container.pop('secret', None)
        if secret is not None:
            secrets.add((secret['username'], secret['password'],
                         Image(container['image']).full_registry))
    return secrets


def fix_relative_mount_paths(containers):
    """
    Convert relative mount paths in list of container into absolute ones.

    Relative mountPaths in docker are relative to the /.
    It's not documented and sometimes relative paths may cause
    bugs in kd or k8s (for now localStorage doesn't work in
    some cases). So, we convert relative path to the
    corresponding absolute path. In future docker may change
    the way how relative mountPaths treated,
    see https://github.com/docker/docker/issues/20988
    """
    for container in containers:
        for mount in container.get('volumeMounts') or []:
            mount['mountPath'] = path.abspath(
                path.join('/', mount['mountPath']))
