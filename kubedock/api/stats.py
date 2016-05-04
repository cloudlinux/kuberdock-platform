import pytz
from flask import Blueprint, jsonify
from ..core import db
from ..stats import StatWrap5Min
from ..pods.models import Pod
from ..kubedata.kubestat import KubeStat
from ..rbac import check_permission
import time
import datetime
from collections import defaultdict, namedtuple
from ..login import auth_required
from ..utils import all_request_params, APIError, PermissionDenied, KubeUtils

stats = Blueprint('stats', __name__, url_prefix='/stats')


@stats.route('/', methods=['GET'], strict_slashes=False)
@auth_required
def unit_stat():
    user = KubeUtils._get_current_user()
    params = all_request_params()
    pod_id = params.get('unit')
    container = params.get('container')
    node = params.get('node')

    if (node is not None and not check_permission('get', 'nodes') or
            pod_id is not None and not check_permission('get', 'pods')):
        raise PermissionDenied()

    # start = request.args.get('start')
    # end = request.args.get('end')
    start = time.time() - 3600  # An hour distance

    limits = None
    if node is None:
        if pod_id is not None:
            pod = Pod.query.filter(Pod.owner_id == user.id,
                                   Pod.id == pod_id).first()
            if pod is None:
                raise APIError('Pod not found', 404, 'PodNotFound')

            limits = pod.get_limits(container)
            if container is None:
                data, disks = get_unit_data(pod_id, start)
            else:
                data, disks = get_container_data(pod_id, container, start)
    else:
        capacity = dict(KubeStat._get_nodes_info()).get(node)
        if capacity is not None:
            limits = namedtuple('Limits', ['cpu', 'memory'])(
                capacity['cores'], capacity['memory'])
        data, disks = get_node_data(node, start)

    metrics = [
        {'title': 'CPU', 'ylabel': '%', 'series': [{'label': 'cpu load'}],
            'lines': 1, 'points': []},

        {'title': 'Memory', 'ylabel': 'MB', 'series': [{'label': 'used',
                                                        'fill': True}],
            'lines': 1, 'points': []},

        {'title': 'Network', 'ylabel': 'bps',
         'series': [{'label': 'in', 'fill': True}, {'label': 'out'}],
         'seriesColors': ['#50f460', '#4bb2c5'],
         'lines': 2, 'points': []}]

    if limits is not None:
        for graph in metrics[:2]:
            graph['series'].insert(
                0, {'label': 'limit' if node is None else 'available'})
            graph['lines'] += 1

    for record in sorted(data):
        timetick = datetime.datetime.fromtimestamp(record[0], pytz.UTC)
        metrics[0]['points'].append(
            [timetick, record[1]] if limits is None else
            [timetick, limits.cpu * 100, record[1]])
        metrics[1]['points'].append(
            [timetick, record[2]] if limits is None else
            [timetick, limits.memory, record[2]])
        metrics[2]['points'].append([timetick, record[3], record[4]])

    # AC-2223: we can't monitor container's network separately
    if container is not None:
        metrics.pop()

    if disks:
        disk_metrics = {}
        for record in sorted(disks.items()):
            timetick = datetime.datetime.fromtimestamp(record[0], pytz.UTC)
            disk_data = process_disks(record[1], timetick, ['/dev/rbd'])
            for key, value in disk_data.items():
                if key not in disk_metrics:
                    disk_metrics[key] = {
                        'title': key, 'ylabel': 'GB',
                        'series': [{'fill': True, 'label': 'used'},
                                   {'label': 'available'}],
                        'seriesColors': ['#ff5800', '#4bb2c5'],
                        'lines': 2, 'points': []}
                disk_metrics[key]['points'].append(value)
        metrics.extend(disk_metrics.values())

    return jsonify({
        'status': 'OK',
        'data': metrics})


def process_disks(data, tick, to_skip=None):
    if to_skip is None:
        to_skip = []
    disks = {}
    for item in data:
        for entry in item.split(';'):
            try:
                disk, usage, limit = entry.split(':')
                if any([disk.startswith(i) for i in to_skip]):
                    continue
                if disk not in disks:
                    disks[disk] = [tick, [], []]
                disks[disk][1].append(int(usage))
                disks[disk][2].append(int(limit))
            except ValueError:
                continue
    for d in disks:
        disks[d][1] = round(((sum(disks[d][1]) / len(disks[d][1])) /
                             1073741824.0), 2)
        disks[d][2] = round(((sum(disks[d][2]) / len(disks[d][2])) /
                             1073741824.0), 2)
    return disks


def get_node_data(node, start, end=None):
    data = db.session.query(
        StatWrap5Min.time_window,
        db.func.sum(StatWrap5Min.cpu),
        db.func.avg(StatWrap5Min.memory),
        db.func.sum(StatWrap5Min.rxb),
        db.func.sum(StatWrap5Min.txb)
    ).filter(
        StatWrap5Min.time_window >= start,
        StatWrap5Min.unit_name == '/',
        StatWrap5Min.container == '/',
        StatWrap5Min.host == node
    ).group_by(
        StatWrap5Min.time_window)
    disks = db.session.query(
        StatWrap5Min.time_window,
        StatWrap5Min.fs_data
    ).filter(
        StatWrap5Min.time_window >= start,
        StatWrap5Min.unit_name == '/',
        StatWrap5Min.container == '/',
        StatWrap5Min.host == node)
    organized = defaultdict(list)
    for record in disks:
        organized[record[0]].append(record[1])
    return data, organized


def get_unit_data(pod_id, start, end=None):
    data = db.session.query(
        StatWrap5Min.time_window,
        db.func.sum(StatWrap5Min.cpu),
        db.func.avg(StatWrap5Min.memory),
        db.func.sum(StatWrap5Min.rxb),
        db.func.sum(StatWrap5Min.txb)
    ).filter(
        StatWrap5Min.time_window >= start,
        StatWrap5Min.unit_name == pod_id,
    ).group_by(
        StatWrap5Min.time_window)
    return data, None


def get_container_data(pod_id, container, start, end=None):
    data = db.session.query(
        StatWrap5Min.time_window,
        db.func.sum(StatWrap5Min.cpu),
        db.func.avg(StatWrap5Min.memory),
        db.func.sum(StatWrap5Min.rxb),
        db.func.sum(StatWrap5Min.txb)
    ).filter(
        StatWrap5Min.time_window >= start,
        StatWrap5Min.unit_name == pod_id,
        StatWrap5Min.container.like('k8s_' + container + '%'),
    ).group_by(
        StatWrap5Min.time_window)
    return data, None
