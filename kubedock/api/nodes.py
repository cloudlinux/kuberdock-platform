from flask import Blueprint, request, jsonify
import socket
from .. import tasks
from ..models import Node
from ..core import db, check_permission
from ..validation import check_int_id, check_node_data, check_hostname
from . import APIError

nodes = Blueprint('nodes', __name__, url_prefix='/nodes')


def _node_is_active(x):
    try:
        return x['status']['conditions'][0]['status'] == 'Full'
    except KeyError:
        return False


@check_permission('get', 'nodes')
def get_nodes_collection():
    # TODO handle kube_type during auto-scan
    new_flag = False
    oldcur = Node.query.all()
    db_hosts = [node.hostname for node in oldcur]
    kub_hosts = {x['id']: x for x in tasks.get_all_nodes()}
    for host in kub_hosts:
        if host not in db_hosts:
            new_flag = True
            try:
                resolved_ip = socket.gethostbyname(host)
            except socket.error:
                raise APIError(
                    "Hostname {0} can't be resolved to ip during auto-scan."
                    "Check /etc/hosts file for correct Node records"
                    .format(host))
            # TODO add resources capacity etc from kub_hosts[host] if needed
            m = Node(ip=resolved_ip, hostname=host)
            db.session.add(m)
    if new_flag:
        db.session.commit()
        cur = Node.query.all()
    else:
        cur = oldcur
    nodes_list = []
    for node in cur:
        nodes_list.append({
            'id': node.id,
            'ip': node.ip,
            'hostname': node.hostname,
            'status': 'running' if node.hostname in kub_hosts and
                                    _node_is_active(kub_hosts[node.hostname])
                                else 'troubles',
            'annotations': node.annotations,
            'labels': node.labels,
        })
    return nodes_list


@nodes.route('/', methods=['GET'])
def get_list():
    return jsonify({'status': 'OK', 'data': get_nodes_collection()})


@nodes.route('/<node_id>', methods=['GET'])
@check_permission('get', 'nodes')
def get_one_node(node_id):
    # render here kube type
    check_int_id(node_id)
    m = db.session.query(Node).get(node_id)
    if m:
        res = tasks.get_node_by_host(m.hostname)
        if res['status'] == 'Failure':
            raise APIError(
                "Error. Node exists in db but don't exists in kubernetes",
                status_code=404)
        data = {
            'id': m.id,
            'ip': m.ip,
            'hostname': m.hostname,
            'status': 'running' if _node_is_active(res) else 'troubles',
            'annotations': m.annotations,
            'labels': m.labels,
        }
        return jsonify({'status': 'OK', 'data': data})
    else:
        raise APIError("Error. Node {0} doesn't exists".format(node_id),
                       status_code=404)


@nodes.route('/', methods=['POST'])
@check_permission('create', 'nodes')
def create_item():
    data = request.json
    check_node_data(data)
    m = db.session.query(Node).filter_by(hostname=data['hostname']).first()
    if not m:
        m = Node(ip=data['ip'], hostname=data['hostname'])
        db.session.add(m)
        db.session.commit()
        r = tasks.add_new_node.delay(m.hostname, data.get('kube_type', 0))
        # r.wait()                              # maybe result?
        data.update({'id': m.id})
        return jsonify({'status': 'OK', 'data': data})
    else:
        raise APIError(
            'Conflict, Node with hostname "{0}" already exists'
            .format(m.hostname), status_code=409)


@nodes.route('/<node_id>', methods=['PUT'])
@check_permission('edit', 'nodes')
def put_item(node_id):
    check_int_id(node_id)
    m = db.session.query(Node).get(node_id)
    if m:
        data = request.json
        check_node_data(data)
        if data['ip'] != m.ip:
            raise APIError("Error. Node ip can't be reassigned, "
                           "you need delete it and create new.")
        new_ip = socket.gethostbyname(data['hostname'])
        if new_ip != m.ip:
            raise APIError("Error. Node ip can't be reassigned, "
                           "you need delete it and create new.")
        m.hostname = data['hostname']
        db.session.add(m)
        db.session.commit()
        return jsonify({'status': 'OK', 'data': data})
    else:
        raise APIError("Error. Node {0} doesn't exists".format(node_id),
                       status_code=404)


@nodes.route('/<node_id>', methods=['DELETE'])
@check_permission('delete', 'nodes')
def delete_item(node_id):
    check_int_id(node_id)
    m = db.session.query(Node).get(node_id)
    if m:
        db.session.delete(m)
        db.session.commit()
        res = tasks.remove_node_by_host(m.hostname)
        if res['status'] == 'Failure':
            raise APIError('Failure. {0} Code: {1}'
                           .format(res['message'], res['code']),
                           status_code=200)
    return jsonify({'status': 'OK'})


@nodes.route('/checkhost/<hostname>', methods=['GET'])
def check_host(hostname):
    check_hostname(hostname)
    ip = socket.gethostbyname(hostname)
    return jsonify({'status': 'OK', 'ip': ip, 'hostname': hostname})