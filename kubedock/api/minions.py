from flask import Blueprint, request, jsonify
import socket
from .. import tasks
from ..models import Minion
from ..core import db, check_permission
from ..validation import check_int_id, check_minion_data, ipv4_addr
from ..validation import hostname as hostname_regex
from . import APIError

minions = Blueprint('minions', __name__, url_prefix='/minions')

node_is_active = lambda x: x['status']['conditions'][0]['status'] == 'Full'


@check_permission('get', 'minions')
def get_minions_collection():
    new_flag = False
    oldcur = Minion.query.all() # TODO values
    db_hosts = [minion.hostname for minion in oldcur]
    kub_hosts = {x['id']: x for x in tasks.get_all_minions()}
    for host in kub_hosts:
        if host not in db_hosts:
            new_flag = True
            try:
                resolved_ip = socket.gethostbyname(host)
            except socket.error:
                raise APIError(
                    "Hostname {0} can't be resolved to ip during auto-scan. Check /etc/hosts file for correct minion records"
                    .format(host))
            # TODO add resources capacity etc from kub_hosts[host] if needed
            m = Minion(ip=resolved_ip, hostname=host)
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
            'status': 'running' if minion.hostname in kub_hosts and node_is_active(kub_hosts[minion.hostname]) else 'troubles',
            'annotations': minion.annotations,
            'labels': minion.labels,
        })
    return minions


@minions.route('/', methods=['GET'])
def get_list():
    return jsonify({'status': 'OK', 'data': get_minions_collection()})


@minions.route('/<minion_id>', methods=['GET'])
@check_permission('get', 'minions')
def get_one_minion(minion_id):
    check_int_id(minion_id)
    m = db.session.query(Minion).get(minion_id)
    if m:
        res = tasks.get_minion_by_host(m.hostname)
        if res['status'] == 'Failure':
            raise APIError("Error. Minion exists in db but don't exists in kubernetes", status_code=404)
        data = {
            'id': m.id,
            'ip': m.ip,
            'hostname': m.hostname,
            'status': 'running' if node_is_active(res) else 'troubles',
            'annotations': m.annotations,
            'labels': m.labels,
        }
        return jsonify({'status': 'OK', 'data': data})
    else:
        raise APIError("Error. Minion {0} doesn't exists".format(minion_id), status_code=404)


@minions.route('/', methods=['POST'])
@check_permission('create', 'minions')
def create_item():
    data = request.json
    check_minion_data(data)
    m = db.session.query(Minion).filter_by(hostname=data['hostname']).first()
    if not m:
        m = Minion(ip=data['ip'], hostname=data['hostname'])
        db.session.add(m)
        db.session.commit()
        r = tasks.add_new_minion.delay(m.hostname)    # TODO send labels, annotations, capacity etc.
        # r.wait()                              # maybe result?
        data.update({'id': m.id})
        return jsonify({'status': 'OK', 'data': data})
    else:
        raise APIError('Conflict, minion with hostname "{0}" already exists'.format(m.hostname), status_code=409)


@minions.route('/<minion_id>', methods=['PUT'])
@check_permission('edit', 'minions')
def put_item(minion_id):
    check_int_id(minion_id)
    m = db.session.query(Minion).get(minion_id)
    if m:
        data = request.json
        check_minion_data(data)
        if data['ip'] != m.ip:
            raise APIError("Error. Minion ip can't be reassigned, you need delete it and create new.")
        new_ip = socket.gethostbyname(data['hostname'])
        if new_ip != m.ip:
            raise APIError("Error. Minion ip can't be reassigned, you need delete it and create new.")
        m.hostname = data['hostname']
        db.session.add(m)
        db.session.commit()
        return jsonify({'status': 'OK', 'data': data})
    else:
        raise APIError("Error. Minion {0} doesn't exists".format(minion_id), status_code=404)


@minions.route('/<minion_id>', methods=['DELETE'])
@check_permission('delete', 'minions')
def delete_item(minion_id):
    check_int_id(minion_id)
    m = db.session.query(Minion).get(minion_id)
    if m:
        db.session.delete(m)
        db.session.commit()
        res = tasks.remove_minion_by_host(m.hostname)
        if res['status'] == 'Failure':
            raise APIError('Failure. {0} Code: {1}'.format(res['message'], res['code']), status_code=200)
    return jsonify({'status': 'OK'})


@minions.route('/checkhost/<hostname>', methods=['GET'])
def check_host(hostname):
    try:
        int(hostname)
    except ValueError:
        if ipv4_addr.match(hostname):
            raise APIError("Provide hostname, not ip address")
        if not hostname_regex.match(hostname):
            raise APIError("Invalid hostname")
        try:
            ip = socket.gethostbyname(hostname)
            return jsonify({'status': 'OK', 'ip': ip, 'hostname': hostname})
        except socket.error:
            raise APIError("Hostname can't be resolved. Check /etc/hosts file for correct minion records")
    else:
        raise APIError("Invalid hostname")