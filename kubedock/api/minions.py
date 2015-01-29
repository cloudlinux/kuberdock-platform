from flask import Blueprint, request, current_app, jsonify, Response
import socket
from . import route
from .. import tasks
from ..models import Minion
from ..core import db, check_permission

minions = Blueprint('minions', __name__, url_prefix='/minions')


@check_permission('get', 'minions')
def get_minions_collection():
    new_flag = False
    oldcur = Minion.query.all()
    db_ips = [minion.ip for minion in oldcur]
    kub_ips = {x['id']: x for x in tasks.get_all_minions()}
    for ip in kub_ips:
        if ip not in db_ips:
            new_flag = True
            try:
                hostname = socket.gethostbyaddr(ip)[0]
            except socket.error:
                hostname = ip
            # TODO add resources capacity etc from kub_ips[ip] if needed
            m = Minion(ip=ip, hostname=hostname, status='')
            db.session.add(m)
    if new_flag:
        db.session.commit()
        cur = Minion.query.all()
    else:
        cur = oldcur
    minions = []
    for minion in cur:
        minions.append({
            'id': minion.id,
            'ip': minion.ip,
            'hostname': minion.hostname,
            'status': 'running' if minion.ip in kub_ips and kub_ips[minion.ip]['status']['conditions'][0]['status'] == 'Full' else 'troubles',
            'annotations': minion.annotations,
            'labels': minion.labels,
        })
    return minions


@minions.route('/', methods=['GET'])
def get_list():
    return jsonify({'status': 'OK', 'data': get_minions_collection()})


@minions.route('/<minion_id>/', methods=['GET'])
@check_permission('get', 'minions')
def get_one_minion(minion_id):
    m = db.session.query(Minion).get(minion_id)
    if m:
        res = tasks.get_minion_by_ip(m.ip)
        if res['status'] == 'Failure':
            return jsonify({'status': "Error. Minion exists in db but don't exists in kubernetes"}), 404
        data = {
            'id': m.id,
            'ip': m.ip,
            'hostname': m.hostname,
            'status': 'running' if res['status']['conditions'][0]['status'] == 'Full' else 'troubles',
            'annotations': m.annotations,
            'labels': m.labels,
        }
        return jsonify({'status': 'OK', 'data': data})
    else:
        return jsonify({'status': "Minion {0} doesn't exists".format(minion_id)}), 404


@minions.route('/', methods=['POST'])
@check_permission('create', 'minions')
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


@minions.route('/<minion_id>/', methods=['PUT'])
@check_permission('edit', 'minions')
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


@minions.route('/<minion_id>/', methods=['DELETE'])
@check_permission('delete', 'minions')
def delete_item(minion_id):
    m = db.session.query(Minion).get(minion_id)
    if m:
        db.session.delete(m)
        db.session.commit()
        res = tasks.remove_minion_by_ip(m.ip)
        if res['status'] == 'Failure':
            return jsonify({'status': 'Failure. {0} Code: {1}'.format(res['message'], res['code'])})
    return jsonify({'status': 'OK'})


@minions.route('/checkhost/<host_addr>/', methods=['GET'])
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