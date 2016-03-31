"""API for logs retreiving.
"""
import pytz

from flask import Blueprint, request, jsonify, Response
from flask.ext.login import current_user

from ..rbac import check_permission
from ..decorators import login_required_or_basic_or_token
from ..utils import parse_datetime_str, KubeUtils
from ..kapi import es_logs, usage
from ..users.models import User
from ..pods.models import Pod
from ..nodes.models import Node
from . import APIError


logs = Blueprint('logs', __name__, url_prefix='/logs')


@logs.route('/container/<pod_id>/<container_id>', methods=['GET'])
@login_required_or_basic_or_token
def api_get_container_logs(pod_id, container_id):
    """Return logs from specified container.
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
    user = KubeUtils._get_current_user()
    starttime = gettime_parameter(request.args, 'starttime')
    endtime = gettime_parameter(request.args, 'endtime')
    try:
        size = int(request.args.get('size', None))
    except (TypeError, ValueError):
        size = 100
    owner = User.get(user.username)
    mime = request.accept_mimetypes.best_match(['application/json',
                                                'text/plain'])

    logs = es_logs.get_container_logs(pod_id, container_id, owner.id,
                                      size, starttime, endtime)

    if mime == 'text/plain' or request.args.get('text', False):
        # return logs as .txt document
        logs_text = []
        for serie in logs[::-1]:
            logs_text.append((serie['start'].replace(tzinfo=pytz.UTC),
                              'Started'))
            logs_text.extend((line['@timestamp'], line['log'].strip('\n'))
                             for line in serie['hits'][::-1])
            if serie['end']:
                msg = ('Exited successfully'
                       if serie['exit_code'] in (0, -2) else 'Falied')
                if serie['reason']:
                    msg = '{0} ({1})'.format(msg, serie['reason'])
                logs_text.append((serie['end'].replace(tzinfo=pytz.UTC),
                                  msg + '\n'))
        timezone = pytz.timezone(current_user.timezone)
        logs_text = '\n'.join(
            '{0}: {1}'.format(time.astimezone(timezone).isoformat(), msg)
            for time, msg in logs_text)
        headers = {'content-disposition': (
            'attachment; filename="{0}_{1}_logs.txt"'.format(
                pod_id, container_id))}
        return Response(logs_text, content_type='text/plain', headers=headers)
    return jsonify({'status': 'OK', 'data': logs})


@logs.route('/node/<hostname>', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'nodes')
@KubeUtils.jsonwrap
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
    node = Node.query.filter_by(hostname=hostname).first()
    if not node:
        raise APIError('Unknown node', 404)
    return es_logs.get_node_logs(hostname, date, size, host=node.ip)


@logs.route('/pod-states/<pod_id>/<depth>', methods=['GET'])
@login_required_or_basic_or_token
@KubeUtils.jsonwrap
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
    if not pod:
        raise APIError(u'Unknown pod {}'.format(pod_id), 404)
    user = KubeUtils._get_current_user()
    if not(user.is_administrator() or user.id == pod.owner_id):
        raise APIError(u'Forbidden for current user', 403)
    try:
        depth = int(depth)
        if depth < 1:
            depth = 0
    except (TypeError, ValueError):
        depth = 1
    return usage.select_pod_states_history(pod_id, depth)


def gettime_parameter(args, param):
    """Extracts parameter from args dict and converts it to datetime object.
    If parameter doesn't exist or can;t be converted to datetime, then return
    None.

    """
    value = args.get(param, None)
    if not value:
        return None
    return parse_datetime_str(value)
