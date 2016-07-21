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
from kubedock.utils import KubeUtils, NODE_STATUSES

stats = Blueprint('stats', __name__, url_prefix='/stats')


class NodeNotRunning(APIError):
    message = 'Node is not running'


class InternalStatsError(InternalAPIError):
    pass


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

    if node.state != NODE_STATUSES.completed:
        raise NodeNotRunning

    resources = node_utils.get_one_node(node.id)['resources']

    if resources:
        data = kubestat.get_node_stat(hostname, start, end)
        cpu_capacity = float(resources.get('cpu')) * 1000
        memory_capacity = float(resources.get('memory'))
    else:
        # We have checked that node is running, but no resources means
        # that node is not running
        raise InternalStatsError(
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


def _merge_graphs(base_graph, other_graphs, result_factory):
    """Merge several graphs into one.
    It takes time points from base_graph, and for other graphs it takes
    nearest lesser-or-equal point.
    It needs because sometimes different graphs that must be shown
    on the same draw have close but little different timestamps.
    (E.g. 'memory/request' and 'memory/usage' -- 'memory/request' can have
    less points then 'memory/usage', but they are shown on one draw)

    :param base_graph: Sorted list of `Point` that will be used as source
        of timestamps.
    :param other_graphs: List of sorted list of `Point` that used as
        other graphs.
    :param result_factory: Factory method that produces items of result list.
        It's signature -- (time, point_of_base_graph, *points_of_other_graphs).
    :return List of items that produced by `result_factory` callback.
    """
    rv = []
    los = [0 for _ in other_graphs]
    for b in base_graph:
        time = b.time
        others = []
        for i, other_graph in enumerate(other_graphs):
            z = _floor(other_graph, time, los[i])
            if z < 0:
                others.append(None)
            else:
                others.append(other_graph[z])
                los[i] = z
        rv.append(result_factory(time, b, *others))
    return rv


def _get_cpu_points(data, cpu_limit=None):
    if not data:
        return []
    if cpu_limit is None:
        limits = data.get('cpu/request', [])
        usages = data.get('cpu/usage_rate', [])

        def r_factory(time, usage, limit):
            if limit is None:
                return time, None, _mc2p(usage.value)
            else:
                return time, _mc2p(limit.value), _mc2p(usage.value)

        return _merge_graphs(usages, [limits], r_factory)
    else:
        return [(usage.time, _mc2p(cpu_limit), _mc2p(usage.value))
                for usage
                in data.get('cpu/usage_rate', [])
                ]


def _get_memory_points(data, memory_limit=None):
    if not data:
        return []
    if memory_limit is None:
        limits = data.get('memory/request', [])
        usages = data.get('memory/usage', [])

        def r_factory(time, usage, limit):
            if limit is None:
                return time, None, _mb(usage.value)
            else:
                return time, _mb(limit.value), _mb(usage.value)

        return _merge_graphs(usages, [limits], r_factory)
    else:
        return [
            (usage.time, _mb(memory_limit), _mb(usage.value))
            for usage
            in data.get('memory/usage', [])
            ]


def _get_network_points(data):
    if not data:
        return []
    rx_rate = data.get('network/rx_rate', [])
    tx_rate = data.get('network/tx_rate', [])

    def r_factory(time, rxb, txb):
        return time, rxb.value, txb.value

    return _merge_graphs(rx_rate, [tx_rate], r_factory)


def _get_fs_points(data):
    if not data:
        return []

    def r_factory(time, usage, limit):
        if limit is None:
            return time, None, _gb(usage.value)
        else:
            return time, _gb(limit.value), _gb(usage.value)

    return [
        {
            'device': limits['resource_id'],
            'points': _merge_graphs(
                usages['values'], [limits['values']], r_factory)
        }
        for limits, usages
        in zip(data['filesystem/limit'], data['filesystem/usage'])
        ]


def _mc2p(mlcores):
    """Convert millicores to percents"""
    return 0.1 * mlcores


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


def _floor(a_list, x_time, lo=0, hi=None):
    """
    Find nearest lesser-or-equal point.
    :param a_list: Sorted list of `Point`. Point must have field 'time'.
    :param x_time: Time to search.
    :param lo: Index of point in list from which search will be started.
    :param hi: Index of point in list on which search will be finished.
    :return: Index of nearest lesser-or-equal point or -1 if timestamp of
        first point of list is greater then `x_time`.
    """
    if lo < 0:
        raise ValueError('lo must be non-negative')
    if hi is None:
        hi = len(a_list)
    while lo < hi and x_time >= a_list[lo].time:
        lo += 1
    return lo - 1
