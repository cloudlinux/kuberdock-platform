"""Utils to extract logs from elasticsearch services."""
from datetime import datetime, timedelta

from .elasticsearch_utils import execute_es_query
from .podcollection import PodCollection, POD_STATUSES
from .nodes import get_kuberdock_logs_pod_name
from ..nodes.models import Node
from ..users.models import User
from ..usage.models import ContainerState as CS
from ..utils import APIError


class LogsPodIsNotRunning(APIError):
    message = 'Logs service is collecting data. Wait few minutes please.'


def get_container_logs(container_name, owner_id=None, size=100,
                       start=None, end=None):
    """Get logs from specified container.

    :param container_name: kuberdock container id
    :param owner_id: owner of the containers
    :param start: minimum log time to select (see log_query doc)
    :param end: maximum log time to select (see log_query doc)
    :param size: limits selection to this number (100 by default) (see log_query doc)
    """
    states = CS.in_range(start, end).filter(CS.container_name == container_name)
    if owner_id is not None:
        states = states.filter(CS.pod.any(owner_id=owner_id)).all()

    # TODO: get logs in one es query
    series = []
    for container_state in states:
        node = Node.get_by_name(container_state.pod_state.hostname)
        host = None if node is None else node.ip
        docker_id = container_state.docker_id
        logs = log_query('docker-*', [{'term': {'container_id': docker_id}}],
                         host, size, start, end)
        hits = [line['_source'] for line in logs.get('hits', [])]
        series.append({
            'total': logs.get('total', len(hits)),
            'hits': hits,
            'exit_code': container_state.exit_code,
            'reason': container_state.reason,
            'start': container_state.start_time,
            'end': container_state.end_time,
        })
        size -= len(hits)
        if size <= 0:
            break

    return series


def get_node_logs(hostname, date, size=100, host=None):
    """Extracts node's logs by query to node's elasticsearch.
    :param hostname: name of the host to get logs
    :param date: date of logs
    :param size: limit selection to this number (default = 100) (see log_query doc)
    :param host: node ip to use or None to search all nodes
    Records will be ordered by timestamp in descending order.
    TODO: add ordering parameter support.
    """
    index = 'syslog-'
    date = date or datetime.utcnow().date()
    index += date.strftime('%Y.%m.%d')
    logs = log_query(index, [{'term': {'host': hostname}}], host, size)
    hits = [line['_source'] for line in logs.get('hits', [])]
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
    If 'starttime' was specified, then will be selected records not younger than
    that time.
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
    order = {'time_nano': {
        'order': 'desc',
        'missing': '@timestamp',
        'unmapped_type': 'string',
    }}
    try:
        result = execute_es_query(index, query, size, order, host)
    except Exception:
        if host and not check_logs_pod(host):
            raise LogsPodIsNotRunning()
        raise
    return result


def check_logs_pod(host):
    """
    Check if service pod with elasticsearch and fluentd is running
    at least a minute on the node.

    :param host: node hostname
    :returns: True, if pod is running
    """
    node = Node.query.filter_by(ip=host).first()
    if node is None or node.state != 'running':
        return

    for pod in PodCollection(User.get_internal()).get(False):
        if pod.get('name') != get_kuberdock_logs_pod_name(node.hostname):
            continue
        if pod.get('status') != POD_STATUSES.running:
            return
        container_states = CS.query.filter(
            CS.pod_state.has(pod_id=pod.get('id'), end_time=None),
            CS.end_time.is_(None),
            CS.start_time < (datetime.utcnow() - timedelta(minutes=1)),
            CS.container_name.in_(['elasticsearch', 'fluentd']),
        ).distinct(CS.container_name).order_by(CS.container_name).all()
        return len(container_states) == 2
    return
