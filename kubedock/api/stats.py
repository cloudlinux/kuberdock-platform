from datetime import datetime, timedelta

from flask import Blueprint

from kubedock.exceptions import APIError
from kubedock.kapi import node_utils
from kubedock.kubedata import kubestat
from kubedock.nodes.models import Node
from kubedock.pods.models import Pod
from ..login import auth_required
from ..rbac import check_permission
from ..utils import KubeUtils, all_request_params

stats = Blueprint('stats', __name__, url_prefix='/stats')


class PodNotFoundError(APIError):
    status_code = 404
    message = 'Pod not found'


class WrongParametersError(APIError):
    message = "Wrong parameters"


@stats.route('/', methods=['GET'], strict_slashes=False)
@auth_required
@KubeUtils.jsonwrap
def get():
    params = all_request_params()
    node = params.get('node')
    pod_id = params.get('unit')
    end = datetime.now()
    start = end - timedelta(minutes=60)
    if node is not None:
        check_permission('get', 'nodes').check()
        return get_node_data(node, start, end)
    elif pod_id is not None:
        check_permission('get', 'pods').check()
        user = KubeUtils.get_current_user()
        pod = Pod.filter(Pod.owner_id == user.id, Pod.id == pod_id).first()
        if pod is None:
            raise PodNotFoundError
        container = params.get('container')
        if container is None:
            return get_pod_data(pod_id, start, end)
        else:
            return get_container_data(pod_id, container, start, end)
    else:
        raise WrongParametersError


def get_node_data(node_name, start, end):
    node = Node.get_by_name(node_name)
    if node is None:
        raise APIError('Unknown node')
    data = kubestat.get_node_stat(node_name, start, end)
    resources = node_utils.get_one_node(node.id)['resources']
    cpu_capacity = resources['cpu']
    memory_capacity = resources['memory']
    diagrams = [
                   CpuDiagram(
                       _get_cpu_points(data, cpu_capacity)).to_dict(),
                   MemoryDiagram(
                       _get_memory_points(data, memory_capacity)).to_dict(),
                   NetworkDiagram(
                       _get_network_points(data)).to_dict()
               ] + [
                   FsDiagram(
                       fs_data['points'], title=fs_data['device']).to_dict()
                   for fs_data in _get_fs_points(data)
                   ]
    return diagrams


def get_pod_data(pod_id, start, end):
    data = kubestat.get_pod_stat(pod_id, start, end)
    diagrams = [
        CpuDiagram(_get_cpu_points(data)).to_dict(),
        MemoryDiagram(_get_memory_points(data)).to_dict(),
        NetworkDiagram(_get_network_points(data)).to_dict()
    ]
    return diagrams


def get_container_data(pod_id, container_id, start, end):
    data = kubestat.get_container_stat(pod_id, container_id, start, end)
    diagrams = [
        CpuDiagram(_get_cpu_points(data)).to_dict(),
        MemoryDiagram(_get_memory_points(data)).to_dict(),
    ]
    return diagrams


def _get_cpu_points(data, cpu_limit=None):
    if cpu_limit is None:
        return [
            (limit.time, 100.0, 100.0 * float(usage.value) / limit.value)
            for limit, usage
            in zip(data['cpu/request'], data['cpu/usage_rate'])
            ]
    else:
        return [
            (usage.time, 100.0, 0.1 * usage.value / float(cpu_limit))
            for usage
            in data['cpu/usage_rate']
            ]


def _get_memory_points(data, memory_limit=None):
    if memory_limit is None:
        return [
            (limit.time, _mb(limit.value), _mb(usage.value))
            for limit, usage
            in zip(data['memory/request'], data['memory/usage'])
            ]
    else:
        return [
            (usage.time, _mb(memory_limit), _mb(usage.value))
            for usage
            in data['memory/usage']
            ]


def _get_network_points(data):
    return [
        (rxb.time, rxb.value, txb.value)
        for rxb, txb
        in zip(data['network/rx_rate'], data['network/tx_rate'])
        ]


def _get_fs_points(data):
    return [
        {
            'device': limits['resource_id'],
            'points': [
                (limit.time, _gb(limit.value), _gb(usage.value))
                for limit, usage
                in zip(limits['values'], usages['values'])
                ]
        }
        for limits, usages
        in zip(data['filesystem/limit'], data['filesystem/usage'])
        ]


def _gb(bytes_):
    return bytes_ / 1073741824.0


def _mb(bytes_):
    return bytes_ / 1048576.0


class Diagram(object):
    title = 'Title'
    ylabel = 'ylabel',
    series = [{'label': 'series_title', 'fill': True}]
    series_colors = None
    points = []

    def __init__(self, points, **kwargs):
        self.points = points
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        result = {
            'title': self.title,
            'ylabel': self.ylabel,
            'series': self.series,
            'lines': len(self.series),
            'points': self.points
        }
        if self.series_colors:
            result['seriesColors'] = self.series_colors
        return result


class CpuDiagram(Diagram):
    title = 'CPU'
    ylabel = '%'
    series = [{'label': 'available'}, {'label': 'cpu load'}]


class MemoryDiagram(Diagram):
    title = 'Memory'
    ylabel = 'MB'
    series = [{'label': 'available'}, {'label': 'used', 'fill': True}]


class NetworkDiagram(Diagram):
    title = 'Network'
    ylabel = 'bps'
    series = [{'label': 'in', 'fill': 'true'}, {'label': 'out'}]
    series_colors = ['#50f460', '#4bb2c5']


class FsDiagram(Diagram):
    ylabel = 'GB'
    series = [{'label': 'available'}, {'label': 'used', 'fill': True}]
    series_colors = ['#4bb2c5', '#ff5800']
