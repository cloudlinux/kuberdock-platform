import json
from uuid import uuid4
from base64 import urlsafe_b64encode, urlsafe_b64decode
from flask import current_app

from . import pd_utils
from .pod import Pod
from .images import Image
from .pstorage import CephStorage, AmazonStorage, NodeCommandError
from .helpers import KubeQuery, ModelQuery, Utilities
from ..core import db
from ..billing import repr_limits, Kube
from ..pods.models import PersistentDisk, PodIP, Pod as DBPod
from ..users.models import User
from ..utils import (run_ssh_command, send_event, APIError, POD_STATUSES,
                     unbind_ip)
from ..settings import (KUBERDOCK_INTERNAL_USER, TRIAL_KUBES, KUBE_API_VERSION,
                        DEFAULT_REGISTRY, AWS)
DOCKERHUB_INDEX = 'https://index.docker.io/v1/'


def get_user_namespaces(user):
    return {pod.namespace for pod in user.pods if not pod.is_deleted}


class PodCollection(KubeQuery, ModelQuery, Utilities):

    def __init__(self, owner=None):
        """
        :param owner: User model instance
        """
        self.owner = owner
        namespaces = self._get_namespaces()
        self._get_pods(namespaces)
        self._merge()

    def add(self, params, skip_check=False):  # TODO: celery
        secrets = set()  # username, password, full_registry
        for container in params['containers']:
            secret = container.pop('secret', None)
            if secret is not None:
                secrets.add((secret['username'], secret['password'],
                             Image(container['image']).full_registry))
        secrets = sorted(secrets)

        if not skip_check:
            self._check_trial(params)
            Image.check_images_availability(
                [container['image'] for container in params['containers']], secrets)

        params['namespace'] = params['id'] = str(uuid4())
        params['owner'] = self.owner
        pod = Pod.create(params)
        pod.compose_persistent(self.owner)
        self._make_namespace(pod.namespace)
        pod.secrets = [self._make_secret(pod.namespace, *secret)
                       for secret in secrets]
        set_public_ip = self.needs_public_ip(params)
        if set_public_ip:
            db_pod = self._save_pod(pod, set_public_ip)
            if getattr(db_pod, 'public_ip', None):
                pod.public_ip = db_pod.public_ip
            if getattr(db_pod, 'public_aws', None):
                pod.public_aws = db_pod.public_aws
        else:
            self._save_pod(pod, set_public_ip)
        pod._forge_dockers()
        return pod.as_dict()

    def get(self, as_json=True):
        if self.owner is None:
            pods = [p.as_dict() for p in self._collection.values()]
        else:
            pods = [p.as_dict() for p in self._collection.values() if getattr(p, 'owner', '') == self.owner.username]
        if as_json:
            return json.dumps(pods)
        return pods

    def get_by_id(self, pod_id, as_json=False):
        try:
            pod = [p for p in self._collection.values() if p.id == pod_id][0]
            if as_json:
                return pod.as_json()
            return pod
        except IndexError:
            self._raise("No such item", 404)

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
    def _set_public_ip(pod, set_public_ip):
        if set_public_ip:
            conf = pod.get_dbconfig()
            if AWS:
                pod.public_aws = True
                conf['public_aws'] = pod.public_aws
            else:
                pod.public_ip = str(PodIP.allocate_ip_address(pod.id))
                conf['public_ip'] = pod.public_ip
            pod.set_dbconfig(conf, False)
            db.session.add(pod)

    def _save_pod(self, obj, set_public_ip):
        kube_type = getattr(obj, 'kube_type', Kube.get_default_kube_type())
        template_id = getattr(obj, 'kuberdock_template_id', None)
        for i in 'kuberdock_template_id', 'owner':
            # to prevent save to config
            if hasattr(obj, i):
                delattr(obj, i)
        pod = DBPod(name=obj.name, config=json.dumps(vars(obj)), id=obj.id,
                    status=POD_STATUSES.stopped, template_id=template_id)
        kube = db.session.query(Kube).get(kube_type)
        if kube is None:
            kube = Kube.get_default_kube()
        if not kube.is_public():
            if not self.owner or self.owner.username != KUBERDOCK_INTERNAL_USER:
                raise APIError('Forbidden kube type for a pods')
        pod.kube = kube
        pod.owner = self.owner
        try:
            db.session.add(pod)
            self._set_public_ip(pod, set_public_ip)
            db.session.commit()
            return pod
        except Exception as e:
            current_app.logger.debug(e.__repr__())
            db.session.rollback()
            # Raise APIError because else response will be 200
            # and backbone creates new model even in error case
            raise APIError(str(e))

    def update(self, pod_id, data):
        pod = self.get_by_id(pod_id)
        command = data.get('command')
        if command is None:
            return
        dispatcher = {
            'start': self._start_pod,
            'stop': self._stop_pod,
            'resize': self._resize_replicas,
            'container_start': self._container_start,
            'container_stop': self._container_stop,
            'container_delete': self._container_delete}
        if command in dispatcher:
            return dispatcher[command](pod, data)
        self._raise("Unknown command")

    def delete(self, pod_id, force=False):
        pod = self.get_by_id(pod_id)
        if pod.owner == KUBERDOCK_INTERNAL_USER and not force:
            self._raise('Service pod cannot be removed')
        self._stop_pod(pod, raise_=False)

        service_name = pod.get_config('service')
        if service_name:
            service = self._get(['services', service_name], ns=pod.namespace)
            state = json.loads(service.get('metadata', {}).get('annotations', {}).get('public-ip-state', '{}'))
            if state.get('assigned-to'):
                unbind_ip(service_name, state, service, 0, current_app)
            rv = self._del(['services', service_name], ns=pod.namespace)
            self._raise_if_failure(rv, "Could not remove a service")

        if hasattr(pod, 'public_ip'):
            pod._free_ip(pod_id=pod_id)
        rv = self._drop_namespace(pod.namespace)
        # current_app.logger.debug(rv)
        self._mark_pod_as_deleted(pod_id)

    def check_updates(self, pod_id, container_name):
        """
        Check if image in registry differs from image in kubernetes

        :raise APIError: if pod not found or container not found in pod
            or image not found in registry
        """
        pod = self.get_by_id(pod_id)
        try:
            container = (c for c in pod.containers
                         if c['name'] == container_name).next()
        except StopIteration:
            raise APIError('Container with id {0} not found'.format(container_name))
        image = container['image']
        image_id = container.get('imageID')
        if image_id is None:
            return False
        image_id_in_registry = Image(image).get_id(self._get_secrets(pod))
        if image_id_in_registry is None:
            raise APIError('Image not found in registry')
        return image_id != image_id_in_registry

    def update_container(self, pod_id, container_name):
        """
        Update container image by restarting the pod.

        :raise APIError: if pod not found or if pod is not running
        """
        pod = self.get_by_id(pod_id)
        self._stop_pod(pod)
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

    def _make_secret(self, namespace, username, password, registry=DEFAULT_REGISTRY):
        # only index.docker.io in .dockercfg allowes to use
        # image url without the registry, like wncm/mynginx
        if registry.endswith('docker.io'):
            registry = DOCKERHUB_INDEX
        auth = urlsafe_b64encode('{0}:{1}'.format(username, password))
        secret = urlsafe_b64encode('{{"{0}": {{"auth": "{1}", "email": "a@a.a" }}}}'
                                   .format(registry, auth))

        name = str(uuid4())
        config = {'apiVersion': KUBE_API_VERSION,
                  'kind': 'Secret',
                  'metadata': {'name': name, 'namespace': namespace},
                  'data': {'.dockercfg': secret},
                  'type': 'kubernetes.io/dockercfg'}

        rv = self._post(['secrets'], json.dumps(config), rest=True, ns=namespace)
        if rv['kind'] == 'Status' and rv['status'] == 'Failure':
            raise APIError(rv['message'])
        return name

    def _get_secrets(self, pod):
        """
        Retrieve from kubernetes all secrets attached to the pod.

        :param pod: pod
        :returns: list of secrets. Each secret is a tuple (username, password, registry)
        """
        secrets = []
        for secret in pod.secrets:
            rv = self._get(['secrets', secret], ns=pod.namespace)
            if rv['kind'] == 'Status':
                raise APIError(rv['message'])
            dockercfg = json.loads(urlsafe_b64decode(str(rv['data']['.dockercfg'])))
            for registry, data in dockercfg.iteritems():
                username, password = urlsafe_b64decode(str(data['auth'])).split(':', 1)
                # only index.docker.io in .dockercfg allowes to use image url without
                # the registry, like wncm/mynginx. Replace it back to default registry
                if registry == DOCKERHUB_INDEX:
                    registry = DEFAULT_REGISTRY
                secrets.append((username, password, registry))
        return secrets

    def _get_namespace(self, namespace):
        data = self._get(ns=namespace)
        if data.get('code') == 404:
            return None
        return data

    def _get_namespaces(self):
        data = self._get(['namespaces'], ns=False)
        if self.owner is None:
            return [i['metadata']['name'] for i in data['items']]
        namespaces = []
        user_namespaces = get_user_namespaces(self.owner)
        for namespace in data['items']:
            ns_name = namespace.get('metadata', {}).get('name', '')
            if ns_name in user_namespaces:
                namespaces.append(ns_name)
        return namespaces

    def _drop_namespace(self, namespace):
        rv = self._del(['namespaces', namespace], ns=False)
        self._raise_if_failure(rv, "Cannot delete namespace '{}'".format(namespace))
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

                if name is not None and replica_item['replicaSelector'] != name:
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
        services_data = []
        replicas_data = []

        if namespaces:
            for namespace in namespaces:
                data.extend(self._get(['pods'], ns=namespace)['items'])
                services_data.extend(self._get(['services'], ns=namespace)['items'])
                replicas_data.extend(self._get(['replicationcontrollers'], ns=namespace)['items'])
        else:
            data.extend(self._get(['pods'])['items'])
            services_data.extend(item for item in self._get(['services'])['items']
                                 if item['metadata']['namespace'] != 'default')
            replicas_data.extend(self._get(['replicationcontrollers'])['items'])

        for item in data:
            pod = Pod.populate(item)

            for s in services_data:
                if self._is_related(item['metadata']['labels'], s['spec'].get('selector')):
                    pod.podIP = s['spec'].get('clusterIP')
                    break

            for r in replicas_data:
                if self._is_related(item['metadata']['labels'], r['spec']['selector']):
                    # If replication controller manages more then one pod,
                    # _get_pods must return only one of them (we will filter by sid)
                    pod.sid = r['metadata']['name']
                    pod.replicas = r['spec']['replicas']
                    break
            else:
                pod.replicas = 1
                current_app.logger.warn('Pod doesn\'t have Replication Controller:'
                                        '{0}'.format(item))

            if pod.sid not in pod_index:
                self._collection[pod.id, pod.namespace] = pod
                pod_index.add(pod.sid)

    def _merge(self):
        """ Merge pods retrieved from kubernates api with data from DB """
        db_pods = self._fetch_pods(users=True)
        for db_pod in db_pods:
            db_pod_config = json.loads(db_pod.config)
            namespace = db_pod.namespace
            template_id = db_pod.template_id

            if (db_pod.id, namespace) not in self._collection:  # exists in DB only
                pod = Pod(db_pod_config)
                pod.id = db_pod.id
                pod.template_id = template_id
                pod._forge_dockers()
                self._collection[pod.id, namespace] = pod
            else:
                pod = self._collection[db_pod.id, namespace]
                pod.name = db_pod.name
                pod.template_id = template_id
                # TODO if remove _is_related then add podIP attribute here
                # pod.service = json.loads(db_pod.config).get('service')
                pod.volumes_original = db_pod_config.get('volumes_original')
                pod.kube_type = db_pod_config.get('kube_type')

                if db_pod_config.get('public_ip'):
                    pod.public_ip = db_pod_config['public_ip']

                pod.secrets = db_pod_config.get('secrets', [])
                a = pod.containers
                b = db_pod_config.get('containers')
                pod.containers = self.merge_lists(a, b, 'name')
                restore_containers_host_ports_config(pod.containers, b)

            if db_pod_config.get('public_aws'):
                pod.public_aws = db_pod_config['public_aws']

            if not hasattr(pod, 'owner'):
                pod.owner = db_pod.owner.username

            if not hasattr(pod, 'status'):
                pod.status = POD_STATUSES.stopped

            for container in pod.containers:
                container.pop('resources', None)
                container['limits'] = repr_limits(container['kubes'],
                                                  db_pod_config['kube_type'])

    def _run_service(self, pod):
        ports = []
        for ci, c in enumerate(getattr(pod, 'containers', [])):
            for pi, p in enumerate(c.get('ports', [])):
                host_port = p.get('hostPort', None) or p.get('containerPort')
                port_name = 'c{0}-p{1}'.format(ci, pi)
                if p.get('isPublic'):
                    port_name += '-public'
                ports.append({
                    "name": port_name,
                    "port": host_port,
                    "protocol": p.get('protocol', 'TCP').upper(),
                    "targetPort": p.get('containerPort')})

        conf = {
            'kind': 'Service',
            'apiVersion': KUBE_API_VERSION,
            'metadata': {
                # 'generateName': pod.name.lower() + '-service-',
                'generateName': 'service-',
                'labels': {'name': pod.id[:54] + '-service'},
                'annotations': {
                    'public-ip-state': json.dumps({
                        'assigned-public-ip': getattr(pod, 'public_ip',
                                                      getattr(pod, 'public_aws', None))
                    })
                },
            },
            'spec': {
                'selector': {'kuberdock-pod-uid': pod.id},
                'ports': ports,
                'type': 'ClusterIP',
                'sessionAffinity': 'None'   # may be ClientIP is better
            }
        }
        if hasattr(pod, 'clusterIP') and pod.clusterIP:
            conf['spec']['clusterIP'] = pod.clusterIP
        return self._post(['services'], json.dumps(conf), rest=True, ns=pod.namespace)

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
        if pod.status == POD_STATUSES.running or \
           pod.status == POD_STATUSES.pending:
            raise APIError("Pod is not stopped, we can't run it")
        if pod.status == POD_STATUSES.succeeded or \
           pod.status == POD_STATUSES.failed:
            self._stop_pod(pod)
        self._make_namespace(pod.namespace)
        db_config = pod.get_config()

        self._process_persistent_volumes(pod, db_config.get('volumes', []))

        if not db_config.get('service'):
            for c in pod.containers:
                if len(c.get('ports', [])) > 0:
                    service_rv = self._run_service(pod)
                    self._raise_if_failure(service_rv, "Could not start a service")
                    db_config['service'] = service_rv['metadata']['name']
                    break

        self.replace_config(pod, db_config)

        config = pod.prepare()
        rv = self._post(['replicationcontrollers'], json.dumps(config),
                        rest=True, ns=pod.namespace)
        self._raise_if_failure(rv, "Could not start '{0}' pod".format(
            pod.name.encode('ascii', 'replace')))
        return {'status': POD_STATUSES.pending}

    def _stop_pod(self, pod, data=None, raise_=True):
        if pod.status != POD_STATUSES.stopped:
            pod.status = POD_STATUSES.stopped
            if hasattr(pod, 'sid'):
                rv = self._del(['replicationcontrollers', pod.sid],
                               ns=pod.namespace)
                self._stop_cluster(pod)
                self._raise_if_failure(rv, "Could not stop a pod")
                # return rv
                return {'status': POD_STATUSES.stopped}
        elif raise_:
            raise APIError('Pod is already stopped')

    def _stop_cluster(self, pod):
        """ Delete all replicas of the pod """
        for p in self._get(['pods'], ns=pod.namespace)['items']:
            if self._is_related(p['metadata']['labels'], {'kuberdock-pod-uid': pod.id}):
                self._del(['pods', p['metadata']['name']], ns=pod.namespace)

    def _do_container_action(self, action, data):
        host = data.get('nodeName')
        if not host:
            return
        rv = {}
        containers = data.get('containers', '').split(',')
        for container in containers:
            command = 'docker {0} {1}'.format(action, container)
            status, message = run_ssh_command(host, command)
            if status != 0:
                self._raise('Docker error: {0} ({1}).'.format(message, status))
            if action in ('start', 'stop'):
                send_event('pull_pod_state', message)
            rv[container] = message or 'OK'
        return rv

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
            if 'rbd' in v:
                storage = CephStorage()
                if not v['rbd'].get('monitors'):
                    v['rbd']['monitors'] = storage.get_monitors()
                drive_name = v['rbd'].get('image')
            elif 'awsElasticBlockStore' in v:
                storage = AmazonStorage()
                drive_name = v['awsElasticBlockStore'].get('drive')
            else:
                continue
            if drive_name is None:
                raise APIError("Got no drive name")

            persistent_disk = PersistentDisk.filter_by(drive_name=drive_name).first()
            if persistent_disk is None:
                name = pd_utils.parse_pd_name(drive_name).drive
                raise APIError('Persistent Disk {0} not found'.format(name), 404)
            drives[drive_name] = (storage, persistent_disk)
        if not drives:
            return

        # check that pod can use all of them
        already_taken = PersistentDisk.take(pod.id, drives.keys())
        if already_taken:
            raise APIError(
                u'For now two pods cannot share one Persistent Disk ({0}). '
                u'Please stop pod "{1}" before starting this one.'
                .format(already_taken.name, already_taken.pod.name))

        # prepare drives
        for drive_name, (storage, persistent_disk) in drives.iteritems():
            storage.create(persistent_disk)
            try:
                vid = storage.makefs(persistent_disk)
            except NodeCommandError:
                msg = (u'Failed to make FS for drive "{0}" because of failed '
                       u'node command'.format(drive_name))
                current_app.logger.exception(msg)
                raise APIError(msg)
            pod._update_volume_path(v['name'], vid)

    def _container_start(self, pod, data):
        self._do_container_action('start', data)

    def _container_stop(self, pod, data):
        self._do_container_action('stop', data)

    def _container_delete(self, pod, data):
        self._do_container_action('rm', data)

    @staticmethod
    def _is_related(labels, selector):
        """
        Check that pod with labels is related to selector
        https://github.com/kubernetes/kubernetes/blob/master/docs/user-guide/labels.md#label-selectors
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


def restore_containers_host_ports_config(pod_containers, db_containers):
    """Updates 'hostPort' parameters in ports list of containers list.
    This parameters for usual pods (all users' pods) is not sending to
    kubernetes, it is treated as service port. So when we will get container
    list from kubernetes there will be no any 'hostPort' parameters.
    This function tries to restore that, so an user will see that parameters in
    client interface. 'hostPort' is stored in Pod's database config.
    If kubernetes will return 'hostPort' for some pods (it is explicitly set for
    internal service pods), then leave it as is.
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
