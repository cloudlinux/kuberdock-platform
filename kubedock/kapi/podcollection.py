import json
from collections import defaultdict
from crypt import crypt
from os import path
from uuid import uuid4

from celery.exceptions import MaxRetriesExceededError
from flask import current_app

import helpers
import ingress_resource
import licensing
import node_utils
import pod_domains
import podutils
import pstorage
from helpers import KubeQuery, K8sSecretsClient, K8sSecretsBuilder
from images import Image
from kubedock.exceptions import (
    NoFreeIPs, NoSuitableNode, SubsystemtIsNotReadyError, ServicePodDumpError)
from lbpoll import LoadBalanceService
from node import Node as K8SNode
from pod import Pod
from .. import billing
from .. import dns_management
from .. import settings
from .. import utils
from ..core import db
from ..domains.models import PodDomain
from ..exceptions import APIError, PodStartFailure
from ..kd_celery import celery
from ..nodes.models import Node
from ..pods.models import (
    PersistentDisk, PodIP, IPPool, Pod as DBPod, PersistentDiskStatuses)
from ..system_settings.models import SystemSettings
from ..usage.models import IpState
from ..utils import POD_STATUSES, NODE_STATUSES, KubeUtils

UNKNOWN_ADDRESS = 'Unknown'

# We use only 30 because useradd limits name to 32, and ssh client limits
# name only to 30 (may be this is configurable) so we use lowest possible
# This value is hardcoded in a few ssh-feature related scripts because they
# will be copied to each node at deploy stage
DIRECT_SSH_USERNAME_LEN = 30
DIRECT_SSH_ERROR = "Error retrieving ssh access, please contact administrator"


def _check_license():
    if not licensing.is_valid():
        raise APIError("Action forbidden. Please contact support.")


def _secrets_dict_to_list(d):
    """Takes secrets as dict and convert it to list of tuples.

    Result items has structure (username, password, registry).

    Input dict has following structure:
    {registry:
       {'auth':
          {'username': username,
           'password': password
          }
       },
       ...
    }
    """
    return [(v['auth']['username'], v['auth']['password'], k)
            for k, v in d.iteritems()]


def get_user_namespaces(user):
    return {pod.namespace for pod in user.pods if not pod.is_deleted}


class PodNotFound(APIError):
    message = 'Pod not found'
    status_code = 404


class PodCollection(object):
    def __init__(self, owner=None):
        """
        :param owner: User model instance
        """
        # Original names of pods in k8s {'metadata': 'name'}
        # Pod class store it in 'sid' field, but here it will be replaced with
        # name of pod in replication controller.
        self.pod_names = None
        self.owner = owner
        self.k8squery = KubeQuery()
        namespaces = self._get_namespaces()
        self._get_pods(namespaces)
        self._merge()

    def _preprocess_new_pod(self, params, original_pod=None, skip_check=False):
        """
        Do some trivial checks and changes in new pod data.

        :param params: pod config
        :param original_pod: kapi-Pod object. Provide this if you need to check
            edit, not creation.
        :param skip_check: use it if you trust the source or need to break some
            rules (usually for kuberdock-internal)
        :returns: prepared pod config and list of secrets. Secret is
            a tuple(username, password, registry).
        """
        secrets = extract_secrets(params['containers'])
        if original_pod is not None:
            # use old secrets too, so user won't need to re-enter credentials
            secrets.update(self.get_secrets(original_pod).values())
        secrets = sorted(secrets)

        self._preprocess_containers(params['containers'], secrets, skip_check,
                                    original_pod=original_pod)

        params['owner'] = self.owner

        return params, secrets

    def _preprocess_pod_dump(self, dump, skip_check=False):
        hidden_fields = ['node', 'podIP', 'status', 'db_status', 'k8s_status',
                         'service', 'serviceAccount']

        pod_data = {k: v
                    for k, v in dump['pod_data'].iteritems()
                    if k not in hidden_fields}
        k8s_secrets = dump['k8s_secrets']
        # k8s_secrets has following structure
        # {secret_name:
        #   {registry:
        #     {'auth':
        #        {'username': username,
        #         'password': password
        #        }
        #     },
        #   ...
        #   }
        # }

        # flatten
        secrets = [s
                   for secret_name, secret_dict in k8s_secrets.iteritems()
                   for s in _secrets_dict_to_list(secret_dict)]

        containers = pod_data['containers']

        self._preprocess_containers(containers, secrets, skip_check)

        pod_data['owner'] = self.owner
        return pod_data, secrets

    def _preprocess_containers(self, containers, secrets, skip_check,
                               original_pod=None):
        fix_relative_mount_paths(containers)

        # TODO: with cerberus 0.10 use "default" normalization rule
        for container in containers:
            container.setdefault('sourceUrl',
                                 Image(container['image']).source_url)
            container.setdefault('kubes', 1)

        if not skip_check:
            self._check_trial(containers, original_pod=original_pod)
            Image.check_containers(containers, secrets)

    def _check_status(self, pod_data):
        billing_type = SystemSettings.get_by_name('billing_type').lower()
        if billing_type != 'no billing' and self.owner.fix_price:
            # All pods created by fixed-price users initially must have
            # status "unpaid". Status may be changed later (using command
            # "set").
            pod_data['status'] = POD_STATUSES.unpaid

    def _add_pod(self, data, secrets, skip_check, reuse_pv):
        self._preprocess_volumes(data)

        data['namespace'] = data['id'] = str(uuid4())
        data['sid'] = str(uuid4())  # TODO: do we really need this field?

        if not skip_check:
            self._check_status(data)

        data.setdefault('status', POD_STATUSES.stopped)

        pod = Pod(data)
        pod.check_name()

        # AC-3256 Fix.
        # Wrap {PD models}/{public IP}/{Pod creation} in a db inside
        # a single db transaction, i.e. if anything goes wrong - rollback.
        with utils.atomic():
            # create PD models in db and change volumes schema in config
            pod.compose_persistent(reuse_pv=reuse_pv)
            set_public_ip = self.needs_public_ip(data)
            db_pod = self._save_pod(pod)
            if set_public_ip:
                if getattr(db_pod, 'public_ip', None):
                    pod.public_ip = db_pod.public_ip
                if getattr(db_pod, 'public_aws', None):
                    pod.public_aws = db_pod.public_aws
                if getattr(db_pod, 'domain', None):
                    pod.domain = db_pod.domain
            pod.forge_dockers()

        namespace = pod.namespace

        self._make_namespace(namespace)

        secret_ids = self._save_k8s_secrets(secrets, namespace)
        pod.secrets = secret_ids

        pod_config = db_pod.get_dbconfig()
        pod_config['secrets'] = pod.secrets
        # Update config
        db_pod.set_dbconfig(pod_config, save=True)
        return pod.as_dict()

    def add(self, params, skip_check=False, reuse_pv=True):  # TODO: celery
        if not skip_check:
            _check_license()

        params, secrets = self._preprocess_new_pod(
            params, skip_check=skip_check)

        return self._add_pod(params, secrets, skip_check, reuse_pv)

    def add_from_dump(self, dump, skip_check=False):
        if not skip_check:
            _check_license()

        pod_data, secrets = self._preprocess_pod_dump(dump, skip_check)

        return self._add_pod(pod_data, secrets, skip_check, reuse_pv=False)

    def _save_k8s_secrets(self, secrets, namespace):
        """Save secrets to k8s.
        :param secrets: List of tuple(username, password, registry)
        :param namespace: Namespace
        :return: List of secrets ids.
        """
        secrets_client = K8sSecretsClient(self.k8squery)
        secrets_builder = K8sSecretsBuilder

        secret_ids = []
        for secret in secrets:
            secret_data = secrets_builder.build_secret_data(*secret)
            secret_id = str(uuid4())

            try:
                secrets_client.create(secret_id, secret_data, namespace)
            except secrets_client.ErrorBase as e:
                raise APIError('Cannot save k8s secrets due to: %s'
                               % e.message)

            secret_ids.append(secret_id)
        return secret_ids

    def _preprocess_volumes(self, params):
        params.setdefault('volumes', [])
        storage_cls = pstorage.get_storage_class()
        if storage_cls:
            persistent_volumes = [vol for vol in params['volumes']
                                  if 'persistentDisk' in vol]
            is_compatible, pinned_node_name = \
                storage_cls.are_pod_volumes_compatible(
                    persistent_volumes, self.owner.id, params)
            if not is_compatible:
                raise APIError("Invalid combination of persistent disks")
            if pinned_node_name is not None:
                params['node'] = pinned_node_name

    @utils.atomic(nested=False)
    def edit(self, original_pod, data, skip_check=False):
        """
        Preprocess and add new pod config in db.
        New config will be applied on the next manual restart.

        :param original_pod: kubedock.kapi.pod.Pod
        :param data: see command_pod_schema and edited_pod_config_schema
            in kubedock.validation
        """
        new_pod_data = data.get('edited_config')
        original_db_pod = DBPod.query.get(original_pod.id)
        original_db_pod_config = original_db_pod.get_dbconfig()

        if new_pod_data is None:
            original_db_pod.set_dbconfig(
                dict(original_db_pod_config, edited_config=None), save=False)
            original_pod.edited_config = None
            return original_pod.as_dict()

        data, secrets = self._preprocess_new_pod(
            new_pod_data, original_pod=original_pod, skip_check=skip_check)

        pod = Pod(dict(new_pod_data, **{
            key: original_db_pod_config[key]
            for key in ('namespace', 'id', 'sid')
            if key in original_db_pod_config}))
        # create PD models in db and change volumes schema in config
        pod.compose_persistent()

        # get old secrets, like mapping {secret: id-of-the-secret-in-k8s}
        exist = {v: k for k, v in self.get_secrets(original_pod).iteritems()}
        # create missing secrets in k8s and add IDs in config
        secrets_to_create = set(secrets) - set(exist.keys())
        new_ids = self._save_k8s_secrets(secrets_to_create, pod.namespace)
        pod.secrets = sorted(new_ids + exist.values())

        # add in kapi-Pod
        original_pod.edited_config = vars(pod).copy()
        original_pod.edited_config.pop('owner', None)
        # add in db-Pod config
        original_config = original_db_pod.get_dbconfig()
        original_config['edited_config'] = original_pod.edited_config
        original_db_pod.set_dbconfig(original_config, save=False)

        return original_pod.as_dict()

    def get(self, pod_id=None, as_json=True):
        if pod_id is None:
            pods = [p.as_dict() for p in self._get_owned()]
        else:
            pods = self._get_by_id(pod_id).as_dict()
        if as_json:
            return json.dumps(pods)
        return pods

    def dump(self, pod_id=None):
        """Get full information about pods.
        ATTENTION! Do not use it in methods allowed for user! It may contain
        secret information. FOR ADMINS ONLY!
        """
        if pod_id is None:
            return self._dump_all()
        else:
            return self._dump_one(pod_id)

    def _dump_all(self):
        if self.owner is None:
            rv = [pod.dump() for pod in self._get_owned()
                  if not pod.owner.is_internal()]
        else:
            # a little optimization. All pods have the same owner,
            # so check once
            if self.owner.is_internal():
                raise ServicePodDumpError
            rv = [pod.dump() for pod in self._get_owned()]
        return rv

    def _dump_one(self, pod_id):
        # check for internal user performed in the pod
        return self._get_by_id(pod_id).dump()

    def _get_by_id(self, pod_id):
        try:
            if self.owner is None:
                pod = (p for p in self._collection.values()
                       if p.id == pod_id).next()
            else:
                pod = (p for p in self._collection.values()
                       if p.id == pod_id and
                       p.owner.id == self.owner.id).next()
        except StopIteration:
            raise PodNotFound()
        return pod

    def _get_owned(self):
        """:rtype: list[Pod]"""
        if self.owner is None:
            pods = [p for p in self._collection.values()]
        else:
            owner_id = self.owner.id
            pods = [p for p in self._collection.values()
                    if p.owner.id == owner_id]
        return pods

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
    @utils.atomic()
    def _prepare_for_public_address(pod, config=None):
        """Prepare pod for Public IP assigning"""
        conf = pod.get_dbconfig() if config is None else config
        public_ip = conf.get('public_ip')
        if public_ip:
            ip_address = IPPool.get_free_host(as_int=True, ip=public_ip)
            if ip_address is None:
                raise NoFreeIPs
        if public_ip or not PodCollection.needs_public_ip(conf):
            conf.pop('domain', None)
            return
        domain_name = conf.get('domain', None)
        if domain_name is None:
            if settings.AWS:
                conf.setdefault('public_aws', UNKNOWN_ADDRESS)
            else:
                ip_address = IPPool.get_free_host(as_int=True)
                if ip_address is None:
                    raise NoFreeIPs()
                # 'true' indicates that this Pod needs Public IP to be assigned
                conf['public_ip'] = pod.public_ip = 'true'
        else:
            ready, message = dns_management.is_domain_system_ready()
            if not ready:
                raise SubsystemtIsNotReadyError(
                    u'Trying to use domain for pod, while DNS is '
                    u'misconfigured: {}'.format(message),
                    response_message=(
                        u'DNS management system is misconfigured. '
                        u'Please, contact administrator.')
                )
            domain = pod_domains.check_domain(domain_name)
            pod_domain = pod_domains.set_pod_domain(pod, domain.id)
            conf['domain'] = pod.domain = u'{}.{}'.format(
                pod_domain.name, domain.name)
        if config is None:
            pod.set_dbconfig(conf, save=False)

    @utils.atomic()
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
    @utils.atomic()
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
                query = query.filter_by(ip_address=utils.ip2int(ip))
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

        network = IPPool.query.filter_by(network=ip.network).first()
        node = network.node
        if current_app.config['NONFLOATING_PUBLIC_IPS'] and node:
            K8SNode(hostname=node.hostname).increment_free_public_ip_count(1)

        IpState.end(pod_id, ip.ip_address)
        db.session.delete(ip)

    @staticmethod
    @utils.atomic(nested=False)
    def unbind_publicIP(pod_id):
        """Temporary unbind publicIP, on next pod start publicIP will be
        reassigned. Unbinded publicIP saved in pod config as
        public_ip_before_freed.

        """
        ip = PodIP.query.filter_by(pod_id=pod_id).first()
        if ip is None:
            return

        pod = ip.pod
        pod_config = pod.get_dbconfig()
        if pod.status not in (POD_STATUSES.stopped, POD_STATUSES.unpaid):
            raise APIError("We can unbind ip only on stopped pod")
        pod_config['public_ip_before_freed'] = pod_config.pop('public_ip',
                                                              None)
        pod_config['public_ip'] = 'true'
        pod.set_dbconfig(pod_config, save=False)

        network = IPPool.query.filter_by(network=ip.network).first()
        node = network.node
        if current_app.config['NONFLOATING_PUBLIC_IPS'] and node:
            K8SNode(hostname=node.hostname).increment_free_public_ip_count(1)

        IpState.end(pod_id, ip.ip_address)
        db.session.delete(ip)
        utils.send_event_to_user('pod:change', {'id': pod_id}, pod.owner_id)

    @classmethod
    @utils.atomic()
    def _return_public_ip(cls, pod_id):
        """
        If pod had public IP, and it was removed, return it back to the pod.

        For more info see `_remove_public_ip` docs.
        """
        pod = DBPod.query.get(pod_id)
        pod_config = pod.get_dbconfig()

        if pod_config.pop('public_ip_before_freed', None) is None:
            return

        if pod_config.get('domain') is not None:
            return

        for container in pod_config['containers']:
            for port in container['ports']:
                port['isPublic'] = port.pop('isPublic_before_freed', None)
        pod.set_dbconfig(pod_config, save=False)
        cls._prepare_for_public_address(pod)

    @utils.atomic()
    def _save_pod(self, obj, db_pod=None):
        """
        Save pod data to db.

        :param obj: kapi-Pod
        :param db_pod: update existing db-Pod
        """
        template_id = getattr(obj, 'kuberdock_template_id', None)
        template_plan_name = getattr(obj, 'kuberdock_plan_name', None)
        status = getattr(obj, 'status', POD_STATUSES.stopped)
        excluded = (  # duplicates of model's fields
            'kuberdock_template_id', 'kuberdock_plan_name',
            'owner', 'kube_type', 'status', 'id', 'name')
        data = {k: v for k, v in vars(obj).iteritems() if k not in excluded}
        if db_pod is None:
            db_pod = DBPod(name=obj.name, config=json.dumps(data), id=obj.id,
                           status=status, template_id=template_id,
                           template_plan_name=template_plan_name,
                           kube_id=obj.kube_type, owner=self.owner)
            db.session.add(db_pod)
        else:
            db_pod.config = json.dumps(data)
            db_pod.status = status
            db_pod.kube_id = obj.kube_type
            db_pod.owner = self.owner

        self._prepare_for_public_address(db_pod)
        return db_pod

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

            # NOTE: the next three commands may look similar, but they do
            #   completely defferent things. Maybe we need to rename some of
            #   them, or change outer logic to reduce differences to merge
            #   a few commands into one.

            # immediately update confing in db and k8s.ReplicationController
            # currently, it's used only for binding pod with LS to current node
            'change_config': self._change_pod_config,
            # immediately set DB data
            # currently, it's used for changing status, name, postDescription
            'set': self._set_entry,
            # add new pod config that will be applied after next manual restart
            'edit': self.edit,
            'unbind-ip': self._unbind_ip,
        }
        if command in dispatcher:
            return dispatcher[command](pod, data)
        podutils.raise_("Unknown command")

    def delete(self, pod_id, force=False):
        pod = self._get_by_id(pod_id)

        if pod.owner.username == settings.KUBERDOCK_INTERNAL_USER \
                and not force:
            podutils.raise_('Service pod cannot be removed', 400)

        pod.set_status(POD_STATUSES.deleting, send_update=True, force=True)

        PersistentDisk.free(pod.id)
        # we remove service also manually
        service_name = helpers.get_pod_config(pod.id, 'service')
        if service_name:
            rv = self.k8squery.delete(
                ['services', service_name], ns=pod.namespace
            )
            podutils.raise_if_failure(rv, "Could not remove a service")

        if hasattr(pod, 'public_ip'):
            self._remove_public_ip(pod_id=pod_id)
        if hasattr(pod, 'domain'):
            ok, message = dns_management.delete_type_A_record(pod.domain)
            if not ok:
                current_app.logger.error(
                    u'Failed to delete A DNS record for pod "{}": {}'
                    .format(pod.id, message))
                utils.send_event_to_role(
                    'notify:error', {'message': message}, 'Admin')
        # all deleted asynchronously, now delete namespace, that will ensure
        # delete all content
        self._drop_namespace(pod.namespace)
        helpers.mark_pod_as_deleted(pod_id)
        PodDomain.query.filter_by(pod_id=pod_id).delete()

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
        secrets = self.get_secrets(pod).values()
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
                "apiVersion": settings.KUBE_API_VERSION,
                "metadata": {"name": namespace}}
            self.k8squery.post(
                ['namespaces'], json.dumps(config), rest=True, ns=False)
            # TODO where raise ?
            # current_app.logger.debug(rv)

    @staticmethod
    def get_secrets(pod):
        """
        Retrieve from kubernetes all secrets attached to the pod.

        :param pod: kubedock.kapi.pod.Pod
        :returns: mapping of secrets name to (username, password, registry)
        """
        pod_secrets = pod.get_secrets()
        return {k: _secrets_dict_to_list(v)[0]
                for k, v in pod_secrets.iteritems()}

    def _get_namespace(self, namespace):
        data = self.k8squery.get(ns=namespace)
        if data.get('code') == 404:
            return None
        return data

    def _get_namespaces(self):
        data = self.k8squery.get(['namespaces'], ns=False)
        namespaces = [i['metadata']['name'] for i in data.get('items', {})]
        if self.owner is None:
            return namespaces
        user_namespaces = get_user_namespaces(self.owner)
        return [ns for ns in namespaces if ns in user_namespaces]

    def _drop_namespace(self, namespace):
        rv = self.k8squery.delete(['namespaces', namespace], ns=False)
        podutils.raise_if_failure(rv, "Cannot delete namespace '{}'".format(
            namespace))
        return rv

    def _get_replicas(self, name=None):
        # TODO: apply namespaces here
        replicas = []
        data = self.k8squery.get(['replicationControllers'])

        for item in data['items']:
            try:
                replica_item = {
                    'id': item['uid'],
                    'sid': item['id'],
                    'replicas': item['currentState']['replicas'],
                    'replicaSelector': item['desiredState']['replicaSelector'],
                    'name': item['labels']['kuberdock-pod-uid']}

                if name is not None \
                        and replica_item['replicaSelector'] != name:
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
                data.extend(self.k8squery.get(['pods'], ns=namespace)['items'])
                replicas = self.k8squery.get(
                    ['replicationcontrollers'], ns=namespace)
                replicas_data.extend(replicas['items'])
        else:
            pods = self.k8squery.get(['pods'])
            data.extend(pods.get('items', {}))
            replicas = self.k8squery.get(['replicationcontrollers'])
            replicas_data.extend(replicas.get('items', {}))

        pod_names = defaultdict(set)

        for item in data:
            pod = Pod.populate(item)
            self.update_public_address(pod)
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

    def update_public_address(self, pod):
        """Check if public address not set and try to get it from
        services. Update public address if found one.
        """
        if settings.AWS:
            if getattr(pod, 'public_aws', UNKNOWN_ADDRESS) == UNKNOWN_ADDRESS:
                dns = LoadBalanceService().get_dns_by_pods(pod.id)
                if pod.id in dns:
                    set_public_address(dns[pod.id], pod.id)

    def _merge(self):
        """ Merge pods retrieved from kubernetes api with data from DB """
        db_pods = helpers.fetch_pods(users=True)
        for db_pod in db_pods:
            db_pod_config = json.loads(db_pod.config)
            namespace = db_pod.namespace

            # exists in DB only
            if (db_pod.id, namespace) not in self._collection:
                pod = Pod(db_pod_config)
                pod.id = db_pod.id
                # Now pod status 'stopping' is changed to 'stopped' only by
                # 'DELETED' event in listeners. If we have missed such event
                # for any reason, then the pod will be in status 'stopping'
                # forever. So, If we have met pod in DB with status 'stopping'
                # and this pod is absent in k8s, then set proper status
                # to DB record.
                if db_pod.status == POD_STATUSES.stopping:
                    pod.set_status(POD_STATUSES.stopped)
                pod.forge_dockers()
                self._collection[pod.id, namespace] = pod
            else:
                pod = self._collection[db_pod.id, namespace]
                pod.volumes_public = db_pod_config.get('volumes_public')
                pod.node = db_pod_config.get('node')
                pod.podIP = db_pod_config.get('podIP')
                pod.service = db_pod_config.get('service')
                pod.postDescription = db_pod_config.get('postDescription')
                pod.edited_config = db_pod_config.get('edited_config')

                if db_pod_config.get('public_ip'):
                    pod.public_ip = db_pod_config['public_ip']
                if db_pod_config.get('public_aws'):
                    pod.public_aws = db_pod_config['public_aws']
                if db_pod_config.get('domain'):
                    pod.domain = db_pod_config['domain']

                pod.secrets = db_pod_config.get('secrets', [])
                a = pod.containers
                b = db_pod_config.get('containers')
                restore_fake_volume_mounts(a, b)
                pod.containers = podutils.merge_lists(a, b, 'name')
                restore_containers_host_ports_config(pod.containers, b)

            pod.name = db_pod.name
            pod.set_owner(db_pod.owner)
            pod.template_id = db_pod.template_id
            pod.template_plan_name = db_pod.template_plan_name
            pod.kube_type = db_pod.kube_id
            pod.db_status = db_pod.status
            pod.direct_access = (json.loads(db_pod.direct_access)
                                 if db_pod.direct_access else None)

            if pod.db_status in (POD_STATUSES.preparing,
                                 POD_STATUSES.stopping,
                                 POD_STATUSES.deleting):
                # if we have one of those statuses in DB,
                # use it as common status
                pod.status = pod.db_status
            else:  # otherwise status in k8s is more important
                pod.status = pod.k8s_status or pod.db_status

            for container in pod.containers:
                if container['state'] == 'terminated':
                    if container.get('exitCode') == 0:
                        container['state'] = 'succeeded'
                    else:
                        container['state'] = 'failed'
                container.pop('resources', None)
                container['limits'] = billing.repr_limits(container['kubes'],
                                                          pod.kube_type)

    def _resize_replicas(self, pod, data):
        # FIXME: not working for now
        number = int(data.get('replicas', getattr(pod, 'replicas', 0)))
        replicas = self._get_replicas(pod.id)
        # TODO check replica numbers and compare to ones set in config
        for replica in replicas:
            rv = self.k8squery.put(
                ['replicationControllers', replica.get('id', '')],
                json.loads({'desiredState': {'replicas': number}}))
            podutils.raise_if_failure(rv, "Could not resize a replica")
        return len(replicas)

    @utils.atomic()
    def _apply_edit(self, pod, db_pod, db_config):
        if db_config.get('edited_config') is None:
            return pod, db_config

        old_pod = pod
        db_config = db_config['edited_config']
        db_config['podIP'] = getattr(old_pod, 'podIP', None)
        db_config['service'] = getattr(old_pod, 'service', None)
        db_config['postDescription'] = getattr(
            old_pod, 'postDescription', None)
        db_config['public_ip'] = getattr(old_pod, 'public_ip', None)
        db_config['public_aws'] = getattr(old_pod, 'public_aws', None)

        # re-check images, PDs, etc.
        db_config, _ = self._preprocess_new_pod(
            db_config, original_pod=old_pod)

        pod = Pod(db_config)
        pod.id = db_pod.id
        pod.set_owner(db_pod.owner)
        update_service(pod)
        self._save_pod(pod, db_pod=db_pod)
        if self.needs_public_ip(db_config):
            if getattr(db_pod, 'public_ip', None):
                pod.public_ip = db_pod.public_ip
            elif getattr(db_pod, 'public_aws', None):
                pod.public_aws = db_pod.public_aws
        else:
            self._remove_public_ip(pod_id=db_pod.id)
        pod.name = db_pod.name
        pod.kube_type = db_pod.kube_id
        pod.forge_dockers()
        return pod, db_pod.get_dbconfig()

    @staticmethod
    @utils.atomic()
    def _assign_public_ip(pod, desired_ip=None):
        ip_address = IPPool.get_free_host(as_int=True, ip=desired_ip)
        if desired_ip and ip_address != utils.ip2int(desired_ip):
            # send event 'IP changed'
            send_to_ids = {
                KubeUtils.get_current_user().id,
                pod.owner.id  # can be the same as current user
            }
            msg = ('Please, take into account that IP address of pod '
                   '{pod_name} was changed from {old_ip} to {new_ip}'
                   .format(pod_name=pod.name, old_ip=desired_ip,
                           new_ip=utils.int2ip(ip_address)))
            for user_id in send_to_ids:
                utils.send_event_to_user(
                    event_name='notify:error', data={'message': msg},
                    user_id=user_id)
        network = IPPool.get_network_by_ip(ip_address)

        pod_ip = PodIP.create(pod_id=pod.id, network=network.network,
                              ip_address=ip_address)
        db.session.add(pod_ip)
        rv = str(pod_ip)
        pod.public_ip = rv
        IpState.start(pod.id, pod_ip)
        return rv

    def _start_pod(self, pod, data=None):
        if data is None:
            data = {}
        async_pod_create = data.get('async-pod-create', True)

        if pod.status == POD_STATUSES.unpaid:
            raise APIError("Pod is unpaid, we can't run it")
        if pod.status in (POD_STATUSES.running, POD_STATUSES.pending,
                          POD_STATUSES.preparing):
            raise APIError("Pod is not stopped, we can't run it")
        if not self._node_available_for_pod(pod):
            raise NoSuitableNode()
        if hasattr(pod, 'domain'):
            ok, message = dns_management.is_domain_system_ready()
            if not ok:
                raise SubsystemtIsNotReadyError(
                    message,
                    response_message=u'Pod cannot be started, because DNS '
                                     u'management subsystem is misconfigured. '
                                     u'Please, contact administrator.'
                )

        if pod.status == POD_STATUSES.succeeded \
                or pod.status == POD_STATUSES.failed:
            self._stop_pod(pod, block=True)
        self._make_namespace(pod.namespace)

        command_options = (data or {}).get('commandOptions') or {}
        db_pod = DBPod.query.get(pod.id)
        db_config = db_pod.get_dbconfig()

        if command_options.get('applyEdit'):
            pod, db_config = self._apply_edit(pod, db_pod, db_config)

        pod.set_status(POD_STATUSES.preparing)

        if not current_app.config['NONFLOATING_PUBLIC_IPS']:
            pod_public_ip = getattr(pod, 'public_ip', None)

            if pod_public_ip is not None:
                if pod_public_ip == 'true':
                    desired_ip = None
                else:
                    current_app.logger.warning(
                        'PodIP {0} is already allocated'.format(pod_public_ip))
                    desired_ip = pod_public_ip

                ip = self._assign_public_ip(pod, desired_ip)
                db_config['public_ip'] = ip
                db_pod.set_dbconfig(db_config)

        if async_pod_create:
            prepare_and_run_pod_task.delay(pod)
        else:
            prepare_and_run_pod(pod)
        return pod.as_dict()

    def _stop_pod(self, pod, data=None, raise_=True, block=False):
        # Call PD release in all cases. If the pod was already stopped and PD's
        # were not released, then it will free them. If PD's already free, then
        # this call will do nothing.
        PersistentDisk.free(pod.id)
        if pod.status == POD_STATUSES.stopping and pod.k8s_status is None:
            pod.set_status(POD_STATUSES.stopped, send_update=True)
            return pod.as_dict()
        elif pod.status not in (POD_STATUSES.stopped, POD_STATUSES.unpaid):
            if hasattr(pod, 'sid'):
                pod.set_status(POD_STATUSES.stopping, send_update=True)
                if block:
                    scale_replicationcontroller(pod.id)
                    pod = wait_pod_status(
                        pod.id, POD_STATUSES.stopped,
                        error_message=(
                            u'During restart, Pod "{0}" did not become '
                            u'stopped after a given timeout. It may become '
                            u'later.'.format(pod.name)))
                else:
                    scale_replicationcontroller_task.apply_async((pod.id,))
                return pod.as_dict()
                # FIXME: else: ??? (what if pod has no "sid"?)
        elif raise_:
            raise APIError('Pod is already stopped')

    def _change_pod_config(self, pod, data):
        db_config = helpers.get_pod_config(pod.id)
        utils.update_dict(db_config, data)
        helpers.replace_pod_config(pod, db_config)

        # get pod again after change
        pod = PodCollection()._get_by_id(pod.id)

        config = pod.prepare()
        rv = self.k8squery.put(
            ['replicationcontrollers', pod.sid], json.dumps(config),
            rest=True, ns=pod.namespace
        )
        podutils.raise_if_failure(rv, "Could not change '{0}' pod".format(
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
        rv = self.k8squery.patch(['replicationcontrollers', pod.sid], rcdata,
                                 ns=pod.namespace,
                                 replace_lists=replace_lists)
        podutils.raise_if_failure(rv, "Could not change '{0}' pod RC".format(
            pod.name.encode('ascii', 'replace')))
        # Delete running pods, so the RC will create new pods with updated
        # spec.
        if restart:
            names = self.pod_names.get((pod_id, pod.namespace), [])
            for name in names:
                rv = self.k8squery.delete(['pods', name], ns=pod.namespace)
                podutils.raise_if_failure(
                    rv,
                    "Could not change '{0}' pod".format(
                        pod.name.encode('ascii', 'replace'))
                )
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

    def reset_direct_access_pass(self, pod_id, new_pass=None):
        """Change ssh password to `new_pass` if set, or generate new one.

        :param pod_id: id of pod
        :param new_pass: new pass to set or None to generate new one
        :return: direct_access dict. see :meth:`._direct_access`

        """
        pod = DBPod.filter_by(id=pod_id).first()
        if not pod:
            raise PodNotFound()
        return self._store_direct_access(pod, new_pass)

    def update_direct_access(self, pod):
        """Update direct access attribute to new one.
        Try to use exist password or generate new one.

        :param pod: kapi/pod object
        :return: direct_access dict. see :meth:`._direct_access`

        """
        origin_pass = None
        try:
            origin_pass = json.loads(pod.direct_access)['auth']
        except:
            pass
        return self._store_direct_access(pod, origin_pass)

    def _store_direct_access(self, pod, origin_pass=None, silent=False):
        """Store direct access attributes
        Call :meth:`._direct_access` and store returned attributes.

        :param pod: pod object
        :type pod: kapi/pod object
        :param origin_pass: pass this password to :meth:`._direct_access`
        :return: direct_access dict. see :meth:`._direct_access`

        """
        try:
            direct_access = self._direct_access(pod.id, origin_pass)
        except APIError as e:
            # Level is not error because it's maybe temporary problem on the
            # cluster (node reboot) and we don't want to receive all such
            # events in Sentry
            current_app.logger.warning(
                "Can't update direct access attributes: {}".format(e))
            return

        pod.direct_access = json.dumps(direct_access)
        pod.save()
        if not silent:
            utils.send_event_to_role('pod:change', {'id': pod.id}, 'Admin')
            utils.send_event_to_user('pod:change', {'id': pod.id},
                                     self.owner.id)
        return direct_access

    def _direct_access(self, pod_id, orig_pass=None):
        """
        Setup direct ssh access to all pod containers via creating special unix
        users with randomly generated secure password(one for all containers
        and updated on each call). "Not needed" users will be garbage collected
        by cron script on the node (hourly)

        :param pod_id: Id of desired running pod
        :param orig_pass: password to be used or None to generate new one
        :return: dict with key "auth" which contain generated password and key
                 key "links" with dict of "container_name":"user_name@node_ip"

        """
        k8s_pod = self._get_by_id(pod_id)
        if k8s_pod.status != POD_STATUSES.running:
            raise APIError('Pod is not running. SSH access is impossible')
        node = k8s_pod.hostIP
        if not node:
            raise APIError(
                'Pod is not assigned to node yet, please try later. '
                'SSH access is impossible')
        ssh, err = utils.ssh_connect(node)
        if err:
            # Level is not error because it's maybe temporary problem on the
            # cluster (node reboot) and we don't want to receive all such
            # events in Sentry
            current_app.logger.warning("Can't connect to node")
            raise APIError(DIRECT_SSH_ERROR)

        if not orig_pass:
            orig_pass = utils.randstr(30, secure=True)
        crypt_pass = crypt(orig_pass, utils.randstr(2, secure=True))
        node_external_ip = node_utils.get_external_node_ip(
            node, ssh, APIError(DIRECT_SSH_ERROR))

        clinks = {}
        for c in k8s_pod.containers:
            cname = c.get('name')
            cid = c.get('containerID')
            if not cid:
                clinks[cname] = 'Container is not running'
                continue
            cid = cid[:DIRECT_SSH_USERNAME_LEN]
            self._try_update_ssh_user(ssh, cid, crypt_pass)
            clinks[cname] = '{}@{}'.format(cid, node_external_ip)
        return {'links': clinks, 'auth': orig_pass}

    @staticmethod
    def _try_update_ssh_user(ssh_to_node, user, passwd):
        """
        Tries to update ssh-related unix user on then node. Creates this user
        if not exists
        :param ssh_to_node: already connected to node ssh object
        :param user: unix user name which is for now truncated container_id
        :param passwd: crypted password
        :return: None
        """
        # TODO this path also used in node_install.sh
        update_user_cmd = '/var/lib/kuberdock/scripts/kd-ssh-user-update.sh ' \
                          '{user} {password}'
        try:
            i, o, e = ssh_to_node.exec_command(
                update_user_cmd.format(user=user, password=passwd),
                timeout=20)
            exit_status = o.channel.recv_exit_status()
        except Exception as e:
            # May happens in case of connection lost during operation
            current_app.logger.warning(
                'Looks like connection error to the node: %s', e,
                exc_info=True)
            raise APIError(DIRECT_SSH_ERROR)
        if exit_status != 0:
            current_app.logger.error(
                "Can't update kd-ssh-user on the node. "
                "Exited with: {}, ({}, {})".format(
                    exit_status, i.read(), o.read()))
            raise APIError(DIRECT_SSH_ERROR)

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

    def _check_trial(self, containers, original_pod=None):
        if self.owner.is_trial():
            pods_collection = self.owner.pods
            if original_pod:
                pods_collection = pods_collection\
                    .filter(DBPod.id != original_pod.id)
            user_kubes = sum([pod.kubes for pod in pods_collection
                              if not pod.is_deleted])
            kubes_left = settings.TRIAL_KUBES - user_kubes
            pod_kubes = sum(c['kubes'] for c in containers)
            if pod_kubes > kubes_left:
                podutils.raise_(
                    'Trial User limit is exceeded. '
                    'Kubes available for you: {0}'.format(kubes_left)
                )

    def _node_available_for_pod(self, pod):
        """
        Check if there is an available node for the pod.

        In case of a pinned node make sure the node is running, otherwise
        check if any node with a required kube type is running.

        The check is skipped for service pods.

        :param pod: A pod to check.
        :type pod: kubedock.kapi.pod.Pod
        :returns: True or False
        :rtype: bool
        """
        dbPod = DBPod.query.get(pod.id)
        if dbPod.is_service_pod:
            return True

        # Check the case of a pinned node
        node_hostname = dbPod.pinned_node
        if node_hostname is not None:
            k8snode = Node.get_by_name(node_hostname)
            return node_utils.node_status_running(k8snode)

        nodes_list = node_utils.get_nodes_collection(kube_type=pod.kube_type)
        running_nodes = [node for node in nodes_list
                         if node['status'] == NODE_STATUSES.running]
        return len(running_nodes) > 0

    def _unbind_ip(self, pod, data=None):
        self.unbind_publicIP(pod.id)


def wait_pod_status(pod_id, wait_status, interval=1, max_retries=120,
                    error_message=None):
    """Keeps polling k8s api until pod status becomes as given"""

    def check_status():
        # we need a fresh status
        db.session.expire(DBPod.query.get(pod_id), ['status'])
        pod = PodCollection()._get_by_id(pod_id)
        current_app.logger.debug(
            'Current pod status: {}, wait for {}, pod_id: {}'.format(
                pod.status, wait_status, pod_id))
        if pod.status == wait_status:
            return pod

    return utils.retry(
        check_status, interval, max_retries,
        APIError(error_message or (
            "Pod {0} did not become {1} after a given timeout. "
            "It may become later.".format(pod_id, wait_status)))
    )


@celery.task(bind=True, default_retry_delay=1, max_retries=10)
def wait_for_rescaling_task(self, pod, size):
    rc = get_replicationcontroller(pod.namespace, pod.sid)
    if rc['status']['replicas'] != size:
        try:
            self.retry()
        except MaxRetriesExceededError:
            current_app.logger.error("Can't scale rc: max retries exceeded")


def scale_replicationcontroller(pod_id, size=0):
    """Set new replicas size and wait until replication controller increase or
    decrease real number of pods or max retries exceed
    """
    pc = PodCollection()
    pod = pc._get_by_id(pod_id)
    data = json.dumps({'spec': {'replicas': size}})
    rc = pc.k8squery.patch(
        ['replicationcontrollers', pod.sid], data, ns=pod.namespace)
    podutils.raise_if_failure(rc, "Couldn't set replicas to {}".format(size))

    if rc['status']['replicas'] != size:
        wait_for_rescaling_task.apply_async((pod, size))


@celery.task(ignore_results=True)
def scale_replicationcontroller_task(*args, **kwargs):
    scale_replicationcontroller(*args, **kwargs)


@celery.task(bind=True, ignore_results=True)
def finish_redeploy(self, pod_id, data, start=True):
    db_pod = DBPod.query.get(pod_id)
    pod_collection = PodCollection(db_pod.owner)
    pod = pod_collection._get_by_id(pod_id)
    try:
        pod_collection._stop_pod(pod, block=True)
    except APIError as e:
        utils.send_event_to_user('notify:error', {'message': e.message},
                                 db_pod.owner_id)
        utils.send_event_to_role('notify:error', {'message': e.message},
                                 'Admin')
        return

    command_options = data.get('commandOptions') or {}
    if command_options.get('wipeOut'):
        for volume in pod.volumes_public:
            pd = volume.get('persistentDisk')
            if pd:
                pd = PersistentDisk.get_all_query().filter(
                    PersistentDisk.name == pd['pdName']
                ).first()
                pstorage.delete_drive_by_id(pd.id)

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
            item.get(container_port_key): item
            for item in ports if item.get(container_port_key)
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


def prepare_and_run_pod(pod):
    db_pod = DBPod.query.get(pod.id)
    db_config = db_pod.get_dbconfig()
    try:
        _process_persistent_volumes(pod, db_config.get('volumes', []))

        local_svc, _ = run_service(pod)
        if local_svc:
            db_config['service'] = pod.service = local_svc['metadata']['name']
            db_config['podIP'] = local_svc['spec']['clusterIP']

        helpers.replace_pod_config(pod, db_config)

        config = pod.prepare()
        k8squery = KubeQuery()
        if not _try_to_update_existing_rc(pod, config):
            rc = k8squery.post(['replicationcontrollers'],
                               json.dumps(config), ns=pod.namespace, rest=True)
            err_msg = "Could not start '{0}' pod".format(
                pod.name.encode('ascii', 'replace'))

            podutils.raise_if_failure(
                rc,
                message=err_msg,
                api_error=PodStartFailure(message=err_msg)
            )

        for container in pod.containers:
            # TODO: create CONTAINER_STATUSES
            container['state'] = POD_STATUSES.pending

        if hasattr(pod, 'domain'):
            ok, message = dns_management.create_or_update_type_A_record(
                pod.domain)
            if ok:
                ok, message = ingress_resource.create_ingress(
                    pod.containers, pod.namespace, pod.domain, pod.service)
            if not ok:
                utils.send_event_to_role(
                    'notify:error',
                    {
                        'message': u'Failed to run pod with domain "{}": {}'
                            .format(pod.domain, message)
                    },
                    'Admin'
                )
                pods = PodCollection()
                pods.update(pod.id, {'command': 'stop'})
                raise APIError(
                    u'Failed to create DNS record for pod "{}". '
                    u'Please, contact administrator'.format(pod.name))
    except Exception as err:
        current_app.logger.exception('Failed to run pod: %s', pod)
        if isinstance(err, APIError):
            # We need to update db_pod in case if the pod status was changed
            # since the last retrieval from DB
            db.session.refresh(db_pod)
            if (not isinstance(err, PodStartFailure)
                    or not db_pod.is_deleted()):
                utils.send_event_to_user(
                    'notify:error', {'message': err.message},
                    db_pod.owner_id)
        pod.set_status(POD_STATUSES.stopped, send_update=True)
        raise
    pod.set_status(POD_STATUSES.pending, send_update=True)
    return pod.as_dict()


@celery.task(ignore_results=True)
def prepare_and_run_pod_task(pod):
    return prepare_and_run_pod(pod)


def update_service(pod):
    """Update pod services to new port configuration in pod.
    Patch services if ports changed, delete services if ports deleted.
    If no service already exist, then do nothing, because all services
    will be created on pod start in method run_service

    """
    ports, public_ports = get_ports(pod)
    service = getattr(pod, 'service', None)
    if service:
        local_svc = update_local_ports(service, pod.namespace, ports)
        if local_svc is None:
            pod.service = None
    public_svc = update_public_ports(pod.id, pod.namespace, public_ports)
    if public_svc is None:
        pod.public_aws = None


def update_public_ports(pod_id, namespace, ports):
    k8squery = KubeQuery()
    if settings.AWS:
        services = LoadBalanceService().get_by_pods(pod_id)
        if pod_id in services:
            # TODO: can have several services
            service = services[pod_id]['metadata']['name']
            if ports:
                data = json.dumps({'spec': {'ports': ports}})
                rv = k8squery.patch(
                    ['services', service], data, ns=namespace)
                podutils.raise_if_failure(rv, 'Could not path service')
                return rv
            else:
                rv = k8squery.delete(
                    ['services', service], ns=namespace)
                podutils.raise_if_failure(rv, 'Could not path service')
                return None


def update_local_ports(service, namespace, ports):
    k8squery = KubeQuery()
    if ports:
        data = json.dumps({'spec': {'ports': ports}})
        rv = k8squery.patch(['services', service], data, ns=namespace)
        podutils.raise_if_failure(rv, 'Could not path service')
        return rv
    else:
        rv = k8squery.delete(['services', service], ns=namespace)
        podutils.raise_if_failure(rv, 'Could not path service')
        return None


def get_ports(pod):
    """Return tuple with local and public ports lists
    Args:
        pod (str): kapi/Pod object
    Return: tuple with two lists of local and public ports
    each port is dict with fields: name, port, protocol, targetPort

    """
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
    return ports, public_ports


def run_service(pod):
    """Run all required services for pod, if such services not exist already
    Args:
        pod: kapi/Pod object
    Returns:
        tuple with local and public services
        or None if service allready exist on not needed

    """
    ports, public_ports = get_ports(pod)
    public_svc = ingress_public_ports(pod.id, pod.namespace, public_ports)
    cluster_ip = getattr(pod, 'podIP', None)
    local_svc = ingress_local_ports(pod.id, pod.namespace, ports, cluster_ip)
    return local_svc, public_svc


def ingress_local_ports(pod_id, namespace, ports, cluster_ip=None):
    """Ingress local ports to service
    Args:
        pod_id (str): pod id
        namespace (str): pod namespace
        ports (list): list of ports to ingress, see get_ports
        cluster_ip (str): cluster_ip to use in service. Optional.

    """
    db_pod = DBPod.query.get(pod_id)
    db_config = db_pod.get_dbconfig()
    if not db_config.get('service') and ports:
        conf = {
            'kind': 'Service',
            'apiVersion': settings.KUBE_API_VERSION,
            'metadata': {
                'generateName': 'service-',
                'labels': {'name': pod_id[:54] + '-service'},
            },
            'spec': {
                'selector': {'kuberdock-pod-uid': pod_id},
                'ports': ports,
                'type': 'ClusterIP',
                'sessionAffinity': 'None'  # may be ClientIP is better
            }
        }
        if cluster_ip:
            conf['spec']['clusterIP'] = cluster_ip
        data = json.dumps(conf)
        rv = KubeQuery().post(['services'], data, rest=True, ns=namespace)
        podutils.raise_if_failure(rv, "Could not ingress local ports")
        return rv


def ingress_public_ports(pod_id, namespace, ports):
    """Ingress public ports with cloudprovider specific methods
    Args:
        pod_id (str): pod id
        namespace (str): pod namespace
        ports (list): list of ports to ingress, see get_ports

    """
    if settings.AWS:
        services = LoadBalanceService().get_by_pods(pod_id)
        if not services and ports:
            conf = {
                'kind': 'Service',
                'apiVersion': settings.KUBE_API_VERSION,
                'metadata': {
                    'generateName': 'lbservice-',
                    'labels': {'kuberdock-type': 'public',
                               'kuberdock-pod-uid': pod_id},
                },
                'spec': {
                    'selector': {'kuberdock-pod-uid': pod_id},
                    'ports': ports,
                    'type': 'LoadBalancer',
                    'sessionAffinity': 'None'
                }
            }
            data = json.dumps(conf)
            rv = KubeQuery().post(['services'], data, rest=True, ns=namespace)
            podutils.raise_if_failure(rv, "Could not ingress public ports")
            return rv


def set_public_address(hostname, pod_id, send=False):
    """Update hostname in DB and send event
    """
    pod = DBPod.query.get(pod_id)
    conf = pod.get_dbconfig()
    conf['public_aws'] = hostname
    pod.set_dbconfig(conf)
    if send:
        utils.send_event_to_user('pod:change', {'id': pod_id}, pod.owner_id)
    return hostname


def _process_persistent_volumes(pod, volumes):
    """
    Processes preliminary persistent volume routines (create, attach, mkfs)
    :param pod: object -> a Pod instance
    :param volumes: list -> list of volumes
    """
    # extract PDs from volumes
    drives = {}
    for v in volumes:
        storage_cls = pstorage.get_storage_class_by_volume_info(v)
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
            raise APIError('Persistent Disk {0} not found'.format(drive_name),
                           404)
        drives[drive_name] = (storage, persistent_disk, v['name'])
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

            def make_msg(item):
                return u'PD: {0}, Pod: {1}'.format(item.name, item.pod.name)

            raise APIError(
                u'For now two pods cannot share one Persistent Disk. '
                u'{0}. Stop these pods before starting this one.'.format(
                    '; '.join(make_msg(item) for item in taken_by_another_pod))
            )

        # prepare drives
        try:
            for drive_name, (storage,
                             persistent_disk,
                             pv_name) in drives.iteritems():
                storage.create(persistent_disk)
                vid = storage.makefs(persistent_disk)
                persistent_disk.state = PersistentDiskStatuses.CREATED
                pod._update_volume_path(pv_name, vid)
        except:
            # free already taken drives in case of exception
            free_on_exit = True
            pod.set_status(POD_STATUSES.stopped)
            raise
    finally:
        if free_on_exit and now_taken:
            PersistentDisk.free_drives([d.drive_name for d in now_taken])


def _try_to_update_existing_rc(pod, config):
    """
    Try to update existing replication controller.
    :param pod: pod to be updated
    :param config: updated config for pod
    :type pod: kubedock.kapi.pod.Pod
    :type config: dict
    :returns: True/False on success/failure
    :rtype: boolean
    """
    k8squery = KubeQuery()
    rc = k8squery.get(['replicationcontrollers', pod.sid], ns=pod.namespace)
    failed, _ = podutils.is_failed_k8s_answer(rc)
    if failed:
        return False
    rc = k8squery.put(['replicationcontrollers', pod.sid],
                      json.dumps(config), ns=pod.namespace, rest=True)
    failed, _ = podutils.is_failed_k8s_answer(rc)
    return not failed


def get_replicationcontroller(namespace, name):
    rc = KubeQuery().get(['replicationcontrollers', name], ns=namespace)
    podutils.raise_if_failure(rc, "Couldn't find Replication Controller")
    return rc
