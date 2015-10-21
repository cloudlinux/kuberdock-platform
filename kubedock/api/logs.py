"""API for logs retreiving.
"""
from flask import Blueprint, request, jsonify
from flask.ext.login import current_user

from ..api import PermissionDenied
from ..rbac import check_permission
from ..usage.models import ContainerState
from ..utils import (login_required_or_basic_or_token, parse_datetime_str,
    KubeUtils)
from ..kapi import es_logs, pod_states
from ..pods.models import Pod
from . import APIError


logs = Blueprint('logs', __name__, url_prefix='/logs')


@logs.route('/container/<containerid>', methods=['GET'])
@login_required_or_basic_or_token
def api_get_container_logs(containerid):
    """Return logs from specified host and container.
    Optional parameters (submitted via ?key=value&...):
        starttime - minimum log time to select
        endtime - maximum log time to select
        size - limits selection to this number (default = 100)
    If no parameters specified, then 100 last log records will be selected.
    If only 'size' was specified, then only that count of last records will be
    selected.
    If 'starttime' was specified, then will be selected records younger than
    that time.
    If 'endtime' was specified, then will be selected records not older than
    endtime.
    Records will be ordered by timestamp in descending order.
    TODO: add ordering parameter support.

    """
    cs = ContainerState.query.filter(
        ContainerState.pod.has(owner=current_user),
        ContainerState.docker_id == containerid,
    ).first()
    if not cs:
        raise PermissionDenied('Denied to {0}'.format(current_user.username))

    starttime = gettime_parameter(request.args, 'starttime')
    endtime = gettime_parameter(request.args, 'endtime')
    try:
        size = int(request.args.get('size', None))
    except (TypeError, ValueError):
        size = 100
    return jsonify(es_logs.get_container_logs(
        containerid, size, starttime, endtime
    ))


@logs.route('/node/<hostname>', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'nodes')
def api_get_node_logs(hostname):
    """Extracts node's logs by query to node's elasticsearch.
    Optional parameters (submitted via ?key=value&...):
        date - date to get logs
        size - limit selection to this number (default = 100)
    Records will be ordered by timestamp in descending order.
    TODO: add ordering parameter support.
    """
    try:
        size = int(request.args.get('size', None))
    except (TypeError, ValueError):
        size = 100
    date = request.args.get('date', None)
    if date:
        date = parse_datetime_str(date)
    return jsonify(es_logs.get_node_logs(hostname, date, size))


@logs.route('/pod-states/<pod_id>/<depth>', methods=['GET'])
@login_required_or_basic_or_token
def api_get_pod_states(pod_id, depth):
    """Extracts pod history.
    :param pod_id: kuberdock pod identifier
    :param depth: number of retrieved history items. 0 - to retrieve all the
        history
    :return: list of dicts. Each item contains fields
        'pod_id' - kuberdock pod identifier
        'hostname' - name of a node where the pod was running
        'start_time' - start time of the pod
        'end_time' - stop time of the pod (if it was stopped)
        'last_event' - last kubernetes event for the pod ('ADDED',
        'MODIFIED', 'DELETED')
        'last_event_time' - time of last kubernetes event for the pod
    """
    pod = Pod.query.filter(Pod.id == pod_id).first()
    user = KubeUtils._get_current_user()
    if not(user.is_administrator() or user.id == pod.owner_id):
        raise APIError(u'Forbidden for current user', 403)
    if not Pod:
        raise APIError(u'Unknown pod {}'.format(pod_id), 404)
    try:
        depth = int(depth)
        if depth < 1:
            depth = 0
    except (TypeError, ValueError):
        depth = 1
    return jsonify({
        'status': 'OK',
        'data': pod_states.select_pod_states_history(pod_id, depth)
    })


def gettime_parameter(args, param):
    """Extracts parameter from args dict and converts it to datetime object.
    If parameter doesn't exist or can;t be converted to datetime, then return
    None.

    """
    value = args.get(param, None)
    if not value:
        return None
    return parse_datetime_str(value)
