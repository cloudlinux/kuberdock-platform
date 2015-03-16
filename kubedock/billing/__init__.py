from .models import Kube, Package


def kubes_to_limits(count, kube_type, version='v1beta1'):
    kube = Kube.query.get(kube_type)

    resources = {'cpu': int(count * kube.cpu),
                 'memory': int(count * kube.memory * 1024 * 1024)}   # was in MB
    if version == 'v1beta1':
        return resources
    return {'resources': {
        'requires': resources,
        'limits': resources,
    }}