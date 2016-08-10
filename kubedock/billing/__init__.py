from .models import Kube, Package, ExtraTax, PackageKube
from kubedock.system_settings.models import SystemSettings


def kubes_to_limits(count, kube_type):
    kube = Kube.query.get(kube_type)

    resources = {
        'cpu': '{0}'.format(count * kube.cpu),
        'memory': int(count * kube.memory * 1024 * 1024)    # was in MB
    }
    return {'resources': {
        'requires': resources,
        'limits': resources,
    }}


def repr_limits(count, kube_type):
    kube = Kube.query.get(kube_type)

    cpu = '{0} {1}'.format(count * kube.cpu, kube.cpu_units)
    memory = '{0} {1}'.format(count * kube.memory, kube.memory_units)

    return {'cpu': cpu, 'memory': memory}


def has_billing():
    billing_type = SystemSettings.get_by_name('billing_type').lower()
    if billing_type == 'no billing':
        return False
    return True
