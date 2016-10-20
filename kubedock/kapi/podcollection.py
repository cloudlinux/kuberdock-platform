import json
from collections import defaultdict
from crypt import crypt
from datetime import datetime
from os import path
from uuid import uuid4

import paramiko
import pytz
from celery.exceptions import MaxRetriesExceededError
from flask import current_app

import helpers
import ingress_resource
import licensing
import node_utils
import pod_domains
import podutils
import pstorage
from helpers import (
    KubeQuery, K8sSecretsClient, K8sSecretsBuilder, LocalService)
from images import Image
from kubedock.exceptions import (
    ContainerCommandExecutionError, NotFound,
    NoFreeIPs, NoSuitableNode, SubsystemtIsNotReadyError, ServicePodDumpError,
    CustomDomainIsNotReady, InternalAPIError)
from kubedock.kapi.lbpoll import get_service_provider
from kubedock.validation import ValidationError
from network_policies import (
    allow_public_ports_policy,
    allow_same_user_policy,
    PUBLIC_PORT_POLICY_NAME
)
from node import Node as K8SNode
from node import NodeException
from pod import Pod
from .pod_locks import (
    PodOperations, get_pod_lock, pod_lock_context, catch_locked_pod,
    task_release_podlock, PodIsLockedError)
from .. import billing
from .. import certificate_utils
from .. import dns_management
from .. import utils
from ..constants import AWS_UNKNOWN_ADDRESS
from ..core import ExclusiveLockContextManager, db
from ..domains.models import PodDomain, BaseDomain
from ..exceptions import (
    APIError,
    InsufficientData,
    PodStartFailure,
    PublicAccessAssigningError,
    PVResizeFailed
)
from ..kd_celery import celery
from ..nodes.models import Node
from ..pods.models import (
    PersistentDisk, PodIP, IPPool, Pod as DBPod, PersistentDiskStatuses)
from ..system_settings import keys as settings_keys
from ..system_settings.models import SystemSettings
from ..usage.models import IpState
from ..utils import POD_STATUSES, NODE_STATUSES, nested_dict_utils, \
    send_event_to_user

UNKNOWN_ADDRESS = 'Unknown'

# We use only 30 because useradd limits name to 32, and ssh client limits
# name only to 30 (may be this is configurable) so we use lowest possible
# This value is hardcoded in a few ssh-feature related scripts because they
# will be copied to each node at deploy stage
DIRECT_SSH_USERNAME_LEN = 30
DIRECT_SSH_ERROR = "Error retrieving ssh access, please contact administrator"
CHANGE_IP_MESSAGE = ('Please, take into account that IP address of pod '
                     '{pod_name} was changed from {old_ip} to {new_ip}')


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


class PodsTask(celery.Task):
    """Base class for celery tasks that manipulates with pods.

    On APIError send notifications to pod's owner and on other errors send
    notifications to admin.

    Attention: `pod_id` must be in kwargs or the first of args.
    """

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        with self.flask_app.app_context():
            pod_id = kwargs.get('pod_id', args[0])
            owner_id = DBPod.query.get(pod_id).owner_id

            if isinstance(exc, InternalAPIError):
                return self._on_internal_api_error(owner_id, exc)
            elif isinstance(exc, APIError):
                return self._on_api_error(owner_id, exc)
            else:
                return self._on_unknown_error(owner_id, exc)

    @staticmethod
    def _on_internal_api_error(owner_id, exc):
        msg = 'Internal error, please contact administrator'
        utils.send_event_to_user(
            'notify:error', {'message': msg}, owner_id)
        utils.send_event_to_role(
            'notify:error', {'message': exc.message}, 'Admin')

    @staticmethod
    def _on_api_error(owner_id, exc):
        utils.send_event_to_user(
            'notify:error', {'message': exc.message}, owner_id)

    @staticmethod
    def _on_unknown_error(owner_id, exc):
        msg = 'Internal error, please contact administrator'
        utils.send_event_to_user(
            'notify:error', {'message': msg}, owner_id)
        utils.send_event_to_role(
            'notify:error',
            {'message': 'Unexpected error: {}'.format(exc.message)},
            'Admin')


def get_user_namespaces(user):
    return {pod.namespace for pod in user.pods if not pod.is_deleted}


class PodNotFound(APIError):
    message = 'Pod not found'
    status_code = 404


class NoDomain(APIError):
    message = ('At least on of "domain" or "base_domain" must be set '
               'when public_access_type is "domain". It seems like '
               'there is some error')


def _get_network_policy_api():
    """Returns KubeQuery object configured to send requests to k8s network
    policy API.
    """
    return KubeQuery(api_version=current_app.config['KUBE_NP_API_VERSION'],
                     base_url=current_app.config['KUBE_NP_BASE_URL'])


class PublicAccessType:
    PUBLIC_IP = 'public_ip'
    PUBLIC_AWS = 'public_aws'
    DOMAIN = 'domain'
    allowed = (PUBLIC_IP, PUBLIC_AWS, DOMAIN)


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

        # TODO: AC-4126 preliminary check for:
        # there is alive node with desired Kube Type (done in validator, move?)
        # there is a free public IP (if required)
        # DNS management system is ok (if required)
        # ...

        # check public addresses before create
        self._check_public_address_available(params, original_pod=original_pod)

        if self.owner is not None:
            params['name'] = DBPod.check_name(params.get('name'),
                                              self.owner.id, generate_new=True)

        return params, secrets

    def _preprocess_pod_dump(self, dump, skip_check=False):
        hidden_fields = ['node', 'podIP', 'status', 'db_status', 'k8s_status',
                         'service', 'serviceAccount', 'hostNetwork']

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
            if self.owner is not None:  # may not have an owner in dry-run
                self._check_trial(containers, original_pod=original_pod)
            with db.session.begin_nested():
                Image.check_containers(containers, secrets)

    def _check_status(self, pod_data):
        billing_type = SystemSettings.get_by_name(
            settings_keys.BILLING_TYPE).lower()
        if billing_type != 'no billing' and self.owner.fix_price:
            # All pods created by fixed-price users initially must have
            # status "unpaid". Status may be changed later (using command
            # "set").
            pod_data['status'] = POD_STATUSES.unpaid

    @staticmethod
    def _preprocess_public_access(pod_data):
        """Preprocess and check public access parameters."""
        t_specified = pod_data.get('public_access_type')
        if t_specified and t_specified not in PublicAccessType.allowed:
            _raise_unexpected_access_type(t_specified)

        possible_types = []

        if 'domain' in pod_data or 'base_domain' in pod_data:
            possible_types.append(PublicAccessType.DOMAIN)
        if 'public_aws' in pod_data or current_app.config['AWS']:
            possible_types.append(PublicAccessType.PUBLIC_AWS)
        if 'public_ip' in pod_data:
            possible_types.append(PublicAccessType.PUBLIC_IP)

        if len(possible_types) > 1:
            raise ValidationError('Inconsistent public access data')
        elif not possible_types:
            if current_app.config['AWS']:
                t = PublicAccessType.PUBLIC_AWS
            else:
                t = PublicAccessType.PUBLIC_IP
        else:
            t = possible_types[0]

        if t_specified and t_specified != t:
            raise ValidationError('Inconsistent public access data')

        pod_data['public_access_type'] = t

        if t == PublicAccessType.DOMAIN:
            if 'base_domain' not in pod_data:
                pod_data['base_domain'] = pod_data.pop('domain')
            pod_data.setdefault('domain', None)
            validate_domains(pod_data)

        elif t == PublicAccessType.PUBLIC_AWS:
            pod_data.setdefault('public_aws', None)

        elif t == PublicAccessType.PUBLIC_IP:
            pod_data.setdefault('public_ip', None)

        else:
            _raise_unexpected_access_type(t)

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
            db_pod = self._save_pod(pod)
            pod.forge_dockers()

        namespace = pod.namespace

        with pod_lock_context(pod.id, operation=PodOperations.CREATE):
            self._make_namespace(pod.namespace)

            secret_ids = self._save_k8s_secrets(secrets, namespace)
            pod.secrets = secret_ids

            pod_config = db_pod.get_dbconfig()
            pod_config['service_annotations'] = data.pop(
                'service_annotations', None)
            pod_config['secrets'] = pod.secrets
            # Update config
            db_pod.set_dbconfig(pod_config, save=True)
            return pod.as_dict()

    def add(self, params, skip_check=False, reuse_pv=True, dry_run=False):
        if self.owner is None and not dry_run:
            raise InsufficientData('Cannot create a pod without an owner')

        if not skip_check:
            _check_license()

        self._preprocess_public_access(params)

        params, secrets = self._preprocess_new_pod(
            params, skip_check=skip_check)

        if dry_run:
            return True

        return self._add_pod(params, secrets, skip_check, reuse_pv)

    def add_from_dump(self, dump, skip_check=False):
        if not skip_check:
            _check_license()

        pod_data, secrets = self._preprocess_pod_dump(dump, skip_check)

        return self._add_pod(pod_data, secrets, skip_check, reuse_pv=True)

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
        persistent_volumes = [vol for vol in params['volumes']
                              if 'persistentDisk' in vol]
        is_compatible, pinned_node_name = \
            pstorage.STORAGE_CLASS.are_pod_volumes_compatible(
                persistent_volumes, self.owner.id, params)
        if not is_compatible:
            raise APIError("Invalid combination of persistent disks")
        if pinned_node_name is not None:
            params['node'] = pinned_node_name

    @catch_locked_pod
    @utils.atomic(nested=False)
    def edit(self, original_pod, data, skip_check=False, lock=False):
        """
        Preprocess and add new pod config in db.
        New config will be applied on the next manual restart.

        :param original_pod: kubedock.kapi.pod.Pod
        :param data: see command_pod_schema and edited_pod_config_schema
            in kubedock.validation
        :param lock: flag specifies should we lock the operation or not
        """
        with pod_lock_context(original_pod.id, operation=PodOperations.EDIT,
                              acquire_lock=lock):
            new_pod_data = data.get('edited_config')
            original_db_pod = DBPod.query.get(original_pod.id)
            original_db_pod_config = original_db_pod.get_dbconfig()

            if new_pod_data is None:
                original_db_pod.set_dbconfig(
                    dict(original_db_pod_config, edited_config=None),
                    save=False)
                original_pod.edited_config = None
                return original_pod.as_dict()

            reject_replica_with_pv(new_pod_data, key='volumes')

            self._preprocess_public_access(new_pod_data)
            self._update_public_access(original_pod.id, original_db_pod_config,
                                       new_pod_data, check_only=True)

            data, secrets = self._preprocess_new_pod(
                new_pod_data, original_pod=original_pod, skip_check=skip_check)

            pod = Pod(dict(new_pod_data, **{
                key: original_db_pod_config[key]
                for key in ('namespace', 'id', 'sid')
                if key in original_db_pod_config}))
            # create PD models in db and change volumes schema in config
            pod.compose_persistent()

            # get old secrets, like mapping {secret: id-of-the-secret-in-k8s}
            exist = {
                v: k for k, v in self.get_secrets(original_pod).iteritems()
            }
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

            utils.send_pod_status_update(
                original_db_pod.status, original_db_pod, 'MODIFIED')

            return original_pod.as_dict()

    def get_owned(self):
        return self._get_owned()

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
    def has_public_ports(conf):
        """Returns true if pod has public ports"""
        for c in conf.get('containers', []):
            for port in c.get('ports', []):
                if port.get('isPublic', False):
                    return True
        return False

    @staticmethod
    def get_public_ports(conf):
        return [
            port
            for container in conf.get('containers', [])
            for port in container.get('ports', [])
            if port.get('isPublic', False)
        ]

    @staticmethod
    def _check_public_address_available(config, original_pod=None):
        """
        :param config: pod config
        :param original_pod: kapi-Pod object. Provide this if you need to check
            edit, not creation.
        """
        if not PodCollection.has_public_ports(config):
            return

        access_type = config.get('public_access_type',
                                 PublicAccessType.PUBLIC_IP)

        if access_type == PublicAccessType.PUBLIC_IP:
            if original_pod:
                public_ip = getattr(original_pod, 'public_ip', None)
            else:
                public_ip = config.get('public_ip', None)
            if not public_ip:
                node = original_pod.node \
                    if original_pod and current_app.config['FIXED_IP_POOLS'] \
                    else None
                IPPool.get_free_host(as_int=True, node=node)
        elif access_type == PublicAccessType.DOMAIN:
            domain = config.get('domain', None)

            if domain:
                # If no domain provided, skip check. It will be perfomed later,
                # when domain will be set.
                #
                # If certificate is provided it's applied to the custom_domain
                # if present. Otherwise is used with the domain from KD.
                # This check is also performed later, on pod start. It is here
                # for the user's convience only
                if config.get('certificate'):
                    certificate_utils.check_cert_is_valid_for_domain(
                        domain, config['certificate']['cert'])
        elif access_type == PublicAccessType.PUBLIC_AWS:
            pass
        else:
            _raise_unexpected_access_type(access_type)

    @staticmethod
    @utils.atomic()
    def _prepare_for_public_address(db_pod, db_config):
        """Prepare pod for Public IP assigning.

        :type db_pod: DBPod
        :type db_config: dict
        """

        if not PodCollection.has_public_ports(db_config):
            for f in ('public_ip', 'public_aws', 'domain'):
                db_config.pop(f, None)
            db_pod.set_dbconfig(db_config, save=False)
            return

        access_type = db_config.get('public_access_type',
                                    PublicAccessType.PUBLIC_IP)

        if access_type == PublicAccessType.PUBLIC_IP:
            if not db_config.get('public_ip', None):
                IPPool.get_free_host(as_int=True)
                # 'true' indicates that this Pod needs Public IP to be assigned
                db_config['public_ip'] = 'true'

        elif access_type == PublicAccessType.PUBLIC_AWS:
            db_config.setdefault('public_aws', AWS_UNKNOWN_ADDRESS)

        elif access_type == PublicAccessType.DOMAIN:
            domain_name = (db_config.get('domain', None) or
                           db_config.get('base_domain'))
            if not domain_name:
                raise NoDomain

            with utils.atomic(PublicAccessAssigningError(
                    details={'message': 'Error while getting Pod Domain'})):
                pod_domain, pod_domain_created = \
                    pod_domains.get_or_create_pod_domain(db_pod, domain_name)
                if pod_domain_created:
                    db.session.add(pod_domain)
            db_config['domain'] = str(pod_domain)

            if db_config.get('certificate'):
                certificate_utils.check_cert_is_valid_for_domain(
                    db_config['domain'], db_config['certificate']['cert'])

        else:
            _raise_unexpected_access_type(access_type)

        db_pod.set_dbconfig(db_config, save=False)

    @catch_locked_pod
    @utils.atomic(nested=False)
    def _set_entry(self, pod, data, lock=False):
        """Immediately set fields "status", "name", "postDescription",
         "unpaid" in DB."""
        db_pod = DBPod.query.get(pod.id)
        commandOptions = data['commandOptions']
        if commandOptions.get('status'):
            if pod.status in (POD_STATUSES.stopped, POD_STATUSES.unpaid):
                pod.status = db_pod.status  # only if not in k8s
                db_pod.status = commandOptions['status']
        if commandOptions.get('unpaid') is not None:
            if commandOptions['unpaid']:
                self.stop_unpaid(pod, lock=lock)
            else:
                db_pod.unpaid = False
                pod.set_status(POD_STATUSES.stopped, send_update=True,
                               force=True)
        if commandOptions.get('name'):
            pod.name = commandOptions['name']
            pod.check_name()
            db_pod.name = pod.name
        if 'postDescription' in commandOptions:
            pod.postDescription = commandOptions['postDescription']
            config = dict(db_pod.get_dbconfig(),
                          postDescription=pod.postDescription)
            db_pod.set_dbconfig(config, save=False)
        if commandOptions.get('custom_domain') is not None:
            custom_domain = commandOptions['custom_domain']
            certificate = commandOptions.get('certificate')
            self._set_custom_domain(pod, custom_domain, certificate)

        return pod.as_dict()

    @staticmethod
    @utils.atomic()
    def _remove_public_ip(pod_id=None, ip=None, force=False):
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
            for port in container.get('ports', tuple()):
                port['isPublic_before_freed'] = port.pop('isPublic', None)
        pod.set_dbconfig(pod_config, save=False)

        network = IPPool.query.filter_by(network=ip.network).first()
        node = network.node
        if current_app.config['FIXED_IP_POOLS'] and node:
            try:
                K8SNode(
                    hostname=node.hostname
                ).increment_free_public_ip_count(1)
            except NodeException as e:
                if not force:
                    raise
                current_app.logger.debug(
                    "Cannot increment pubic IP count: {}".format(repr(e)))
        IpState.end(pod_id, ip.ip_address)
        db.session.delete(ip)

    @staticmethod
    @utils.atomic(nested=False)
    def unbind_publicIP(pod_id, lock=False):
        """Temporary unbind publicIP, on next pod start publicIP will be
        reassigned. Unbinded publicIP saved in pod config as
        public_ip_before_freed.

        """
        ip = PodIP.query.filter_by(pod_id=pod_id).first()
        if ip is None:
            return

        with pod_lock_context(pod_id,
                              operation=PodOperations.UNBIND_IP,
                              acquire_lock=lock):
            pod = ip.pod
            pod_config = pod.get_dbconfig()
            if pod.status not in (POD_STATUSES.stopped, POD_STATUSES.unpaid):
                raise APIError("We can unbind ip only on stopped pod")
            pod_config['public_ip_before_freed'] = pod_config.pop(
                'public_ip', None)
            pod_config['public_ip'] = 'true'
            pod.set_dbconfig(pod_config, save=False)

            network = IPPool.query.filter_by(network=ip.network).first()
            node = network.node
            if current_app.config['FIXED_IP_POOLS'] and node:
                K8SNode(
                    hostname=node.hostname).increment_free_public_ip_count(1)

            IpState.end(pod_id, ip.ip_address)
            db.session.delete(ip)
            utils.send_event_to_user(
                'pod:change', {'id': pod_id}, pod.owner_id
            )

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
        cls._prepare_for_public_address(pod, pod_config)

    @utils.atomic()
    def _save_pod(self, pod, db_pod=None):
        """
        Save pod data to db, prepare it for public access and update kapi pod.

        :param pod: kapi-Pod
        :param db_pod: update existing db-Pod
        :type pod: Pod
        :type db_pod: DBPod
        """
        template_id = getattr(pod, 'kuberdock_template_id', None)
        template_version_id = getattr(
            pod, 'kuberdock_template_version_id', None)
        template_plan_name = getattr(pod, 'kuberdock_plan_name', None)
        status = getattr(pod, 'status', POD_STATUSES.stopped)
        excluded = (  # duplicates of model's fields
            'kuberdock_template_id', 'kuberdock_plan_name',
            'kuberdock_template_version_id',
            'owner', 'kube_type', 'status', 'id', 'name')
        data = {k: v for k, v in vars(pod).iteritems() if k not in excluded}
        if db_pod is None:
            db_pod = DBPod.create(
                name=pod.name, config=json.dumps(data), id=pod.id,
                status=status, template_id=template_id,
                template_version_id=template_version_id,
                template_plan_name=template_plan_name, kube_id=pod.kube_type,
                owner=self.owner)
            db.session.add(db_pod)
        else:
            db_pod.status = status
            db_pod.kube_id = pod.kube_type
            db_pod.owner = self.owner
        self._prepare_for_public_address(db_pod, data)
        # update kapi pod
        for f in ('public_ip', 'public_aws', 'domain'):
            try:
                delattr(pod, f)
            except AttributeError:
                pass
        for k, v in data.items():
            setattr(pod, k, v)
        return db_pod

    def update(self, pod_id, data):
        return self.update_with_options(pod_id, data, lock=True)

    def update_with_options(self, pod_id, data, lock=False):
        """Executes some command for pod, which is given in data['command']
        parameter.
        :param lock: flag defines should an operation lock other pod
            operations ot not.
        """
        pod = self._get_by_id(pod_id)
        command = data.pop('command', None)
        if command is None:
            return
        dispatcher = {
            'start': self._start_pod,
            'synchronous_start': self._sync_start_pod,
            'stop': self._stop_pod,
            'redeploy': self._redeploy,

            # NOTE: the next three commands may look similar, but they do
            #   completely different things. Maybe we need to rename some of
            #   them, or change outer logic to reduce differences to merge
            #   a few commands into one.

            # immediately update config in db and k8s.ReplicationController
            # currently, it's used only for binding pod with LS to current node
            'change_config': self._change_pod_config,
            # immediately set DB data
            # currently, it's used for changing status, name, postDescription
            'set': self._set_entry,
            # add new pod config that will be applied after next manual restart
            'edit': self.edit,
            'unbind-ip': self._unbind_ip,
        }
        # List of commands which do not require a lock for other operations on
        # the pod.
        # TODO: 'resize' is here just because it is not working now
        non_locking_commands = ['resize']
        if command in dispatcher:
            if command in non_locking_commands:
                return dispatcher[command](pod, data)
            return dispatcher[command](pod, data, lock=lock)
        podutils.raise_("Unknown command")

    @catch_locked_pod
    def delete(self, pod_id, force=False):
        pod = self._get_by_id(pod_id)

        if pod.owner.is_internal() and not force:
            podutils.raise_('Service pod cannot be removed', 400)
        with pod_lock_context(pod_id, operation=PodOperations.DELETE):
            pod.set_status(POD_STATUSES.deleting, send_update=True, force=True)

            PersistentDisk.free(pod.id)
            # we remove service also manually
            service_name = helpers.get_pod_config(pod.id, 'service')
            if service_name:
                rv = self.k8squery.delete(
                    ['services', service_name], ns=pod.namespace
                )
                if not force:
                    podutils.raise_if_failure(rv, "Could not remove a service")

            if hasattr(pod, 'public_ip'):
                self._remove_public_ip(pod_id=pod_id, force=force)
            if hasattr(pod, 'domain'):
                self._remove_pod_domain(pod_id=pod_id, pod_domain=pod.domain)

            self._drop_network_policies(pod.namespace, force=force)
            # all deleted asynchronously, now delete namespace, that will
            # ensure delete all content
            self._drop_namespace(pod.namespace, force=force)
            helpers.mark_pod_as_deleted(pod_id)

    @staticmethod
    def remove_custom_domain(pod_id, domain):
        db_pod = DBPod.query.get(pod_id)  # type: DBPod
        db_config = db_pod.get_dbconfig()  # type: dict

        ingress_resource.remove_custom_domain(
            db_pod.namespace, db_config['service'], db_config['containers'],
            domain)

        db_config.pop('custom_domain', None)
        db_pod.set_dbconfig(db_config, save=False)

    @staticmethod
    def add_custom_domain(pod_id, domain, certificate=None):
        if not pod_domains.validate_domain_reachability(domain):
            raise CustomDomainIsNotReady(domain)

        db_pod = DBPod.query.get(pod_id)  # type: DBPod
        db_config = db_pod.get_dbconfig()  # type: dict
        db_config['custom_domain'] = domain

        ingress_resource.add_custom_domain(
            db_pod.namespace, db_config['service'], db_config['containers'],
            domain, certificate)

        db_pod.set_dbconfig(db_config, save=False)

    @staticmethod
    def _remove_pod_domain(pod_id, pod_domain):
        """:type pod_domain: str"""
        record_type = 'CNAME' if current_app.config['AWS'] else 'A'
        ok, message = dns_management.delete_record(pod_domain, record_type)
        if not ok:
            current_app.logger.error(
                u'Failed to delete DNS record for pod "{}": {}'
                .format(pod_id, message))
            utils.send_event_to_role(
                'notify:error', {'message': message}, 'Admin')

        domain_name = pod_domain.split('.', 1)[0]

        db_pod_domain = PodDomain.query.filter_by(
            pod_id=pod_id, name=domain_name).first()  # type: PodDomain

        if not db_pod_domain:
            return

        base_domain = db_pod_domain.base_domain
        db.session.delete(db_pod_domain)
        db_pod = DBPod.query.get(pod_id)  # type: DBPod
        db_config = db_pod.get_dbconfig()  # type: dict
        db_config.pop('domain')
        db_config.pop('custom_domain', None)
        db_config.setdefault('base_domain', base_domain.name)
        # ^^^ ensure for old-style db_config without this field
        db_pod.set_dbconfig(db_config, save=False)

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

    @catch_locked_pod
    def update_container(self, pod_id, container_name):
        """
        Update container image by restarting the pod.

        :raise APIError: if pod not found or if pod is not running
        """
        with pod_lock_context(pod_id, operation=PodOperations.RESTART):
            pod = self._get_by_id(pod_id)
            self._stop_pod(pod, block=True, lock=False)
            return self._start_pod(pod, lock=False)

    def _make_namespace(self, namespace):
        data = self._get_namespace(namespace)
        if data is None:
            owner_repr = str(self.owner.id)
            config = {
                "kind": "Namespace",
                "apiVersion": current_app.config['KUBE_API_VERSION'],
                "metadata": {
                    "annotations": {
                        "net.alpha.kubernetes.io/network-isolation": "yes"
                    },
                    "labels": {
                        "kuberdock-user-uid": owner_repr
                    },
                    "name": namespace
                }
            }
            rv = self.k8squery.post(
                ['namespaces'], json.dumps(config), rest=True, ns=False)
            podutils.raise_if_failure(rv, "Could not add namespaces")

            # Add main ns policy
            _get_network_policy_api().post(
                ['networkpolicys'],
                json.dumps(allow_same_user_policy(owner_repr)),
                rest=True,
                ns=namespace,
            )

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
        failed, _ = podutils.is_failed_k8s_answer(data)
        if failed:
            return None
        return data

    def _get_namespaces(self):
        data = self.k8squery.get(['namespaces'], ns=False)
        podutils.raise_if_failure(data, "Could not get namespaces")
        namespaces = [i['metadata']['name'] for i in data.get('items', {})]
        if self.owner is None:
            return namespaces
        user_namespaces = get_user_namespaces(self.owner)
        return [ns for ns in namespaces if ns in user_namespaces]

    def _drop_namespace(self, namespace, force=False):
        rv = self.k8squery.delete(['namespaces', namespace], ns=False)
        if not force:
            podutils.raise_if_failure(
                rv, "Cannot delete namespace '{}'".format(namespace)
            )
        return rv

    @staticmethod
    def _drop_network_policies(namespace, force=False):
        """
        This should drop all network policies in provided namespace
        including special "public" policy
        """
        rv = _get_network_policy_api().delete(
            ['networkpolicys'], ns=namespace)
        if not force:
            podutils.raise_if_failure(
                rv, "Cannot delete NetworkPolicy for namespace: '{}'"
                    .format(namespace))

    def _get_pods(self, namespaces=None):
        # current_app.logger.debug(namespaces)
        if not hasattr(self, '_collection'):
            self._collection = {}
        pod_index = set()

        pods_data = []
        replicas_data = []

        if namespaces:
            for namespace in namespaces:
                pods = self.k8squery.get(['pods'], ns=namespace)
                podutils.raise_if_failure(pods, "Could not get pods")
                pods_data.extend(pods.get('items', {}))
                replicas = self.k8squery.get(
                    ['replicationcontrollers'], ns=namespace)
                podutils.raise_if_failure(replicas, "Could not get replicas")
                replicas_data.extend(replicas['items'])
        else:
            pods = self.k8squery.get(['pods'])
            podutils.raise_if_failure(pods, "Could not get pods")
            pods_data.extend(pods.get('items', {}))
            replicas = self.k8squery.get(['replicationcontrollers'])
            podutils.raise_if_failure(replicas, "Could not get replicas")
            replicas_data.extend(replicas.get('items', {}))

        pod_names = defaultdict(set)

        for item in pods_data:
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
        if current_app.config['AWS']:
            if getattr(pod, 'public_aws', AWS_UNKNOWN_ADDRESS) \
                    == AWS_UNKNOWN_ADDRESS:
                dns = get_service_provider().get_dns_by_pods(pod.id)
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
                pod.forbidSwitchingAppPackage = db_pod_config.get(
                    'forbidSwitchingAppPackage')
                pod.appLastUpdate = db_pod_config.get('appLastUpdate')
                pod.appCommands = db_pod_config.get('appCommands')

                pod.public_access_type = db_pod_config.get(
                    'public_access_type', PublicAccessType.PUBLIC_IP)
                if db_pod_config.get('public_ip'):
                    pod.public_ip = db_pod_config['public_ip']
                if db_pod_config.get('public_aws'):
                    pod.public_aws = db_pod_config['public_aws']
                if db_pod_config.get('domain'):
                    pod.domain = db_pod_config['domain']
                if db_pod_config.get('base_domain'):
                    pod.base_domain = db_pod_config['base_domain']
                if db_pod_config.get('custom_domain'):
                    pod.custom_domain = db_pod_config['custom_domain']

                pod.secrets = db_pod_config.get('secrets', [])
                a = pod.containers
                b = db_pod_config.get('containers')
                restore_fake_volume_mounts(a, b)
                pod.containers = podutils.merge_lists(a, b, 'name')
                restore_containers_host_ports_config(pod.containers, b)

            pod.name = db_pod.name
            pod.set_owner(db_pod.owner)
            pod.template_id = db_pod.template_id
            pod.template_version_id = db_pod.template_version_id
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
                if container.get('state', '') == 'terminated':
                    if container.get('exitCode') == 0:
                        container['state'] = 'succeeded'
                    else:
                        container['state'] = 'failed'
                container.pop('resources', None)
                kubes = container.get('kubes')
                if kubes:
                    container['limits'] = billing.repr_limits(kubes,
                                                              pod.kube_type)

    @utils.atomic()
    def _apply_edit(self, pod, db_pod, db_config, internal_edit=True):
        if db_config.get('edited_config') is None:
            return pod, db_config

        old_pod = pod
        old_config = db_config
        new_config = db_config['edited_config']
        reject_replica_with_pv(new_config)
        if not internal_edit:
            new_config['forbidSwitchingAppPackage'] = 'the pod was edited'
        fields_to_copy = ['podIP', 'service', 'postDescription',
                          'appVariables', 'service_annotations', ]
        for k in fields_to_copy:
            v = getattr(old_pod, k, None)
            if v is not None:
                new_config[k] = v
        updated_dt = datetime.utcnow().replace(tzinfo=pytz.UTC).isoformat()
        new_config['appLastUpdate'] = updated_dt

        self._update_public_access(pod.id, old_config, new_config)

        # re-check images, PDs, etc.
        new_config, _ = self._preprocess_new_pod(
            new_config, original_pod=old_pod)

        # save old values
        old_pv_sizes = old_pod.get_volumes_size()

        # resize or abort operation
        new_pv_sizes = {pd['persistentDisk']['pdName']:
                        pd['persistentDisk']['pdSize']
                        for pd in new_config.get('volumes_public', [])
                        if pd.get('persistentDisk') and
                        old_pv_sizes.get(pd['persistentDisk']['pdName']) and
                        old_pv_sizes[pd['persistentDisk']['pdName']] !=
                        pd['persistentDisk']['pdSize']}

        # added exists PDs
        new_pds = {pd['persistentDisk']['pdName']:
                   pd['persistentDisk']['pdSize']
                   for pd in new_config.get('volumes_public', [])
                   if pd.get('persistentDisk') and
                   not old_pv_sizes.get(pd['persistentDisk']['pdName'])}
        if new_pds:
            persistent_storage = pstorage.STORAGE_CLASS()
            for pd_name, new_size in new_pds.iteritems():
                old_pd = persistent_storage.get_by_name(db_pod.owner, pd_name)
                if old_pd:
                    new_pv_sizes[pd_name] = new_size
                    old_pv_sizes = old_pd['size']

        pod = Pod(new_config)
        pod.id = db_pod.id
        pod.set_owner(db_pod.owner)
        update_service(pod)
        db_pod = self._save_pod(pod, db_pod=db_pod)
        if new_pv_sizes:
            pv_query = PersistentDisk.get_all_query().filter(
                PersistentDisk.name.in_(new_pv_sizes.keys()),
                PersistentDisk.owner_id == db_pod.owner_id
            )
            pv_id_dict = {pv.name: pv.id for pv in pv_query}
            try:
                for (pv_name, new_size) in new_pv_sizes.iteritems():
                    change_pv_size(pv_id_dict[pv_name], new_size,
                                   update_stat=False)
            except APIError as err:
                send_event_to_user(
                    'notify:error', {'message': "Error while resize "
                                                "persistent storage"},
                    pod.owner_id)
                # revert resize volumes
                for (pv_name, old_size) in old_pv_sizes.iteritems():
                    pv_id = pv_id_dict.get(pv_name)
                    change_pv_size(pv_id, old_size, update_stat=False)
                raise err

        config = db_pod.get_dbconfig()
        pod.name = db_pod.name
        pod.kube_type = db_pod.kube_id
        pod.status = old_pod.status
        pod.volumes = config.get('volumes')
        pod.forge_dockers()
        return pod, db_pod.get_dbconfig()

    def _update_public_access(self, pod_id, old_config, new_config,
                              check_only=False):
        if old_config == new_config:
            return

        access_type = old_config.get('public_access_type',
                                     PublicAccessType.PUBLIC_IP)
        if (access_type != new_config.setdefault('public_access_type',
                                                 access_type)):
            raise APIError('Changing of public access type does not support')

        if access_type == PublicAccessType.PUBLIC_IP:
            self._update_public_ip(pod_id, old_config, new_config, check_only)

        elif access_type == PublicAccessType.PUBLIC_AWS:
            self._update_public_aws(pod_id, old_config, new_config, check_only)

        elif access_type == PublicAccessType.DOMAIN:
            self._update_domain(pod_id, old_config, new_config, check_only)

        else:
            _raise_unexpected_access_type(access_type)

    def _update_public_ip(self, pod_id, old_config, new_config, check_only):
        if check_only:
            return

        had_public_ports = self.has_public_ports(old_config)
        has_public_ports = self.has_public_ports(new_config)

        if had_public_ports and not has_public_ports:
            self._remove_public_ip(pod_id)
            new_config['public_ip'] = None

    def _update_public_aws(self, pod_id, old_config, new_config, check_only):
        if check_only:
            return

        has_public_ports = self.has_public_ports(new_config)

        if not has_public_ports:
            new_config['public_aws'] = None

    def _update_domain(self, pod_id, old_config, new_config, check_only):
        old_ports = {port.get('hostPort') or port['containerPort']: port
                     for port in self.get_public_ports(old_config)}
        new_ports = {port.get('hostPort') or port['containerPort']: port
                     for port in self.get_public_ports(new_config)}
        old_pod_domain = old_config.get('domain')
        ing_client = ingress_resource.IngressResourceClient()

        need_remove_ing = False
        need_remove_domain = False

        if new_config.get('base_domain') != old_config.get('base_domain'):
            # base domain changed, need to reassign domain and delete old one
            need_remove_ing = True
            need_remove_domain = True
            new_config['domain'] = None

        if not new_ports:
            need_remove_domain = True
            need_remove_ing = True
            new_config['domain'] = None

        if old_pod_domain != new_config.get('domain'):
            need_remove_domain = True
            need_remove_ing = True

        if old_ports != new_ports:
            need_remove_ing = True

        if old_config.get('certificate') != new_config.get('certificate'):
            need_remove_ing = True

        if old_config.get('custom_domain') != new_config.get('custom_domain'):
            need_remove_ing = True
        ###

        if check_only:
            return

        if need_remove_ing:
            ing_client.remove_by_name(old_config.get('namespace'))
        if need_remove_domain:
            self._remove_pod_domain(pod_id, old_pod_domain)

    def _sync_start_pod(self, pod, data=None, lock=False):
        if data is None:
            data = {}
        nested_dict_utils.set(data, 'commandOptions.async', False)
        return self._start_pod(pod, data=data, lock=lock)

    @catch_locked_pod
    def _start_pod(self, pod, data=None, lock=False):
        if data is None:
            data = {}
        command_options = data.get('commandOptions', {})

        with pod_lock_context(pod.id,
                              operation=PodOperations.PREPARE_FOR_START,
                              acquire_lock=lock):
            db_pod = DBPod.query.get(pod.id)
            db_config = db_pod.get_dbconfig()
            if command_options.get('applyEdit'):
                internal_edit = command_options.get('internalEdit', False)
                pod, db_config = self._apply_edit(pod, db_pod, db_config,
                                                  internal_edit=internal_edit)
                db.session.commit()
            reject_replica_with_pv(db_config)

            if pod.status == POD_STATUSES.unpaid:
                raise APIError("Pod is unpaid, we can't run it")
            if pod.status in (POD_STATUSES.running, POD_STATUSES.pending,
                              POD_STATUSES.preparing):
                raise APIError("Pod is not stopped, we can't run it")
            if not self._node_available_for_pod(pod):
                raise NoSuitableNode()

            if hasattr(pod, 'domain'):
                self._handle_shared_ip(pod)

            if pod.status == POD_STATUSES.succeeded \
                    or pod.status == POD_STATUSES.failed:
                self._stop_pod(pod, block=True, lock=False)
            self._make_namespace(pod.namespace)

            pod.set_status(POD_STATUSES.preparing, send_update=True)

            if not current_app.config['FIXED_IP_POOLS']:
                self._assign_public_ip(pod, db_pod, db_config)
                # prepare_and_run_pod_task read config from db in async task
                # public_ip could not have time to save before read
                db.session.commit()

        if command_options.get('async', True):
            prepare_and_run_pod.delay(db_pod.id, lock=lock)
            return pod.as_dict()
        else:
            with pod_lock_context(pod.id, operation=PodOperations.START,
                                  acquire_lock=lock):
                return prepare_and_run_pod(db_pod.id)

    def _handle_shared_ip(self, pod):
        ok, message = dns_management.is_domain_system_ready()
        if not ok:
            raise SubsystemtIsNotReadyError(
                message,
                response_message=u'Pod cannot be started, because DNS '
                                 u'management subsystem is misconfigured. '
                                 u'Please, contact administrator.'
            )

    def assign_public_ip(self, pod_id, node=None):
        """Returns assigned ip"""
        pod = self._get_by_id(pod_id)
        db_pod = DBPod.query.get(pod_id)  # type: DBPod
        if db_pod is None:
            raise Exception('Something goes wrong. Pod is present, but db_pod '
                            'is absent')
        db_conf = db_pod.get_dbconfig()
        return self._assign_public_ip(pod, db_pod, db_conf, node)

    @staticmethod
    def _assign_public_ip(pod, db_pod, db_config, node=None):
        """Returns assigned ip"""

        # @utils.atomic()  # atomic does not work
        def _assign(desired_ip, notify_on_change=False):
            """Try to assign desired IP to pod.

            If desired ip cannot be assigned, next available ip will be
            assigned and if notify_on_change is True then notifications will be
            sent to current user and pod's owner (can be the same one).

            Attention:
                Before call ensure that PodIP for specified pod is not present
                in db.
            """
            with ExclusiveLockContextManager(
                    'PodCollection._assing_public_ip',
                    blocking=True,
                    ttl=current_app.config[
                        'PUBLIC_ACCESS_ASSIGNING_TIMEOUT']) as lock:
                if not lock:
                    raise PublicAccessAssigningError(details={
                        'message': 'Timeout getting Public IP'
                    })

                ip_address = IPPool.get_free_host(as_int=True, node=node,
                                                  ip=desired_ip)

                if notify_on_change and ip_address != utils.ip2int(desired_ip):
                    # send event 'IP changed'
                    msg = (
                        CHANGE_IP_MESSAGE.format(
                            pod_name=pod.name,
                            old_ip=desired_ip,
                            new_ip=utils.int2ip(ip_address)))
                    utils.send_event_to_user(
                        event_name='notify:warning', data={'message': msg},
                        user_id=pod.owner.id)

                network = IPPool.get_network_by_ip(ip_address)

                pod_ip = PodIP.create(pod_id=pod.id, network=network.network,
                                      ip_address=ip_address)
                db.session.add(pod_ip)
                assigned_ip = str(pod_ip)
                pod.public_ip = assigned_ip
                IpState.start(pod.id, pod_ip)
                db_config['public_ip'] = assigned_ip
                db_pod.set_dbconfig(db_config)
                return assigned_ip

        try:
            pod_public_ip = getattr(pod, 'public_ip', None)

            if pod_public_ip is None:
                return

            if pod_public_ip == 'true':
                ip = db_config.get('public_ip_before_freed')
                rv = _assign(ip, notify_on_change=False)
            elif PodIP.filter_by(pod_id=pod.id).first() is None:
                # pod ip is specified but is not present in db
                rv = _assign(pod_public_ip, notify_on_change=True)
            else:
                current_app.logger.warning('PodIP %s is already allocated',
                                           pod_public_ip)
                rv = pod_public_ip

            return rv

        except (NoFreeIPs, PublicAccessAssigningError):
            pod.set_status(POD_STATUSES.stopped, send_update=True)
            raise
        except Exception:
            current_app.logger.exception('Failed to bind publicIP: %s', pod)
            pod.set_status(POD_STATUSES.stopped, send_update=True)
            raise

    @staticmethod
    @catch_locked_pod
    def _stop_pod(pod, data=None, raise_=True, block=False, lock=False):
        podlock = None
        release_lock = True
        try:
            podlock = get_pod_lock(pod.id, operation=PodOperations.STOP,
                                   acquire_lock=lock)
            # Call PD release in all cases. If the pod was already stopped and
            # PD's were not released, then it will free them. If PD's already
            # free, then this call will do nothing.
            PersistentDisk.free(pod.id)
            if (pod.status in (POD_STATUSES.stopping, POD_STATUSES.preparing,)
                    and pod.k8s_status is None):
                pod.set_status(POD_STATUSES.stopped, send_update=True)
                return pod.as_dict()
            elif pod.status not in (POD_STATUSES.stopped, POD_STATUSES.unpaid):
                if hasattr(pod, 'sid'):
                    pod.set_status(POD_STATUSES.stopping, send_update=True)
                    if block:
                        scale_replicationcontroller(pod.id, pod.namespace,
                                                    pod.sid)
                        pod = wait_pod_status(
                            pod.id, POD_STATUSES.stopped,
                            error_message=(
                                u'During restart, Pod "{0}" did not become '
                                u'stopped after a given timeout. It may '
                                u'become later.'.format(pod.name)))
                    else:
                        release_lock = False
                        if podlock:
                            serialized_lock = podlock.serialize()
                        else:
                            serialized_lock = None
                        scale_replicationcontroller.delay(
                            pod.id, pod.namespace, pod.sid,
                            serialized_lock=serialized_lock)

                    # Remove ingresses if shared IP was used
                    if hasattr(pod, 'domain'):
                        client = ingress_resource.IngressResourceClient()
                        client.remove_by_name(pod.namespace)

                    return pod.as_dict()
                    # FIXME: else: ??? (what if pod has no "sid"?)
            elif raise_:
                raise APIError('Pod is already stopped')
        finally:
            if release_lock and podlock:
                podlock.release()

    @catch_locked_pod
    def _change_pod_config(self, pod, data, lock=False):
        with pod_lock_context(pod.id, operation=PodOperations.CHANGE_CONFIG,
                              acquire_lock=lock):
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

    @catch_locked_pod
    def _redeploy(self, pod, data, lock=False):
        podlock = None
        # In case of any exception, release lock while we did not call
        # celery task finish_redeploy
        release_lock = True
        try:
            podlock = get_pod_lock(pod.id, operation=PodOperations.REDEPLOY,
                                   acquire_lock=lock)
            command_options = data.get('commandOptions', {})
            do_async = command_options.get('async', True)

            if podlock and do_async:
                serialized_lock = podlock.serialize()
            else:
                serialized_lock = None
            if do_async:
                # pass acquired lock to nested task, it must release the lock
                release_lock = False
                finish_redeploy.delay(
                    pod.id, data, serialized_lock=serialized_lock)
                rv = pod.as_dict()
            else:
                rv = finish_redeploy(pod.id, data)
        finally:
            if podlock and release_lock:
                podlock.release()
        return rv

    def exec_in_container(self, pod_id, container_name, command):
        k8s_pod = self._get_by_id(pod_id)
        ssh_access = getattr(k8s_pod, 'direct_access', None)
        if not ssh_access:
            raise ContainerCommandExecutionError(
                "Couldn't access the contianer")
        if container_name not in ssh_access['links']:
            raise NotFound('Container not found')
        username, host = ssh_access['links'][container_name].split('@', 1)

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(host, username=username, password=ssh_access['auth'],
                        timeout=10, look_for_keys=False, allow_agent=False)
        except Exception:
            raise ContainerCommandExecutionError(
                'Failed to connect to the container')
        try:
            _, o, _ = ssh.exec_command(command, timeout=20)
            exit_status = o.channel.recv_exit_status()
            result = o.read().strip('\n')
        except Exception:
            raise ContainerCommandExecutionError()
        return {'exitStatus': exit_status, 'result': result}

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
                pods_collection = pods_collection \
                    .filter(DBPod.id != original_pod.id)
            user_kubes = sum([pod.kubes for pod in pods_collection
                              if not pod.is_deleted])
            max_kubes_trial_user = int(
                SystemSettings.get_by_name(settings_keys.MAX_KUBES_TRIAL_USER)
                or 0
            )
            kubes_left = max_kubes_trial_user - user_kubes
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

    @catch_locked_pod
    def _unbind_ip(self, pod, data=None, lock=False):
        self.unbind_publicIP(pod.id, lock=lock)

    @classmethod
    def stop_unpaid(cls, pod, block=False, lock=False):
        with pod_lock_context(pod.id,
                              operation=PodOperations.STOP_UNPAIND,
                              acquire_lock=lock):
            DBPod.query.filter_by(id=pod.id).update({'unpaid': True})
            if pod.status == POD_STATUSES.unpaid:
                return
            if pod.status == POD_STATUSES.stopped:
                pod.set_status(POD_STATUSES.unpaid, send_update=True)
                return
            PodCollection._stop_pod(pod, raise_=False, block=block, lock=False)
            db.session.flush()

    def _set_custom_domain(self, pod, domain, certificate=None):
        if not pod_domains.validate_domain_reachability(domain):
            raise CustomDomainIsNotReady(domain)
        if getattr(pod, 'custom_domain', None):
            self.remove_custom_domain(pod.id, pod.custom_domain)
        self.add_custom_domain(pod.id, domain, certificate)
        pod.custom_domain = domain
        app_commands = getattr(pod, 'appCommands', None)
        if app_commands and app_commands.get('changeDomain'):
            command = app_commands['changeDomain']
            if command['type'] == 'execInContainer':
                self.exec_in_container(
                    pod.id, command['container'],
                    "DOMAIN='{}' {}".format(domain, command['command']))


def _raise_unexpected_access_type(access_type):
    raise ValidationError(details={
        'public_access_type': 'Unknown type: %s' % access_type
    })


def _check_if_domain_system_ready():
    ready, message = dns_management.is_domain_system_ready()
    if not ready:
        raise SubsystemtIsNotReadyError(
            u'Trying to use domain for pod, while DNS is '
            u'misconfigured: {}'.format(message),
            response_message=(
                u'DNS management system is misconfigured. '
                u'Please, contact administrator.')
        )


def wait_pod_status(pod_id, wait_status, interval=1, max_retries=120,
                    error_message=None):
    """Keeps polling k8s api until pod status becomes as given"""

    def check_status():
        # we need a fresh status
        db.session.expire(DBPod.query.get(pod_id), ['status'])
        db_pod = db.session.query(DBPod).get(pod_id)
        pod = PodCollection()._get_by_id(pod_id)
        current_app.logger.debug(
            'Current pod status: {}, {}, wait for {}, pod_id: {}'.format(
                pod.status, db_pod.status, wait_status, pod_id))
        if pod.status == wait_status:
            return pod

    return utils.retry(
        check_status, interval, max_retries,
        APIError(error_message or (
            "Pod {0} did not become {1} after a given timeout. "
            "It may become later.".format(pod_id, wait_status)))
    )


@celery.task(bind=True, default_retry_delay=1, max_retries=10)
def wait_for_rescaling(self, namespace, sid, size):
    rc = get_replicationcontroller(namespace, sid)
    if rc['status']['replicas'] != size:
        try:
            self.retry()
        except MaxRetriesExceededError:
            current_app.logger.error("Can't scale rc: max retries exceeded")
            raise APIError('Cannot scale replication controller')


@celery.task(bind=True, base=PodsTask, ignore_results=True)
@task_release_podlock
def scale_replicationcontroller(self, pod_id, namespace, sid, size=0,
                                serialized_lock=None):
    """Set new replicas size and wait until replication controller increase or
    decrease real number of pods or max retries exceed.

    Notes:
        `pod_id` is needed for PodsTask.
        `bind=True` is needed for `@task_release_podlock`.
    """
    data = json.dumps({'spec': {'replicas': size}})
    rc = KubeQuery().patch(['replicationcontrollers', sid], data, ns=namespace)
    podutils.raise_if_failure(rc, "Couldn't set replicas to {}".format(size))

    if rc['status']['replicas'] != size:
        wait_for_rescaling.delay(namespace, sid, size).get()


@celery.task(bind=True, base=PodsTask, ignore_results=True)
@task_release_podlock
def finish_redeploy(self, pod_id, data, start=True):
    db_pod = DBPod.query.get(pod_id)
    pod_collection = PodCollection(db_pod.owner)
    pod = pod_collection._get_by_id(pod_id)
    with utils.atomic(nested=False):
        pod_collection._stop_pod(pod, block=True, raise_=False, lock=False)
    command_options = data.get('commandOptions') or {}
    if command_options.get('wipeOut'):
        for volume in pod.volumes_public:
            pd = volume.get('persistentDisk')
            if not pd:
                continue
            pd = PersistentDisk.get_all_query().filter(
                PersistentDisk.name == pd['pdName'],
                PersistentDisk.owner_id == db_pod.owner_id
            ).first()
            if not pd:
                current_app.logger.error(
                    u"Can't find PD '{}', user {}, pod_id {}, "
                    u"pod name '{}'".format(
                        pd['pdName'], db_pod.owner_id,
                        db_pod.id, db_pod.name
                    )
                )
                continue
            pstorage.delete_drive_by_id(pd.id)

    if start:  # start updated pod
        return PodCollection(db_pod.owner).update_with_options(
            pod_id,
            {
                # already in celery, use the same task, sync
                'command': 'synchronous_start',
                'commandOptions': command_options
            },
            # Do not acquire lock because we are already in lock.
            # If serialized_lock is None, then also don't acquire a lock, as
            # long as the task called without locking.
            lock=False
        )
    else:
        return pod.as_dict()


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


@celery.task(base=PodsTask, ignore_results=True)
def prepare_and_run_pod(pod_id, lock=False):
    with pod_lock_context(pod_id, operation=PodOperations.START,
                          acquire_lock=lock):

        db_pod = DBPod.query.get(pod_id)
        db_config = db_pod.get_dbconfig()
        pod = PodCollection(db_pod.owner)._get_by_id(pod_id)

        try:
            _process_persistent_volumes(pod, db_config.get('volumes', []))

            service_annotations = db_config.get('service_annotations')
            local_svc, _ = run_service(pod, service_annotations)
            if local_svc:
                db_config['service'] = pod.service \
                    = local_svc['metadata']['name']
                db_config['podIP'] = LocalService().get_clusterIP(local_svc)
                try:
                    db_pod.set_dbconfig(db_config, save=True)
                except:
                    msg = 'Error saving Pod config to Database'
                    current_app.logger.exception(msg)
                    raise PodStartFailure(msg)

            config = pod.prepare()
            k8squery = KubeQuery()
            if not _try_to_update_existing_rc(pod, config):
                rc = k8squery.post(
                    ['replicationcontrollers'], json.dumps(config),
                    ns=pod.namespace, rest=True)
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

            if getattr(pod, 'domain', None):
                # if no open ports domain set to None
                # in `prepare_for_public_access`
                _ensure_old_dns_record_removed(pod.domain)
                custom_domain = getattr(pod, 'custom_domain', None)
                ok, message = ingress_resource.create_ingress(
                    pod.containers, pod.namespace, pod.service, pod.domain,
                    custom_domain, pod.certificate)
                if not ok:
                    msg = u'Failed to run pod with domain "{}": {}'
                    utils.send_event_to_role(
                        'notify:error',
                        {'message': msg.format(pod.domain, message)}, 'Admin')
                    # "pod stop" will be called below
                    raise APIError(msg)
        except Exception as err:
            current_app.logger.exception('Failed to run pod: %s', pod)
            # We have to stop pod here to release all the things that was
            # allocated during partial start
            pods = PodCollection()
            pods._stop_pod(pod, raise_=False, block=False, lock=False)
            # If we forget to do commit here all Pod's status changes will
            # be lost with rollback on raise as well as other changes related
            # to "teardown" part like releasing of PDs
            db.session.commit()
            if isinstance(err, APIError):
                # We need to update db_pod in case if the pod status was
                # changed since the last retrieval from DB
                db.session.refresh(db_pod)
                if isinstance(err, PodStartFailure):
                    err_msg = u'{}. Please, contact administrator.'.format(err)
                else:
                    err_msg = err.message
                if not db_pod.is_deleted:
                    utils.send_event_to_user(
                        'notify:error', {'message': err_msg},
                        db_pod.owner_id)
            raise
        pod.set_status(POD_STATUSES.pending, send_update=True)
        db.session.commit()
        return pod.as_dict()


def _ensure_old_dns_record_removed(pod_domain):
    # ensure that old record does not overlap wildcard record
    record_type = 'CNAME' if current_app.config['AWS'] else 'A'
    ok, message = dns_management.delete_record(
        pod_domain, record_type)
    if not ok:
        msg = 'Error during deleting of old dns record: {}'.format(message)
        raise APIError(msg)


def update_service(pod):
    """Update pod services to new port configuration in pod.
    Patch services if ports changed, delete services if ports deleted.
    If no service already exist, then do nothing, because all services
    will be created on pod start in method run_service

    """
    ports, public_ports = get_ports(pod)
    local_svc = update_local_ports(pod.id, ports)
    if local_svc is None:
        pod.service = None
    public_svc = update_public_ports(pod.id, pod.namespace,
                                     public_ports, pod.owner)
    if public_svc is None:
        pod.public_aws = None


def update_public_ports(pod_id, namespace, ports, owner):
    svc_provider = get_service_provider()
    services = svc_provider.get_by_pods(pod_id)
    if services and services[pod_id]:
        svc = services[pod_id]
        public_svc = svc_provider.update_ports(svc, ports)
        if public_svc is None:
            del_public_ports_policy(namespace)
        else:
            set_public_ports_policy(namespace, ports, owner)
        return public_svc


def update_local_ports(pod_id, ports):
    local_provider = LocalService()
    services = local_provider.get_by_pods(pod_id)
    if services and services[pod_id]:
        svc = services[pod_id]
        return local_provider.update_ports(svc, ports)


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


def run_service(pod, annotations=None):
    """Run all required services for pod, if such services not exist already
    Args:
        pod: kapi/Pod object
    Returns:
        tuple with local and public services
        or None if service already exist or not needed

    """
    resolve = getattr(pod, 'kuberdock_resolve', [])
    domain = getattr(pod, 'domain', None)
    ports, public_ports = get_ports(pod)
    publicIP = getattr(pod, 'public_ip', None)
    if publicIP == 'true':
        publicIP = None
    public_svc = ingress_public_ports(pod.id, pod.namespace,
                                      public_ports, pod.owner, publicIP,
                                      domain, annotations)
    cluster_ip = getattr(pod, 'podIP', None)
    local_svc = ingress_local_ports(pod.id, pod.namespace, ports,
                                    resolve, cluster_ip)
    return local_svc, public_svc


def ingress_local_ports(pod_id, namespace, ports,
                        resolve=None, cluster_ip=None):
    """Ingress local ports to service
    :param: pod_id: pod id
    :param: namespace: pod namespace
    :param: ports: list of ports to ingress, see get_ports
    :param: cluster_ip: cluster_ip to use in service. Optional.
    """
    local_svc = LocalService()
    services = local_svc.get_by_pods(pod_id)
    if not services and ports:
        service = local_svc.get_template(pod_id, ports, resolve)
        service = local_svc.set_clusterIP(service, cluster_ip)
        rv = local_svc.post(service, namespace)
        podutils.raise_if_failure(rv, "Could not ingress local ports")
        return rv


def ingress_public_ports(pod_id, namespace, ports, owner, publicIP=None,
                         domain=None, annotations=None):
    """Ingress public ports with cloudprovider specific methods
    :param pod_id: pod id
    :param namespace: pod namespace
    :param ports: list of ports to ingress, see get_ports
    :param owner: pod owner
    :param publicIP: publicIP to ingress. Optional.
    :param domain: domain of a pod. Optional, only used in shared IP case
    """
    # For now in shared IP case a pod needs to have a rechable 80 port
    # Which ingress frontend uses to proxy traffic. It does not need the public
    # service, but needs a public port policy
    if domain:
        shared_ip_ports = [{'name': 'c0-p80',
                            'protocol': 'TCP',
                            'port': '80',
                            'targetPort': '80'}]
        set_public_ports_policy(namespace, shared_ip_ports, owner)
        return

    svc = get_service_provider()
    services = svc.get_by_pods(pod_id)
    if not services and ports:
        service = svc.get_template(pod_id, ports, annotations)
        if not current_app.config['AWS']:
            service = svc.set_publicIP(service, publicIP)
        rv = svc.post(service, namespace)
        podutils.raise_if_failure(rv, "Could not ingress public ports")
        set_public_ports_policy(namespace, ports, owner)
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


def set_public_ports_policy(namespace, ports, owner):
    """
    Add/Update Network Policy for Public Ports
    :param namespace: pod namespace
    :param ports: list of public ports
    :param owner: pod owner
    """
    del_public_ports_policy(namespace)
    _get_network_policy_api().post(
        ['networkpolicys'],
        json.dumps(allow_public_ports_policy(ports, owner)),
        rest=True,
        ns=namespace,
    )


def del_public_ports_policy(namespace):
    """
    Remove Network Policy for Public Ports
    :param namespace: pod namespace
    """
    _get_network_policy_api().delete(
        ['networkpolicys', PUBLIC_PORT_POLICY_NAME],
        ns=namespace,
    )


def change_pv_size(persistent_disk_id, new_size, dry_run=False,
                   update_stat=True):
    max_size = int(
        SystemSettings.get_by_name(settings_keys.PERSISTENT_DISK_MAX_SIZE)
        or 0
    )
    if max_size and max_size < new_size:
        raise PVResizeFailed(
            'Volume size can not be greater than {} Gb'.format(max_size)
        )
    storage = pstorage.STORAGE_CLASS()
    ok, changed_pod_ids = storage.resize_pv(persistent_disk_id, new_size,
                                            dry_run=dry_run,
                                            update_stat=update_stat)
    if dry_run or not (ok and changed_pod_ids):
        return ok, changed_pod_ids
    pc = PodCollection()
    for pod_id, restart_required in changed_pod_ids:
        # Check RC for the pod already exists, if it is not, then skip
        # updating
        pod = pc._get_by_id(pod_id)
        rc = KubeQuery().get(
            ['replicationcontrollers', pod.sid], ns=pod.namespace
        )
        failed, _ = podutils.is_failed_k8s_answer(rc)
        if failed:
            continue
        pod = DBPod.query.filter(DBPod.id == pod_id).first()
        config = pod.get_dbconfig()
        volumes = config.get('volumes', [])
        annotations = [vol.pop('annotation') for vol in volumes]
        pc.patch_running_pod(
            pod_id,
            {
                'metadata': {
                    'annotations': {
                        'kuberdock-volume-annotations': json.dumps(annotations)
                    }
                },
            },
            replace_lists=True,
            restart=restart_required
        )
    return ok, changed_pod_ids


@celery.task(ignore_result=True)
def pod_set_unpaid_state_task():
    q = DBPod.query.filter(DBPod.unpaid.is_(True),
                           DBPod.status.notin_([POD_STATUSES.stopping,
                                                POD_STATUSES.deleted,
                                                POD_STATUSES.unpaid]))
    for db_pod in q:
        try:
            PodCollection.stop_unpaid(
                PodCollection()._get_by_id(db_pod.id), lock=True)
        except PodIsLockedError as err:
            current_app.logger.warning(
                u'pod_set_unpaid_state_task failed for pod: {}'.format(err))


def reject_replica_with_pv(config, key='volumes_public'):
    """Check if pod have both persisten volumes and replicas more then 1
    and raise APIError if so.
    :param config: pods db config
    """
    have_pvs = any([True for volume in config.get(key, [])
                    if 'persistentDisk' in volume])
    if have_pvs and config.get('replicas', 1) > 1:
        raise APIError("We don't support replications for pods with PV yet")


def validate_domains(pod_config):
    if pod_config.get('public_access_type') != PublicAccessType.DOMAIN:
        return

    pod_domain = pod_config.get('domain')  # type: str
    base_domain = pod_config.get('base_domain')  # type: str

    if not base_domain:
        raise ValidationError(
            details={'base_domain': 'Base domain cannot be empty when '
                                    'public access type is "domain"'})

    db_base_domain = BaseDomain.filter_by(name=base_domain).first()
    if not db_base_domain:
        raise ValidationError(
            details={'base_domain': 'Base domain "{}" not found'
                                    .format(base_domain)})

    if pod_domain:
        errors = []
        try:
            sub_domain_part, base_domain_part = pod_domain.split('.', 1)
        except ValueError:
            errors.append({'domain': 'Domain "{}" is not subdomain of "{}"'
                                     .format(pod_domain, base_domain)})
        else:
            if base_domain_part != base_domain:
                errors.append({'domain': 'Domain "{}" is not subdomain of "{}"'
                                         .format(pod_domain, base_domain)})
            if PodDomain.filter_by(
                    name=sub_domain_part, base_domain=db_base_domain).first():
                errors.append({'domain': 'Pod domain "{}" already exists'
                                         .format(pod_domain)})

        if errors:
            raise ValidationError(details=errors)
