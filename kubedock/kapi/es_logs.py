"""Utils to extract logs from elasticsearch services."""
from .elasticsearch_utils import execute_es_query

def get_container_logs(host, containerid, size, starttime=None, endtime=None):
    """Return logs from specified host and container.
    :param host: hostname or ip address of host where we should connect to
        elasticsearch
    :param containerid: docker container identifier
    :param starttime: minimum log time to select
    :param endtime: maximum log time to select
    :param size: limits selection to this number (default = 100)
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
    index = 'docker-*'
    size = size or 100
    filters = [
        {'term': {'container_id': containerid}}
    ]
    if starttime or endtime:
        condition = {}
        if starttime:
            condition['gte'] = starttime
        if endtime:
            condition['lt'] = endtime

        filters.append({'range': {'@timestamp': condition}})
    query = {'filtered': {'filter': {'and': filters}}}
    return execute_es_query(
        host, index, query, size, {'@timestamp': {'order': 'desc'}}
    )


def get_node_logs(host, date, size, hostname):
    """Extracts node's logs by query to node's elasticsearch.
    :param host: hostname or ip address of host where we should connect to
        elasticsearch
    :param date: date of logs
    :param hostname: name of the host to get logs (one name  or list of names)
    :param size: limit selection to this number (default = 100)
    Records will be ordered by timestamp in descending order.
    TODO: add ordering parameter support.
    """
    size = size or 100
    index = 'syslog-'
    if date:
        index += date.strftime('%Y.%m.%d')
    else:
        index += '*'
    if hostname:
        query = {'filtered': {'filter': {'term': {'host': hostname}}}}
    else:
        query = None

    return execute_es_query(
        host, index, query, size, {'@timestamp': {'order': 'desc'}}
    )
