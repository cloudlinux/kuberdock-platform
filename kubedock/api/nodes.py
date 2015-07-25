from flask import Blueprint, request, jsonify
from fabric.api import run, settings, env
from fabric.tasks import execute
import boto.ec2
import math
import socket
import operator
import socket
import os
from .. import tasks
from ..models import Node, User, Pod
from ..core import db
from ..rbac import check_permission
from ..utils import login_required_or_basic_or_token, KubeUtils, from_binunit, send_event
from ..validation import check_int_id, check_node_data, check_hostname, check_new_pod_data
from ..billing import Kube, kubes_to_limits
from ..settings import NODE_INSTALL_LOG_FILE, MASTER_IP, PD_SEPARATOR, AWS, CEPH
from ..settings import KUBERDOCK_INTERNAL_USER
from ..kapi.podcollection import PodCollection
from ..tasks import add_node_to_k8s
from . import APIError


nodes = Blueprint('nodes', __name__, url_prefix='/nodes')


KUBERDOCK_LOGS_MEMORY_LIMIT = 256 * 1024 * 1024


def get_kuberdock_logs_pod_name(node):
    return 'kuberdock-logs-{0}'.format(node)


def get_dns_pod_config(domain='kuberdock', ip='10.254.0.10'):
    return {
        "name": "kuberdock-dns",
        "clusterIP": ip,
        "replicas": 1,
        "kube_type": 0,
        "replicationController": True,
        "node": None,
        "save_only": True,
        "restartPolicy": "Always",
        "volumes": [],
        "containers": [
            {
                "command": [
                    "/etcd",
                    "-listen-client-urls=http://0.0.0.0:2379,http://0.0.0.0:4001",
                    "-initial-cluster-token=skydns-etcd",
                    "-advertise-client-urls=http://127.0.0.1:4001"
                ],
                "kubes": 1,
                "image": "quay.io/coreos/etcd:v2.0.3",
                "name": "etcd",
                "env": [],
                "ports": [],
                "volumeMounts": [],
                "workingDir": "",
                "terminationMessagePath": None
            },
            {
                "command": [
                    "/kube2sky",
                    "-domain={0}".format(domain),
                ],
                "kubes": 1,
                "image": "gcr.io/google-containers/kube2sky:1.1",
                "name": "kube2sky",
                "env": [],
                "ports": [],
                "volumeMounts": [],
                "workingDir": "",
                "terminationMessagePath": None
            },
            {
                "command": [
                    "/skydns",
                    "-machines=http://127.0.0.1:4001", "-addr=0.0.0.0:53",
                    "-domain={0}.".format(domain)
                ],
                "kubes": 1,
                "image": "gcr.io/google-containers/skydns:2015-03-11-001",
                "name": "skydns",
                "env": [],
                "ports": [
                    {
                        "isPublic": False,
                        "protocol": "UDP",
                        "containerPort": 53
                    }
                ],
                "volumeMounts": [],
                "workingDir": "",
                "terminationMessagePath": None
            }
        ]
    }


def get_kuberdock_logs_config(node, name, kube_type, kubes, master_ip):
    return {
        "name": name,
        "clusterIP": None,
        "replicas": 1,
        "kube_type": kube_type,
        "replicationController": True,
        "node": node,
        "save_only": True,
        "restartPolicy": "Always",
        "volumes": [
            {
                "name": "docker-containers",
                "hostPath": {
                    "path": "/var/lib/docker/containers"
                }
            },
            {
                "name": "es-persistent-storage",
                "hostPath": {
                    "path": "/var/lib/elasticsearch"
                }
            }
        ],
        "containers": [
            {
                "command": ["./run.sh"],
                "kubes": kubes,
                "image": "kuberdock/fluentd:1.0",
                "name": "fluentd",
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
                        "protocol": "UDP",
                        "containerPort": 5140,
                        "hostPort": 5140
                    }
                ],
                "volumeMounts": [
                    {
                        "readOnly": False,
                        "name": "docker-containers",
                        "mountPath": "/var/lib/docker/containers"
                    }
                ],
                "workingDir": "/root",
                "terminationMessagePath": None
            },
            {
                "command": ["/elasticsearch/run.sh"],
                "kubes": kubes,
                "image": "kuberdock/elasticsearch:1.0",
                "name": "elasticsearch",
                "env": [
                    {
                        "name": "MASTER",
                        "value": master_ip
                    }
                ],
                "ports": [
                    {
                        "isPublic": False,
                        "protocol": "TCP",
                        "containerPort": 9200,
                        "hostPort": 9200
                    },
                    {
                        "isPublic": False,
                        "protocol": "TCP",
                        "containerPort": 9300,
                        "hostPort": 9300
                    }
                ],
                "volumeMounts": [
                    {
                        "readOnly": False,
                        "name": "es-persistent-storage",
                        "mountPath": "/elasticsearch/data"
                    }
                ],
                "workingDir": "",
                "terminationMessagePath": None
            }
        ]
    }


def _get_node_condition(x):
    try:
        return x['status']['conditions'][0]
    except KeyError:
        return {}


def _node_is_active(x):
    try:
        cond = _get_node_condition(x)
        return cond['type'] == 'Ready' and cond['status'] == 'True'
    except KeyError:
        return False


@check_permission('get', 'nodes')
def get_nodes_collection():
    new_flag = False
    oldcur = Node.query.all()
    db_hosts = [node.hostname for node in oldcur]
    kub_hosts = {x['metadata']['name']: x for x in tasks.get_all_nodes()}
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
            m = Node(ip=resolved_ip, hostname=host, kube=default_kube,
                     state='autoadded')
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
                        'Possible reasons:\n'
                        '1) node is in installation progress on final step'
                    )
        else:
            if node.state == 'pending':
                node_status = 'pending'
                node_reason = (
                    'Node is not a member of KuberDock cluster\n'
                    'Possible reasons:\n'
                    'Node is in installation progress\n'
                )
            else:
                node_status = 'troubles'
                node_reason = (
                    'Node is not a member of KuberDock cluster\n'
                    'Possible reasons:\n'
                    '1) error during node installation\n'
                    '2) no connection between node and master(firewall, node reboot, etc.)\n'
                )

        if node_status == 'running':
            install_log = ''
        else:
            try:
                install_log = open(NODE_INSTALL_LOG_FILE.format(node.hostname)).read()
            except IOError:
                install_log = 'No install log available for this node.\n'

        try:
            resources = kub_hosts[node.hostname]['status']['capacity']
        except KeyError:
            resources = {}

        try:
            resources['memory'] = from_binunit(resources['memory'])
        except (KeyError, ValueError):
            pass

        nodes_list.append({
            'id': node.id,
            'ip': node.ip,
            'hostname': node.hostname,
            'kube_type': node.kube.id,
            'status': node_status,
            'reason': node_reason,
            'install_log': install_log,
            'resources': resources
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

        resources = res['status'].get('capacity', {})

        try:
            resources['memory'] = from_binunit(resources['memory'])
        except (KeyError, ValueError):
            pass

        data = {
            'id': m.id,
            'ip': m.ip,
            'hostname': m.hostname,
            'kube_type': m.kube.id,
            'status': 'running' if _node_is_active(res) else 'troubles',
            'resources': resources
        }
        return jsonify({'status': 'OK', 'data': data})
    else:
        raise APIError("Error. Node {0} doesn't exists".format(node_id),
                       status_code=404)


def add_node(data, do_deploy=True, with_testing=False):
    m = db.session.query(Node).filter_by(hostname=data['hostname']).first()
    if not m:
        kube = Kube.query.get(data.get('kube_type', 0))
        m = Node(ip=socket.gethostbyname(data['hostname']),
                 hostname=data['hostname'], kube=kube, state='pending')
        logs_kubes = 1
        node_resources = kubes_to_limits(logs_kubes, kube.id)['resources']
        logs_memory_limit = node_resources['limits']['memory']
        if logs_memory_limit < KUBERDOCK_LOGS_MEMORY_LIMIT:
            logs_kubes = int(math.ceil(
                float(KUBERDOCK_LOGS_MEMORY_LIMIT) / logs_memory_limit
            ))
        ku = User.query.filter_by(username=KUBERDOCK_INTERNAL_USER).first()
        logs_podname = get_kuberdock_logs_pod_name(data['hostname'])
        logs_config = get_kuberdock_logs_config(data['hostname'], logs_podname,
                                                kube.id, logs_kubes, MASTER_IP)
        check_new_pod_data(logs_config)
        logs_pod = PodCollection(ku).add(logs_config)
        PodCollection(ku).update(logs_pod['id'], {'command': 'start'})

        dns_pod = db.session.query(Pod).filter_by(name='kuberdock-dns',
                                                  owner=ku).first()
        if not dns_pod:
            dns_config = get_dns_pod_config()
            check_new_pod_data(dns_config)
            dns_pod = PodCollection(ku).add(dns_config)
            PodCollection(ku).update(dns_pod['id'], {'command': 'start'})

        try:
            # clear old log before it pulled by SSE event
            os.remove(NODE_INSTALL_LOG_FILE.format(m.hostname))
        except OSError:
            pass

        if do_deploy:
            tasks.add_new_node.delay(m.hostname, kube.id, m, with_testing)
        else:
            err = add_node_to_k8s(m.hostname, kube.id)
            if err:
                raise APIError('Error during adding node to k8s. {0}'
                               .format(err))
            else:
                # TODO write all possible states to class
                m.state = 'completed'
                db.session.add(m)
                db.session.commit()
        data.update({'id': m.id})
        send_event('pull_nodes_state', 'ping')
        return jsonify({'status': 'OK', 'data': data})
    else:
        raise APIError(
            'Conflict, Node with hostname "{0}" already exists'
            .format(m.hostname), status_code=409)


@nodes.route('/', methods=['POST'])
@check_permission('create', 'nodes')
def create_item():
    data = request.json
    check_node_data(data)
    return add_node(data)


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
    ku = User.query.filter_by(username=KUBERDOCK_INTERNAL_USER).first()
    logs_pod_name = get_kuberdock_logs_pod_name(m.hostname)
    logs_pod = db.session.query(Pod).filter_by(name=logs_pod_name,
                                               owner=ku).first()
    if logs_pod:
        PodCollection(ku).delete(logs_pod.id, force=True)
    if m:
        db.session.delete(m)
        db.session.commit()
        res = tasks.remove_node_by_host(m.hostname)
        if res['status'] == 'Failure':
            raise APIError('Failure. {0} Code: {1}'
                           .format(res['message'], res['code']),
                           status_code=200)
        try:
            os.remove(NODE_INSTALL_LOG_FILE.format(m.hostname))
        except OSError:
            pass
    return jsonify({'status': 'OK'})


@nodes.route('/checkhost/<hostname>', methods=['GET'])
def check_host(hostname):
    check_hostname(hostname)
    return jsonify({'status': 'OK'})


def poll():
    devices = dict.fromkeys(run('rbd ls').split(), None)
    mapped_list = [i.strip().split() for i in run('rbd showmapped').splitlines()]
    # Maybe we'll want mounted later
    # mounted_list = run('mount | grep /dev/rbd')
    mapped = [dict(zip(mapped_list[0], i)) for i in mapped_list[1:]]
    for i in mapped:
        devices[i['image']] = dict(filter(
            (lambda x: x[0] not in ['id', 'image', 'snap']),
            i.items()))
    return devices


def get_ceph_volumes():
    drives = []
    env.user = 'root'
    env.skip_bad_hosts = True
    nodes = dict([(k, v)
        for k, v in db.session.query(Node).values(Node.ip, Node.hostname)])
    with settings(warn_only=True):
        data = execute(poll, hosts=nodes.keys())
    sets = [set(filter((lambda x: x[1] is None), i.items())) for i in data.values()]
    intersection = map(operator.itemgetter(0), sets[0].intersection(*sets[1:]))
    username = KubeUtils._get_current_user().username
    for item in intersection:
        try:
            drive, user = item.rsplit(PD_SEPARATOR, 1)
        except ValueError:
            continue
        if user == username:
            drives.append(drive)
    return drives


def get_aws_volumes():
    drives = []
    try:
        from ..settings import REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
    except ImportError:
        return drives
    username = KubeUtils._get_current_user().username
    conn = boto.ec2.connect_to_region(
        REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
    for vol in conn.get_all_volumes():
        try:
            item = vol.tags.get('Name', 'Nameless')
            drive, user = item.rsplit(PD_SEPARATOR, 1)
        except ValueError:
            continue
        if user == username and vol.status == 'available':
            drives.append(drive)
    return drives


@nodes.route('/lookup', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'pods')
def pd_lookup():
    if AWS:
        return jsonify({'status': 'OK', 'data': get_aws_volumes()})
    if CEPH:
        return jsonify({'status': 'OK', 'data': get_ceph_volumes()})
    return jsonify({'status': 'OK', 'data': []})


@nodes.route('/redeploy/<node_id>', methods=['GET'])
@check_permission('redeploy', 'nodes')
def redeploy_item(node_id):
    check_int_id(node_id)
    m = db.session.query(Node).get(node_id)
    tasks.add_new_node.delay(m.hostname, m.kube.id, m)
    return jsonify({'status': 'OK'})
