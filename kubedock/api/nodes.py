from flask import Blueprint, request, jsonify
import json
import math
import operator
import socket
from uuid import uuid4
from .. import tasks
from ..models import Node, User, Pod
from ..core import db
from ..rbac import check_permission
from ..utils import login_required_or_basic
from ..validation import check_int_id, check_node_data, check_hostname
from ..billing import Kube, kubes_to_limits
from ..settings import MASTER_IP
from . import APIError
from .pods import make_config
from fabric.api import run, settings, env
from fabric.tasks import execute


nodes = Blueprint('nodes', __name__, url_prefix='/nodes')


KUBERDOCK_LOGS_MEMORY_LIMIT = 256 * 1024 * 1024


def get_kuberdock_logs_pod_name(node):
    return 'kuberdock-logs-{0}'.format(node)


def get_kuberdock_logs_config(node, name, kube_type, kubes, uuid, master_ip):
    return {
        "node": node,
        "lastAddedImage": "kuberdock/elasticsearch",
        "name": name,
        "replicas": 1,
        "cluster": False,
        "restartPolicy": {
            "always": {}
        },
        "volumes": [
            {
                "name": "docker-containers",
                "source": {
                    "hostDir": {
                        "path": "/var/lib/docker/containers"
                    }
                }
            },
            {
                "name": "es-persistent-storage",
                "source": {
                    "hostDir": {
                        "path": "/var/lib/elasticsearch"
                    }
                }
            }
        ],
        "kube_type": kube_type,
        "id": uuid,
        "containers": [
            {
                "terminationMessagePath": None,
                "name": "fluentd",
                "workingDir": "/root",
                "image": "kuberdock/fluentd:1.0",
                "volumeMounts": [
                    {
                        "readOnly": False,
                        "name": "docker-containers",
                        "mountPath": "/var/lib/docker/containers"
                    }
                ],
                "command": ["./run.sh"],
                "env": [
                    {
                        "name": "NODENAME",
                        "value": node
                    },
                    {
                        "name": "ES_HOST",
                        "value": "127.0.0.1"
                    }
                ],
                "ports": [
                    {
                        "isPublic": False,
                        "protocol": "udp",
                        "containerPort": 5140,
                        "hostPort": 5140
                    }
                ],
                "kubes": kubes
            },
            {
                "terminationMessagePath": None,
                "name": "elasticsearch",
                "workingDir": "",
                "image": "kuberdock/elasticsearch:1.0",
                "volumeMounts": [
                    {
                        "readOnly": False,
                        "name": "es-persistent-storage",
                        "mountPath": "/elasticsearch/data"
                    }
                ],
                "command": ["/elasticsearch/run.sh"],
                "env": [
                    {
                        "name": "MASTER",
                        "value": master_ip
                    }
                ],
                "ports": [
                    {
                        "isPublic": False,
                        "protocol": "tcp",
                        "containerPort": 9200,
                        "hostPort": 9200
                    },
                    {
                        "isPublic": False,
                        "protocol": "tcp",
                        "containerPort": 9300,
                        "hostPort": 9300
                    }
                ],
                "kubes": kubes
            }
        ],
        "portalIP": None
    }


def _node_is_active(x):
    try:
        return x['status']['conditions'][0]['status'] == 'Full'
    except KeyError:
        return False


def _get_node_condition(x):
    try:
        return x['status']['conditions'][0]
    except KeyError:
        return {}


@check_permission('get', 'nodes')
def get_nodes_collection():
    new_flag = False
    oldcur = Node.query.all()
    db_hosts = [node.hostname for node in oldcur]
    kub_hosts = {x['id']: x for x in tasks.get_all_nodes()}
    for host in kub_hosts:
        if host not in db_hosts:
            new_flag = True
            default_kube = Kube.query.get(0)
            try:
                resolved_ip = socket.gethostbyname(host)
            except socket.error:
                raise APIError(
                    "Hostname {0} can't be resolved to ip during auto-scan."
                    "Check /etc/hosts file for correct Node records"
                    .format(host))
            # TODO add resources capacity etc from kub_hosts[host] if needed
            m = Node(ip=resolved_ip, hostname=host, kube=default_kube)
            db.session.add(m)
    if new_flag:
        db.session.commit()
        cur = Node.query.all()
    else:
        cur = oldcur
    nodes_list = []
    for node in cur:
        if node.hostname in kub_hosts:
            if _node_is_active(kub_hosts[node.hostname]):
                node_status = 'running'
                node_reason = ''
            else:
                node_status = 'troubles'
                condition = _get_node_condition(kub_hosts[node.hostname])
                if condition:
                    node_reason = (
                        'Node state is {0}\n'
                        'Reason: "{1}"\n'
                        'Last transition time: {2}'.format(
                            condition['status'],
                            condition['reason'],
                            condition['lastTransitionTime']
                        )
                    )
                else:
                    node_reason = (
                        'Node is a member of KuberDock cluster but '
                        'does not provide information about its condition\n'
                        'Possible reason -- node is in installation progress'
                    )
        else:
            node_status = 'troubles'
            node_reason = (
                'Node is not a member of KuberDock cluster\n'
                'Possible reason is an error during installation'
            )

        nodes_list.append({
            'id': node.id,
            'ip': node.ip,
            'hostname': node.hostname,
            'kube_type': node.kube.id,
            'status': node_status,
            'reason': node_reason,
            'annotations': node.annotations,
            'labels': node.labels,
            'resources': kub_hosts.get(node.hostname, {}).get('resources', {})
        })
    return nodes_list


@nodes.route('/', methods=['GET'])
def get_list():
    return jsonify({'status': 'OK', 'data': get_nodes_collection()})


@nodes.route('/<node_id>', methods=['GET'])
@check_permission('get', 'nodes')
def get_one_node(node_id):
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
            'kube_type': m.kube.id,
            'status': 'running' if _node_is_active(res) else 'troubles',
            'annotations': m.annotations,
            'labels': m.labels,
            'resources': res.get('resources', {})
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
        kube = Kube.query.get(data.get('kube_type', 0))
        m = Node(ip=data['ip'], hostname=data['hostname'], kube=kube)
        logs_kubes = 1
        node_resources = kubes_to_limits(logs_kubes, kube.id)['resources']
        logs_memory_limit = node_resources['limits']['memory']
        if logs_memory_limit < KUBERDOCK_LOGS_MEMORY_LIMIT:
            logs_kubes = int(math.ceil(
                float(KUBERDOCK_LOGS_MEMORY_LIMIT) / logs_memory_limit
            ))
        temp_uuid = str(uuid4())
        ku = User.query.filter_by(username='kuberdock-internal').first()
        logs_id = get_kuberdock_logs_pod_name(data['hostname'])
        logs_config = get_kuberdock_logs_config(data['hostname'], logs_id,
                                                kube.id, logs_kubes, temp_uuid,
                                                MASTER_IP)
        config = make_config(logs_config, logs_id)

        logs_pod = Pod(
            name=logs_id,
            config=json.dumps(logs_config),
            id=temp_uuid,
            status='pending',
            owner=ku,
        )
        db.session.add(m)
        db.session.add(logs_pod)
        db.session.commit()
        r = tasks.add_new_node.delay(m.hostname, kube.id)
        # r.wait()                              # maybe result?
        tasks.create_containers_nodelay(config)
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
    logs_pod_name = get_kuberdock_logs_pod_name(m.hostname)
    logs_pod = db.session.query(Pod).filter_by(name=logs_pod_name).first()
    if logs_pod:
        logs_pod.delete()
        db.session.commit()
    tasks.delete_pod_nodelay(logs_pod_name)
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


def poll():
    devices = dict.fromkeys(run('rbd ls').split(), None)
    mapped_list = [i.strip().split() for i in run('rbd showmapped').splitlines()]
    # Maybe we'll want mounted later
    #mounted_list = run('mount | grep /dev/rbd')
    mapped = [dict(zip(mapped_list[0], i)) for i in mapped_list[1:]]
    for i in mapped:
        devices[i['image']] = dict(filter(
            (lambda x: x[0] not in ['id', 'image', 'snap']),
            i.items()))
    return devices


@nodes.route('/lookup', methods=['GET'])
@login_required_or_basic
@check_permission('get', 'pods')
def pd_lookup():
    env.user = 'root'
    env.skip_bad_hosts = True
    env.key_file = '/usr/home/bliss/.ssh/id_pub'
    nodes = dict([(k, v)
        for k, v in db.session.query(Node).values(Node.ip, Node.hostname)])
    with settings(warn_only=True):
        data = execute(poll, hosts=nodes.keys())
    sets = [set(filter((lambda x: x[1] is None), i.items())) for i in data.values()]
    intersection = map(operator.itemgetter(0), sets[0].intersection(*sets[1:]))
    return jsonify({'status': 'OK', 'data': intersection})
