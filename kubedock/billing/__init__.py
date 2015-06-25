from .models import Kube, Package, ExtraTax


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
