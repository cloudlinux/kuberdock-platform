from kubedock import dns_management
from kubedock import settings
from kubedock.domains.models import BaseDomain, PodDomain

DNS_RECORD_TYPE = 'CNAME' if settings.AWS else 'A'


def upgrade(*args, **kwargs):
    for base_domain in BaseDomain.query.all():
        domain = '*.{}'.format(base_domain.name)
        ok, message = dns_management.create_or_update_record(
            domain, DNS_RECORD_TYPE)
        if not ok:
            raise Exception('Failed to create DNS record '
                            'for domain "{domain}": {reason}'
                            .format(domain=domain, reason=message))
    for pod_domain in PodDomain.query.all():
        domain = '{}.{}'.format(pod_domain.name, pod_domain.base_domain.name)
        dns_management.delete_record(domain, DNS_RECORD_TYPE)


def downgrade(*args, **kwargs):
    pass
