
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

"""Utils to extract logs from elasticsearch services."""
import hashlib
from datetime import datetime, timedelta

from dateutil.parser import parse as parse_dt

from .elasticsearch_utils import execute_es_query, LogsError
from .nodes import get_kuberdock_logs_pod_name
from .podcollection import PodCollection, POD_STATUSES
from ..core import ConnectionPool
from ..exceptions import APIError
from ..nodes.models import Node
from ..usage.models import ContainerState as CS
from ..users.models import User
from ..utils import NODE_STATUSES
from ..settings import KUBERDOCK_INTERNAL_USER
from ..login import current_user


CONTAINER_POSTFIX = 'Contact the administrator if the problem persists.'


def get_container_logs(pod_id, container_name, owner_id=None, size=100,
                       start=None, end=None):
    """Get logs from specified container.

    :param pod_id: kuberdock pod id
    :param container_name: kuberdock container id
    :param owner_id: owner of the containers
    :param start: minimum log time to select (see log_query doc)
    :param end: maximum log time to select (see log_query doc)
    :param size: limits selection to this number (100 by default)
        (see log_query doc)
    """
    states = CS.in_range(start, end).filter(
        CS.container_name == container_name,
        CS.pod_state.has(pod_id=pod_id))
    if owner_id is not None:
        states = states.filter(CS.pod.has(owner_id=owner_id)).all()

    # TODO: get logs in one es query
    series = []
    for container_state in states:
        node = Node.get_by_name(container_state.pod_state.hostname)
        host = None if node is None else node.ip
        docker_id = container_state.docker_id
        try:
            logs = log_query('docker-*',
                             [{'term': {'container_id': docker_id}}],
                             host, size, start, end)
        except LogsError as err:
            # Show detailed error messages for kuberdock-internal user and
            # a generic one for other users in case of
            # LogsError.CONNECTION_ERROR and LogsError.INTERNAL_ERROR
            err_msg = CONTAINER_POSTFIX
            if current_user.username == KUBERDOCK_INTERNAL_USER:
                err_msg = err.message
            if err.error_code == LogsError.NO_LOGS:
                logs = {}
            elif err.error_code == LogsError.CONNECTION_ERROR:
                raise APIError(
                    'Failed to get logs. {0}'.format(err_msg),
                    status_code=503
                )
            elif err.error_code == LogsError.POD_ERROR:
                raise APIError(err.message, status_code=502)
            elif err.error_code == LogsError.INTERNAL_ERROR:
                raise APIError(
                    'Internal logs error. {0}'.format(err_msg),
                    status_code=500
                )
            else:
                raise APIError(
                    'Contact the administrator. '
                    'Unknown logs error occurred: {0}'.format(err.message),
                    status_code=500
                )
        except Exception as err:
            raise APIError('Contact the administrator. '
                           'Unknown error occurred: {0}'.format(err),
                           status_code=500)
        hits = [line['_source'] for line in logs.get('hits', [])]
        for hit in hits:
            hit['@timestamp'] = parse_dt(hit['@timestamp'])
        series.append({
            'total': logs.get('total', len(hits)),
            'hits': hits,
            'exit_code': container_state.exit_code,
            'reason': container_state.reason,
            'start': container_state.start_time,
            'end': container_state.end_time,
        })
        size -= len(hits) + 2  # start&stop lines
        if size <= 0:
            break

    if not series:
        raise APIError('Pod never been started yet', status_code=404)

    return series


def get_node_logs(hostname, date, size=100, host=None):
    """Extracts node's logs by query to node's elasticsearch.
    :param hostname: name of the host to get logs
    :param date: date of logs
    :param size: limit selection to this number (default = 100)
        (see log_query doc)
    :param host: node ip to use or None to search all nodes
    Records will be ordered by timestamp in descending order.
    TODO: add ordering parameter support.
    """
    index = 'syslog-'
    date = date or datetime.utcnow().date()
    index += date.strftime('%Y.%m.%d')
    try:
        logs = log_query(
            index,
            [{'term': {'host_md5': hashlib.md5(hostname).hexdigest()}}],
            host,
            size
        )
    except LogsError as err:
        if err.error_code == LogsError.NO_LOGS:
            raise APIError(err.message, status_code=404)
        elif err.error_code == LogsError.CONNECTION_ERROR:
            raise APIError('Failed to get logs: {0}'.format(err.message),
                           status_code=503)
        elif err.error_code == LogsError.POD_ERROR:
            raise APIError(err.message, status_code=502)
        elif err.error_code == LogsError.INTERNAL_ERROR:
            raise APIError('Internal logs error: {0}'.format(err.message),
                           status_code=500)
        raise APIError('Unknown logs error: {0}'.format(err.message),
                       status_code=500)
    except Exception as err:
        raise APIError('Unknown error: {0}'.format(err), status_code=500)

    hits = [line['_source'] for line in logs['hits']]
    return {'total': logs.get('total', len(hits)), 'hits': hits}


def log_query(index, filters=None, host=None, size=100, start=None, end=None):
    """Build and execute generic log elasticsearch query.

    :param index: elasticsearch index name
    :param filters: additional filters that will be mixed with time filters
    :param host: node ip to use or None to search all nodes
    :param size: restrict output to this number of records
    :param start: minimum log time to select
    :param end: maximum log time to select

    If no parameters specified, then 100 last log records will be selected.
    If only 'size' was specified, then only that count of last records will be
    selected.
    If 'starttime' was specified, then will be selected records not younger
    than that time.
    If 'endtime' was specified, then will be selected records not older than
    that time.
    Records will be ordered by timestamp in descending order.
    """
    filters = [] if filters is None else filters[:]
    if start or end:
        condition = {}
        if start:
            condition['gte'] = start
        if end:
            condition['lt'] = end
        filters.append({'range': {'@timestamp': condition}})
    query = {'filtered': {'filter': {'and': filters}}}
    order = {'time_nano':
        {'order': 'desc'}
    }
    try:
        result = execute_es_query(index, query, size, order, host)
    except LogsError:
        if host:
            error = check_logs_pod(host)
            if error:
                raise LogsError(error, LogsError.POD_ERROR)
        raise
    return result


def check_logs_pod(host):
    """
    Wrapper for cache logging pod state in Redis

    :param host: See _check_logs_pod
    :return: See _check_logs_pod
    """
    redis = ConnectionPool.get_connection()
    key = 'logging_state_{0}'.format(host)
    value = redis.get(key)

    if value is None:
        value = _check_logs_pod(host)
        redis.setex(key, 60, value)

    return value


def _check_logs_pod(host):
    """
    Check if service pod with elasticsearch and fluentd is running
    at least a minute on the node.

    :param host: node hostname
    :returns: True, if pod is running
    """
    node = Node.query.filter_by(ip=host).first()
    if node is None:
        return 'Node not found ({0})'.format(host)
    elif node.state not in (NODE_STATUSES.completed, NODE_STATUSES.running):
        return 'Node is in {0} state'.format(node.state)

    pod_name = get_kuberdock_logs_pod_name(node.hostname)

    for pod in PodCollection(User.get_internal()).get(as_json=False):
        if pod.get('name') != pod_name:
            continue
        pod_status = pod.get('status')
        if pod_status == POD_STATUSES.pending:
            return 'Logging service is starting. Please wait...'
        elif pod_status == POD_STATUSES.failed:
            return 'Failed to collect logs on {0}'.format(node.hostname)
        elif pod_status == POD_STATUSES.stopped:
            return 'Logging service stopped for {0}'.format(node.hostname)
        elif pod_status != POD_STATUSES.running:
            return 'Unknown logging service state ({0})'.format(pod_status)
        container_states = CS.query.filter(
            CS.pod_state.has(pod_id=pod.get('id'), end_time=None),
            CS.end_time.is_(None),
            CS.start_time < (datetime.utcnow() - timedelta(minutes=1)),
            CS.container_name.in_(['elasticsearch', 'fluentd']),
        ).distinct(CS.container_name).order_by(CS.container_name).all()
        if len(container_states) == 2:
            return ''
        else:
            return ('Logging service start takes more than 1 minute for '
                    '{0}'.format(node.hostname))
    return 'No logging service enabled for {0}'.format(node.hostname)
