import os
from contextlib import contextmanager
from string import Template

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
        if _is_default_backend_exists(kd_user):
            return

        backend_config = _get_default_backend_config()
        validation.check_internal_pod_data(backend_config, kd_user)
        backend_pod = PodCollection(kd_user).add(backend_config,
                                                 skip_check=True)
        PodCollection(kd_user).update(
            backend_pod['id'], {'command': 'synchronous_start'})

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
    if _is_ingress_controller_exists(kd_user):
        return
    _check_free_ips()

    def _create_pod():
        default_backend_pod = Pod.query.filter_by(
            name=KUBERDOCK_BACKEND_POD_NAME,
            owner=kd_user).first()

        if not default_backend_pod:
            raise DefaultBackendNotReady(
                'No Default HTTP Backend Pod can be found')

        default_backend_pod_config = default_backend_pod.get_dbconfig()

        backend_ns = default_backend_pod_config['namespace']
        backend_svc = default_backend_pod_config.get('service', None)

        if backend_svc is None:
            raise DefaultBackendNotReady(
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

    def _on_error(e):
        current_app.logger.exception(
            'Tried to create an Ingress Controller service '
            'pod but got an error.'
        )

    handled_exceptions = (IntegrityError, APIError)

    try:
        utils.retry_with_catch(_create_pod, max_tries=5, retry_pause=10,
                               exc_types=handled_exceptions,
                               callback_on_error=_on_error)
    except handled_exceptions as e:
        raise IngressControllerNotReady(e.message)


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

    return config


def _check_cluster_email():
    """Check if cluster email is not empty"""
    if SystemSettings.get_by_name(keys.EXTERNAL_SYSTEMS_AUTH_EMAIL):
        return
    raise APIError('Email for external services is empty')


def _create_ingress_nginx_configmap():
    client = ConfigMapClient(KubeQuery())
    default_nginx_settings = {'server-name-hash-bucket-size': '128'}

    try:
        client.create(
            data=default_nginx_settings,
            metadata={'name': KUBERDOCK_INGRESS_CONFIG_MAP_NAME},
            namespace=KUBERDOCK_INGRESS_CONFIG_MAP_NAMESPACE)
    except ConfigMapAlreadyExists:
        pass
    except Exception as e:
        current_app.logger.exception(
            'Could not create ConfigMap for Ingress Controller')
        raise IngressConfigMapError(e.message)


def _is_default_backend_exists(kd_user):
    return bool(Pod.filter_by(name=KUBERDOCK_BACKEND_POD_NAME,
                              owner=kd_user).first())


def _is_ingress_controller_exists(kd_user):
    return bool(Pod.filter_by(name=KUBERDOCK_INGRESS_POD_NAME,
                              owner=kd_user).first())


def _is_nginx_config_map_exists():
    try:
        ConfigMapClient(KubeQuery()).get(
            name=KUBERDOCK_INGRESS_CONFIG_MAP_NAME,
            namespace=KUBERDOCK_INGRESS_CONFIG_MAP_NAMESPACE)
        return True
    except ConfigMapNotFound:
        return False


def _check_free_ips():
    if current_app.config['AWS']:
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
        _is_default_backend_exists(kd_user),
        _is_ingress_controller_exists(kd_user),
        _is_nginx_config_map_exists(),
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
