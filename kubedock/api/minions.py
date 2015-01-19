from flask import Blueprint, request, current_app, jsonify, Response
import socket
from . import route
from .. import tasks
from ..models import Minion
from ..core import db

bp = Blueprint('minions', __name__, url_prefix='/minions')


def get_minions_collection():
    kub_coll = tasks.get_all_minions.delay()
    new_flag = False
    minions = []
    oldcur = Minion.query.all()
    db_ips = [minion.ip for minion in oldcur]
    kub_items = kub_coll.wait()['items']
    active_ips = [x['id'] for x in kub_items]
    for ip in active_ips:
        if ip not in db_ips:
            new_flag = True
            try:
                hostname = socket.gethostbyaddr(ip)[0]
            except socket.error:
                hostname = ip
            # TODO add resources capacity etc from kub_items[ip] if needed
            m = Minion(ip=ip, hostname=hostname, status='')
            db.session.add(m)
    if new_flag:
        db.session.commit()
        cur = Minion.query.all()
    else:
        cur = oldcur
    for minion in cur:
        minions.append({
            'id': minion.id,
            'ip': minion.ip,
            'hostname': minion.hostname,
            'status': 'running' if minion.ip in active_ips else 'troubles',
            'annotations': minion.annotations,
            'labels': minion.labels,
        })
    return minions


@route(bp, '/', methods=['GET'])
def get_list():
    return jsonify({'status': 'OK', 'data': get_minions_collection()})


@route(bp, '/<minion_id>/', methods=['GET'])
def get_one_minion(minion_id):
    kub_coll = tasks.get_all_minions.delay()
    active_ips = []
    map((lambda x: active_ips.append(x['id'])), kub_coll.wait()['items'])
    m = db.session.query(Minion).get(minion_id)
    if m:
        data = {
            'id': m.id,
            'ip': m.ip,
            'hostname': m.hostname,
            'status': 'running' if m.ip in active_ips else 'troubles',
            'annotations': m.annotations,
            'labels': m.labels,
        }
        return jsonify({'status': 'OK', 'data': data})
    else:
        return jsonify({'status': "Minion {0} doesn't exists".format(minion_id)}), 404


@route(bp, '/', methods=['POST'])
def create_item():
    data = request.json
    m = db.session.query(Minion).filter_by(ip=data['ip']).first()
    if not m:
        temp = dict(filter((lambda t: t[1] != ''), data.items()))
        m = Minion(**temp)
        db.session.add(m)
        db.session.commit()
        r = tasks.add_new_minion.delay(m.ip)    # TODO send labels, annotations, capacity etc.
        # r.wait()                              # maybe result?
        data.update({'id': m.id})
        return jsonify({'status': 'OK', 'data': data})
    else:
        return jsonify({'status': 'Conflict: Minion with ip "{0}" already exists'.format(m.ip)}), 409


@route(bp, '/<minion_id>/', methods=['PUT'])
def put_item(minion_id):
    m = db.session.query(Minion).get(minion_id)
    if m:
        data = request.json
        # after some validation, including ip unique...
        data = dict(filter((lambda item: item[1] != ''), data.items()))
        m.ip = data['ip']
        m.hostname = data['hostname']
        db.session.add(m)
        db.session.commit()
        return jsonify({'status': 'OK', 'data': data})
    else:
        return jsonify({'status': "Minion " + minion_id + " doesn't exists"}), 404


@route(bp, '/<minion_id>/', methods=['DELETE'])
def delete_item(minion_id):
    m = db.session.query(Minion).get(minion_id)
    if m:
        res = tasks.remove_minion_by_ip.delay(m.ip)
        db.session.delete(m)
        db.session.commit()
        res = res.wait()
        if res['status'] == 'Failure':
            return jsonify({'status': '{0}. {1} Code: {2}'.format(res['status'], res['message'], res['code'])})
    return jsonify({'status': 'OK'})


@route(bp, '/checkhost/<host_addr>/', methods=['GET'])
def check_host(host_addr):
    try:
        ip = socket.gethostbyname(host_addr)
    except socket.error:
        return jsonify({'status': 'FAIL'})
    if ip == host_addr:
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except socket.error:
            hostname = ip
        return jsonify({'status': 'OK', 'ip': ip, 'hostname': hostname})
    else:
        return jsonify({'status': 'OK', 'ip': ip, 'hostname': host_addr})