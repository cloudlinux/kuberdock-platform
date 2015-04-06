from flask import Blueprint, jsonify, request, current_app
from ..core import db
from ..stats import StatWrap5Min
from ..kubedata.kubestat import KubeUnitResolver
import operator
import itertools
import time
import datetime
from ..utils import login_required_or_basic

stats = Blueprint('stats', __name__, url_prefix='/stats')

@stats.route('/', methods=['GET'])
@login_required_or_basic
def unit_stat():
    uuid = request.args.get('unit', None)
    container = request.args.get('container', None)

    #start = request.args.get('start', None)
    #end = request.args.get('end', None)
    items = KubeUnitResolver().by_unit(uuid)
    current_app.logger.debug(items)

    items_list= map(operator.itemgetter(2), itertools.chain(*items.values()))
    current_app.logger.debug(items_list)
    start = time.time() - 3600  # An hour distance

    if container is None:
        data = get_unit_data(items_list, start)
    else:
        data = get_container_data(items_list, container, start)

    cpu = {'title': 'CPU', 'ylabel': '%', 'lines': 1, 'points': []}
    mem = {'title': 'Memory', 'ylabel': 'MB', 'lines': 1, 'points': []}
    net = {'title': 'Network Usage', 'ylabel': 'bps', 'lines': 2, 'points': []}

    for record in sorted(data, key=operator.itemgetter(0)):
        timetick = datetime.datetime.fromtimestamp(record[0]).strftime("%H:%M")
        cpu['points'].append([timetick, record[1]])
        mem['points'].append([timetick, record[2]])
        net['points'].append([timetick, record[3], record[4]])

    #points = map((lambda x: dict(zip(['time', 'cpu', 'memory', 'rxb', 'txb'], x))),
    #                sorted(data, key=operator.itemgetter(0)))
    #points = {'id': 1, 'points': map((lambda x: [x[0], x[1]]),
    #                sorted(data, key=operator.itemgetter(0)))}
    return jsonify({
        'status': 'OK',
        'data': [cpu, mem, net]})

def get_unit_data(items_list, start, end=None):
    data = db.session.query(
        StatWrap5Min.time_window,
        db.func.sum(StatWrap5Min.cpu),
        db.func.sum(StatWrap5Min.memory),
        db.func.sum(StatWrap5Min.rxb),
        db.func.sum(StatWrap5Min.txb)).filter(
            StatWrap5Min.time_window>=start).filter(
            StatWrap5Min.unit_name.in_(items_list)).group_by(
                StatWrap5Min.time_window)
    return data

def get_container_data(items_list, container, start, end=None):
    data = db.session.query(
        StatWrap5Min.time_window,
        db.func.sum(StatWrap5Min.cpu),
        db.func.sum(StatWrap5Min.memory),
        db.func.sum(StatWrap5Min.rxb),
        db.func.sum(StatWrap5Min.txb)).filter(
            StatWrap5Min.time_window>=start).filter(
                StatWrap5Min.unit_name.in_(items_list)).filter(
                    StatWrap5Min.container.like('k8s_'+container+'%')).group_by(
                StatWrap5Min.time_window)
    return data