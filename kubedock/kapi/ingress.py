import os
from contextlib import contextmanager
from string import Template
from time import sleep

import yaml
from flask import current_app
from sqlalchemy.exc import IntegrityError

from .configmap import (
    ConfigMapClient, ConfigMapAlreadyExists, ConfigMapNotFound
)
from .helpers import KubeQuery
from .podcollection import PodCollection
from .. import settings
from .. import utils
from .. import validation
from ..billing.models import Kube
from ..constants import (
    AWS_UNKNOWN_ADDRESS,
    KUBERDOCK_BACKEND_POD_NAME,
    KUBERDOCK_INGRESS_POD_NAME,
    KUBERDOCK_INGRESS_CONFIG_MAP_NAME,
    KUBERDOCK_INGRESS_CONFIG_MAP_NAMESPACE,
)
from ..exceptions import (
    APIError,
    DefaultBackendNotReady,
    IngressControllerNotReady,
    IngressConfigMapError
)
from ..kd_celery import celery
from ..pods.models import Pod, IPPool
from ..system_settings import keys
from ..system_settings.models import SystemSettings
from ..users.models import User

DEFAULT_BACKEND_CONFIG_FILE = 'default_backend_config.yaml'
INGRESS_CONFIG_FILE = 'ingress_config.yaml'
INGRESS_NGINX_SETTINGS_FILE = 'ingress_nginx_settings.yaml'


def _find_template(template_name):
    """Finds template in templates dir and returns full path."""
    return os.path.join(settings.ASSETS_PATH, template_name)


def _read_template(template_name, template_vars):
    """Reads template, substitutes variables and loads yaml as dict."""
    with open(_find_template(template_name)) as f:
        t = Template(f.read())
    s = t.safe_substitute(**template_vars)
    rv = yaml.safe_load(s)
    return rv


def _create_default_backend_pod():
    """
    Create Default Backend pod that serving 404 response for Ingress Controller
    """
    kd_user = User.get_internal()

    def _create_pod():
        if _get_default_backend(kd_user):
            current_app.logger.debug('Default backend exists. Skip')
            return

        backend_config = _get_default_backend_config()
        validation.check_internal_pod_data(backend_config, kd_user)
        backend_pod = PodCollection(kd_user).add(backend_config,
                                                 skip_check=True)
        PodCollection(kd_user).update(
            backend_pod['id'], {'command': 'synchronous_start'})
        current_app.logger.debug('Default created and started')

    def _on_error(e):
        current_app.logger.exception(
            'Tried to create a Default HTTP Backend service '
            'pod but got an error.'
        )

    handled_exceptions = (IntegrityError, APIError)
    # pod already exists or an error occurred during it's
    # creation

    try:
        utils.retry_with_catch(_create_pod, max_tries=5, retry_pause=1,
                               exc_types=handled_exceptions,
                               callback_on_error=_on_error)
    except handled_exceptions as e:
        raise DefaultBackendNotReady(details=e.message)


def _create_ingress_controller_pod():
    """Create Ingress Controller pod"""
    kd_user = User.get_internal()

    # Check if pod is already exists and if not - check free public ip for it
    if _get_ingress_controller(kd_user):
        current_app.logger.debug('Ingress controller exists. Skip')
        return
    _check_free_ips()

    def _create_pod():
        default_backend_pod = _get_default_backend(kd_user)

        if not default_backend_pod:
            raise IngressControllerNotReady(
                'No Default HTTP Backend Pod can be found')

        default_backend_pod_config = default_backend_pod.get_dbconfig()
        backend_ns, backend_svc = _get_backend_address(
            default_backend_pod_config)

        if backend_svc is None:
            raise IngressControllerNotReady(
                'Cannot get service name of Default HTTP Backend Pod')

        email = SystemSettings.get_by_name(
            keys.EXTERNAL_SYSTEMS_AUTH_EMAIL)
        ingress_config = _get_ingress_pod_config(backend_ns, backend_svc,
                                                 email)
        validation.check_internal_pod_data(ingress_config, kd_user)
        ingress_pod = PodCollection(kd_user).add(ingress_config,
                                                 skip_check=True)
        PodCollection(kd_user).update(
            ingress_pod['id'], {'command': 'synchronous_start'})
        current_app.logger.debug('Ingress controller created and started')
        return ingress_pod['id']

    def _on_error(e):
        current_app.logger.exception(
            'Tried to create an Ingress Controller service '
            'pod but got an error.'
        )

    handled_exceptions = (IntegrityError, APIError)

    try:
        pod_id = utils.retry_with_catch(
            _create_pod, max_tries=5, retry_pause=10,
            exc_types=handled_exceptions, callback_on_error=_on_error)
    except handled_exceptions as e:
        raise IngressControllerNotReady(e.message)

    public_address = _wait_for_pod_public_address(kd_user, pod_id)

    if public_address:
        current_app.logger.debug(
            'Public address of ingress controller: %s', public_address)
    else:
        raise APIError(
            'Failed to get public address of ingress controller pod')


def _wait_for_pod_public_address(owner, pod_id):
    tries = 30
    interval = 2

    rv = None

    if current_app.config['AWS']:
        public_address_field = 'public_aws'
    else:
        public_address_field = 'public_ip'
    none_values = (None, AWS_UNKNOWN_ADDRESS)

    for _ in range(tries):
        pod = PodCollection(owner).get(pod_id, as_json=False)
        public_address = pod[public_address_field]
        if public_address in none_values:
            sleep(interval)
            continue
        else:
            rv = public_address
            break

    return rv


def _get_backend_address(default_backend_pod_config):
    backend_ns = default_backend_pod_config['namespace']
    backend_svc = default_backend_pod_config.get('service', None)
    return backend_ns, backend_svc


def _get_default_backend_config():
    """Return config of k8s default http backend pod."""
    template_vars = {
        'name': KUBERDOCK_BACKEND_POD_NAME,
        'kube_type': Kube.get_internal_service_kube_type()
    }
    return _read_template(DEFAULT_BACKEND_CONFIG_FILE, template_vars)


def _get_ingress_pod_config(backend_ns, backend_svc, email, ip='10.254.0.100'):
    """Return config of k8s ingress controller pod."""
    template_vars = {
        'name': KUBERDOCK_INGRESS_POD_NAME,
        'kube_type': Kube.get_internal_service_kube_type(),
        'backend_ns': backend_ns,
        'backend_svc': backend_svc,
        'ingress_configmap_ns': KUBERDOCK_INGRESS_CONFIG_MAP_NAMESPACE,
        'ingress_configmap_name': KUBERDOCK_INGRESS_CONFIG_MAP_NAME,
        'email': email,
        'pod_ip': ip
    }
    config = _read_template(INGRESS_CONFIG_FILE, template_vars)

    if settings.IS_PRODUCTION_PKG:
        config['containers'][1]['env'].append(
            {
                "name": "LEGO_URL",
                "value": "https://acme-v01.api.letsencrypt.org/directory"
            }
        )

    if current_app.config['AWS']:
        config['service_annotations'] = {
            'service.beta.kubernetes.io/aws-load-balancer-proxy-protocol': '*'
        }

    return config


def _get_ingress_nginx_settings():
    # In AWS case ELB uses proxy protocol, so we need to enable it on Ingress
    # Controller as well
    if current_app.config['AWS']:
        params = {'use_proxy_protocol': 'true'}
    else:
        params = {'use_proxy_protocol': 'false'}
    return _read_template(INGRESS_NGINX_SETTINGS_FILE, params)


def _check_cluster_email():
    """Check if cluster email is not empty"""
    if SystemSettings.get_by_name(keys.EXTERNAL_SYSTEMS_AUTH_EMAIL):
        return
    raise APIError('Email for external services is empty')


def _create_ingress_nginx_configmap():
    client = ConfigMapClient(KubeQuery())

    try:
        client.create(
            data=_get_ingress_nginx_settings(),
            metadata={'name': KUBERDOCK_INGRESS_CONFIG_MAP_NAME},
            namespace=KUBERDOCK_INGRESS_CONFIG_MAP_NAMESPACE)
        current_app.logger.debug('Nginx configmap created')
    except ConfigMapAlreadyExists:
        current_app.logger.debug('Nginx configmap exists. Skip')
        pass
    except Exception as e:
        current_app.logger.exception(
            'Could not create ConfigMap for Ingress Controller')
        raise IngressConfigMapError(e.message)


def _get_default_backend(kd_user):
    return Pod.filter_by(name=KUBERDOCK_BACKEND_POD_NAME,
                         owner=kd_user).first()


def _get_ingress_controller(kd_user):
    return Pod.filter_by(name=KUBERDOCK_INGRESS_POD_NAME,
                         owner=kd_user).first()


def _get_nginx_config_map():
    try:
        return ConfigMapClient(KubeQuery()).get(
            name=KUBERDOCK_INGRESS_CONFIG_MAP_NAME,
            namespace=KUBERDOCK_INGRESS_CONFIG_MAP_NAMESPACE)
    except ConfigMapNotFound:
        return None


def _check_free_ips():
    if not current_app.config['AWS']:
        IPPool.get_free_host()


@contextmanager
def _notify_on_errors_context(*err_types):
    """Context that send notifies to admin on errors"""
    try:
        yield
    except err_types as e:
        utils.send_event_to_role(
            'notify:error', {'message': e.message}, 'Admin')


def is_subsystem_up():
    """Check if ip sharing subsystem is up.

    Returns True if ready otherwise False.
    """
    kd_user = User.get_internal()
    return all((
        _get_default_backend(kd_user),
        _get_ingress_controller(kd_user),
        _get_nginx_config_map(),
    ))


def check_subsystem_up_preconditions():
    """Check some preconditions that must be satisfied before system up."""
    _check_cluster_email()
    _check_free_ips()


def prepare_ip_sharing():
    """Bring up all components of sharing iP subsystem."""
    check_subsystem_up_preconditions()
    _create_default_backend_pod()
    _create_ingress_nginx_configmap()
    _create_ingress_controller_pod()


@celery.task(ignore_results=True)
def prepare_ip_sharing_task():
    """Run `prepare_ip_sharing` asynchronously."""
    with _notify_on_errors_context(APIError):
        return prepare_ip_sharing()
