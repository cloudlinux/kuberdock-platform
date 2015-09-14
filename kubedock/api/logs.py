"""API for logs retreiving.
"""
from flask import Blueprint, request, jsonify

from ..utils import parse_datetime_str
from ..kapi import es_logs


logs = Blueprint('logs', __name__, url_prefix='/logs')


@logs.route('/container/<host>/<containerid>', methods=['GET'])
def api_get_container_logs(host, containerid):
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
    starttime = gettime_parameter(request.args, 'starttime')
    endtime = gettime_parameter(request.args, 'endtime')
    try:
        size = int(request.args.get('size', None))
    except (TypeError, ValueError):
        size = 100
    return jsonify(es_logs.get_container_logs(
        host, containerid, size, starttime, endtime
    ))


@logs.route('/node/<host>/<date>', methods=['GET'])
def api_get_node_logs(host, date):
    """Extracts node's logs by query to node's elasticsearch.
    Optional parameters (submitted via ?key=value&...):
        hostname - name of the host to get logs
        size - limit selection to this number (default = 100)
    Records will be ordered by timestamp in descending order.
    TODO: add ordering parameter support.
    """
    try:
        size = int(request.args.get('size', None))
    except (TypeError, ValueError):
        size = 100
    date = parse_datetime_str(date)
    hostname = request.args.get('hostname')
    return jsonify(es_logs.get_node_logs(host, date, size, hostname))


def gettime_parameter(args, param):
    """Extracts parameter from args dict and converts it to datetime object.
    If parameter doesn't exist or can;t be converted to datetime, then return
    None.

    """
    value = args.get(param, None)
    if not value:
        return None
    return parse_datetime_str(value)
