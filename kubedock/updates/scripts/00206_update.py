from time import sleep

from kubedock import dns_management
from kubedock import settings
from kubedock.constants import (
    KUBERDOCK_BACKEND_POD_NAME,
    KUBERDOCK_INGRESS_POD_NAME,
    KUBERDOCK_INGRESS_CONFIG_MAP_NAME,
    KUBERDOCK_INGRESS_CONFIG_MAP_NAMESPACE,
)
from kubedock.domains.models import BaseDomain, PodDomain
from kubedock.kapi import ingress
from kubedock.kapi.configmap import ConfigMapClient, ConfigMapNotFound
from kubedock.kapi.helpers import KubeQuery
from kubedock.kapi.podcollection import PodCollection
from kubedock.pods.models import Pod
from kubedock.users.models import User


def _recreate_ingress_pod_if_needed():
    kd_user = User.get_internal()
    ingress_pod = Pod.filter_by(name=KUBERDOCK_INGRESS_POD_NAME,
                                owner=kd_user).first()
    if ingress_pod:
        PodCollection(kd_user).delete(ingress_pod.id, force=True)
        default_backend_pod = Pod.filter_by(name=KUBERDOCK_BACKEND_POD_NAME,
                                            owner=kd_user).first()
        if not default_backend_pod:
            raise Exception(
                'Nginx ingress controller pod exists, but default backend pod '
                'is not found. Something wrong. Please contact support to get '
                'help.')
        PodCollection(kd_user).delete(default_backend_pod.id, force=True)
        c = ConfigMapClient(KubeQuery())
        try:
            c.delete(name=KUBERDOCK_INGRESS_CONFIG_MAP_NAME,
                     namespace=KUBERDOCK_INGRESS_CONFIG_MAP_NAMESPACE)
        except ConfigMapNotFound:
            pass
        sleep(30)  # TODO: Workaround. Remove it when AC-5470 will be fixed
        ingress.prepare_ip_sharing()


def _update_dns_records():
    record_type = 'CNAME' if settings.AWS else 'A'

    ingress_pod_exists = bool(Pod.filter_by(name=KUBERDOCK_INGRESS_POD_NAME,
                                            owner=User.get_internal()).first())

    for base_domain in BaseDomain.query.all():
        if not ingress_pod_exists:
            raise Exception(
                'There is no ingress controller pod, but some base domains '
                'found. Something wrong. Please contact support to get help.')
        domain = '*.{}'.format(base_domain.name)
        ok, message = dns_management.create_or_update_record(
            domain, record_type)
        if not ok:
            raise Exception(
                'Failed to create DNS record for domain "{domain}": {reason}'
                .format(domain=domain, reason=message))

    for pod_domain in PodDomain.query.all():
        domain = '{}.{}'.format(pod_domain.name, pod_domain.base_domain.name)
        ok, message = dns_management.delete_record(domain, record_type)
        if not ok:
            raise Exception(
                'Cannot delete old DNS record for domain "{domain}": {reason}'
                .format(domain=domain, reason=message))


def upgrade(upd, *args, **kwargs):
    upd.print_log('Recreate ingress pod if needed...')
    _recreate_ingress_pod_if_needed()
    upd.print_log('Update dns records...')
    _update_dns_records()


def downgrade(*args, **kwargs):
    pass
