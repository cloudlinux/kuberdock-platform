from datetime import datetime, timedelta

from flask import Blueprint
from sqlalchemy.exc import DataError

from kubedock.exceptions import APIError, InternalAPIError
from kubedock.kapi import node_utils
from kubedock.kapi.podcollection import PodNotFound
from kubedock.kubedata import kubestat
from kubedock.login import auth_required
from kubedock.nodes.models import Node
from kubedock.pods.models import Pod
from kubedock.rbac import check_permission
from kubedock.utils import KubeUtils

stats = Blueprint('stats', __name__, url_prefix='/stats')


class NodeNotRunning(APIError):
    message = 'Node is not running'


@stats.route('/nodes/<hostname>', methods=['GET'])
@auth_required
@check_permission('get', 'nodes')
@KubeUtils.jsonwrap
def nodes(hostname):
    end = datetime.now()
    start = end - timedelta(minutes=60)

    node = Node.get_by_name(hostname)
    if node is None:
        raise APIError('Unknown node', 404)

    if node.state != 'completed':
        raise NodeNotRunning

    resources = node_utils.get_one_node(node.id)['resources']

    if resources:
        data = kubestat.get_node_stat(hostname, start, end)
        cpu_capacity = float(resources.get('cpu')) * 1000
        memory_capacity = float(resources.get('memory'))
    else:
        # We have checked that node is running, but no resources means
        # that node is not running
        raise InternalAPIError(
            'DBNode is running, but k8s says it does not. Unknown error')

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


@stats.route('/pods/<pod_id>', methods=['GET'])
@auth_required
@check_permission('get', 'pods')
@KubeUtils.jsonwrap
def pods(pod_id):
    end = datetime.now()
    start = end - timedelta(minutes=60)

    _check_if_pod_exists(pod_id)
    data = kubestat.get_pod_stat(pod_id, start, end)
    diagrams = [
        CpuDiagram(_get_cpu_points(data)).to_dict(),
        MemoryDiagram(_get_memory_points(data)).to_dict(),
        NetworkDiagram(_get_network_points(data)).to_dict()
    ]
    return diagrams


@stats.route('/pods/<pod_id>/containers/<container_id>', methods=['GET'])
@auth_required
@check_permission('get', 'pods')
@KubeUtils.jsonwrap
def containers(pod_id, container_id):
    end = datetime.now()
    start = end - timedelta(minutes=60)

    _check_if_pod_exists(pod_id)
    data = kubestat.get_container_stat(pod_id, container_id, start, end)
    diagrams = [
        CpuDiagram(_get_cpu_points(data)).to_dict(),
        MemoryDiagram(_get_memory_points(data)).to_dict(),
    ]
    return diagrams


def _check_if_pod_exists(pod_id):
    user = KubeUtils.get_current_user()
    try:
        pod = Pod.filter(Pod.owner_id == user.id, Pod.id == pod_id).first()
        if pod is None:
            raise PodNotFound
    except DataError:
        # pod_id is not uuid
        raise PodNotFound


def _get_cpu_points(data, cpu_limit=None):
    if not data:
        return []
    if cpu_limit is None:
        return [
            (usage.time, 0.1 * limit.value, 0.1 * usage.value)
            for limit, usage
            in zip(data['cpu/request'], data['cpu/usage_rate'])
            ]
    else:
        return [
            (usage.time, 0.1 * cpu_limit, 0.1 * usage.value)
            for usage
            in data['cpu/usage_rate']
            ]


def _get_memory_points(data, memory_limit=None):
    if not data:
        return []
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
    if not data:
        return []
    return [
        (rxb.time, rxb.value, txb.value)
        for rxb, txb
        in zip(data['network/rx_rate'], data['network/tx_rate'])
        ]


def _get_fs_points(data):
    if not data:
        return []
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
