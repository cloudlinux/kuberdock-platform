from flask import Blueprint, request, jsonify
from fabric.api import run, settings, env, hide
from fabric.tasks import execute
from functools import wraps
from datetime import datetime
import math
import socket
import os
from .. import tasks
from ..models import Node, User, Pod
from ..nodes.models import NodeMissedAction
from ..core import db
from ..rbac import check_permission
from ..utils import login_required_or_basic_or_token, KubeUtils, from_binunit, send_event
from ..utils import maintenance_protected
from ..validation import (
    check_int_id, check_node_data, check_hostname, check_internal_pod_data)
from ..billing import Kube, kubes_to_limits
from ..settings import (NODE_INSTALL_LOG_FILE, MASTER_IP, AWS,
                        CEPH, KUBERDOCK_INTERNAL_USER, PORTS_TO_RESTRICT,
                        SSH_KEY_FILENAME, ELASTICSEARCH_REST_PORT,
                        KUBERDOCK_SETTINGS_FILE, ERROR_TOKEN)
from ..kapi import pd_utils
from ..kapi.podcollection import PodCollection
from ..tasks import add_node_to_k8s
from . import APIError


nodes = Blueprint('nodes', __name__, url_prefix='/nodes')


KUBERDOCK_LOGS_MEMORY_LIMIT = 256 * 1024 * 1024


def save_failed(token):
    """
    Decorator getting strings starting with token and saving'em to DB
    """
    def outer(func):
        @wraps(func)
        def inner(*args, **kw):
            data = func(*args, **kw)
            failed = [n for n in data.items()
                if isinstance(n[1], basestring) and n[1].startswith(token)]
            if not failed:
                return data
            time_stamp = datetime.now()
            try:
                for i in failed:
                    db.session.add(NodeMissedAction(
                        host=i[0],
                        command=i[1].replace(token, '', 1),
                        time_stamp=time_stamp))
                db.session.commit()
            except Exception:
                pass
            return data
        return inner
    return outer


def get_kuberdock_logs_pod_name(node):
    return 'kuberdock-logs-{0}'.format(node)


def get_dns_pod_config(domain='kuberdock', ip='10.254.0.10'):
    return {
        "name": "kuberdock-dns",
        "clusterIP": ip,
        "replicas": 1,
        "kube_type": Kube.get_internal_service_kube_type(),
        "node": None,
        "restartPolicy": "Always",
        "volumes": [],
        "containers": [
            {
                "command": [
                    "/usr/local/bin/etcd",
                    "-data-dir",
                    "/var/etcd/data",
                    "-listen-client-urls",
                    "http://127.0.0.1:2379,http://127.0.0.1:4001",
                    "-advertise-client-urls",
                    "http://127.0.0.1:2379,http://127.0.0.1:4001",
                    "-initial-cluster-token",
                    "skydns-etcd"
                ],
                "kubes": 1,
                "image": "gcr.io/google_containers/etcd:2.0.9",
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
                "image": "gcr.io/google_containers/kube2sky:1.11",
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
                    "-machines=http://127.0.0.1:4001",
                    "-addr=0.0.0.0:53",
                    "-domain={0}.".format(domain)
                ],
                "kubes": 1,
                "image": "gcr.io/google_containers/skydns:2015-03-11-001",
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


def get_kuberdock_logs_config(node, name, kube_type,
                              collector_kubes, storage_kubes, master_ip,
                              internal_ku_token):

    # Give 2/3 of elastic kubes limits to elastic heap. It's recommended do not
    # give all memory to the heap, and leave some to Lucene.
    es_memory_limit = kubes_to_limits(
        storage_kubes, kube_type
    )['resources']['limits']['memory']
    es_heap_limit = (es_memory_limit * 2) / 3
    return {
        "name": name,
        "clusterIP": None,
        "replicas": 1,
        "kube_type": kube_type,
        "node": node,
        "restartPolicy": "Always",
        "volumes": [
            {
                "name": "docker-containers",
                # path is allowed only for kuberdock-internal
                "localStorage": {"path": "/var/lib/docker/containers"}
            },
            {
                "name": "es-persistent-storage",
                # path is allowed only for kuberdock-internal
                "localStorage": {"path": "/var/lib/elasticsearch"},
            }
        ],
        "containers": [
            {
                "command": ["./run.sh"],
                "kubes": collector_kubes,
                "image": "kuberdock/fluentd:1.3",
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
                "kubes": storage_kubes,
                "image": "kuberdock/elasticsearch:1.4",
                "name": "elasticsearch",
                "env": [
                    {
                        "name": "MASTER",
                        "value": master_ip
                    },
                    {
                        "name": "TOKEN",
                        "value": internal_ku_token
                    },
                    {
                        "name": "NODENAME",
                        "value": node
                    },
                    {
                        "name": "ES_HEAP_SIZE",
                        "value": "{}m".format(es_heap_limit / (1024 * 1024))
                    }
                ],
                "ports": [
                    {
                        "isPublic": False,
                        "protocol": "TCP",
                        "containerPort": ELASTICSEARCH_REST_PORT,
                        "hostPort": ELASTICSEARCH_REST_PORT
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
            default_kube = Kube.get_default_kube()
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
@login_required_or_basic_or_token
def get_list():
    return jsonify({'status': 'OK', 'data': get_nodes_collection()})


@nodes.route('/<node_id>', methods=['GET'])
@login_required_or_basic_or_token
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
    cursor = db.session.query(Node)
    m = cursor.filter_by(hostname=data['hostname']).first()
    if m is not None:
        raise APIError('Conflict, Node with hostname "{0}" already exists'
                       .format(m.hostname), status_code=409)
    if not MASTER_IP:
        raise APIError('There is no MASTER_IP specified in {0}.'
                       'Check that file has not been renamed by package '
                       'manager to .rpmsave or similar'
                       .format(KUBERDOCK_SETTINGS_FILE))
    ip = socket.gethostbyname(data['hostname'])
    if ip == MASTER_IP:
        raise APIError('Looks like you are trying to add MASTER as NODE, '
                       'this kind of setups is not supported at this '
                       'moment')
    kube = Kube.query.get(data.get('kube_type', Kube.get_default_kube_type()))
    m = Node(ip=ip, hostname=data['hostname'], kube=kube, state='pending')
    logs_kubes = 1
    logcollector_kubes = logs_kubes
    logstorage_kubes = logs_kubes
    node_resources = kubes_to_limits(
        logs_kubes, Kube.get_internal_service_kube_type()
    )['resources']
    logs_memory_limit = node_resources['limits']['memory']
    if logs_memory_limit < KUBERDOCK_LOGS_MEMORY_LIMIT:
        logs_kubes = int(math.ceil(
            float(KUBERDOCK_LOGS_MEMORY_LIMIT) / logs_memory_limit
        ))

    if logs_kubes > 1:
        # allocate total log cubes to log collector and to log
        # storage/search containers as 1 : 3
        total_kubes = logs_kubes * 2
        logcollector_kubes = int(math.ceil(float(total_kubes) / 4))
        logstorage_kubes = total_kubes - logcollector_kubes
    ku = User.query.filter_by(username=KUBERDOCK_INTERNAL_USER).first()
    logs_podname = get_kuberdock_logs_pod_name(data['hostname'])
    internal_ku_token = ku.get_token()
    logs_config = get_kuberdock_logs_config(
        data['hostname'], logs_podname,
        Kube.get_internal_service_kube_type(),
        logcollector_kubes,
        logstorage_kubes,
        MASTER_IP,
        internal_ku_token
    )
    check_internal_pod_data(logs_config, ku)
    logs_pod = PodCollection(ku).add(logs_config, skip_check=True)
    PodCollection(ku).update(logs_pod['id'], {'command': 'start'})

    dns_pod = db.session.query(Pod).filter_by(name='kuberdock-dns',
                                              owner=ku).first()
    if not dns_pod:
        dns_config = get_dns_pod_config()
        check_internal_pod_data(dns_config, ku)
        dns_pod = PodCollection(ku).add(dns_config, skip_check=True)
        PodCollection(ku).update(dns_pod['id'], {'command': 'start'})

    try:
        # clear old log before it pulled by SSE event
        os.remove(NODE_INSTALL_LOG_FILE.format(m.hostname))
    except OSError:
        pass

    nodes_data = cursor.values(Node.ip, Node.hostname)
    nodes_ = dict(i for i in nodes_data if i[0] != ip).keys()
    if do_deploy:
        tasks.add_new_node.delay(m.hostname, kube.id, m, with_testing,
                                 nodes_)
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

    for port in PORTS_TO_RESTRICT:
        handle_nodes(process_rule, nodes=nodes_, action='insert',
                     port=port, target='ACCEPT', source=ip)
    data.update({'id': m.id})
    send_event('pull_nodes_state', 'ping')
    return jsonify({'status': 'OK', 'data': data})


@nodes.route('/', methods=['POST'])
@login_required_or_basic_or_token
@check_permission('create', 'nodes')
@maintenance_protected
def create_item():
    data = request.json
    check_node_data(data)
    return add_node(data)


@nodes.route('/<node_id>', methods=['PUT'])
@login_required_or_basic_or_token
@check_permission('edit', 'nodes')
@maintenance_protected
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
@login_required_or_basic_or_token
@check_permission('delete', 'nodes')
@maintenance_protected
def delete_item(node_id):
    check_int_id(node_id)
    cursor = db.session.query(Node)
    m = cursor.get(node_id)
    ku = User.query.filter_by(username=KUBERDOCK_INTERNAL_USER).first()
    if m:

        logs_pod_name = get_kuberdock_logs_pod_name(m.hostname)
        logs_pod = db.session.query(Pod).filter_by(name=logs_pod_name,
                                                   owner=ku).first()
        if logs_pod:
            PodCollection(ku).delete(logs_pod.id, force=True)

        nodes_data = cursor.values(Node.ip, Node.hostname)
        nodes_ = dict(i for i in nodes_data if i[0] != m.ip).keys()
        db.session.delete(m)
        db.session.commit()
        for port in PORTS_TO_RESTRICT:
            handle_nodes(process_rule, nodes=nodes_, action='delete',
                port=port, target='ACCEPT', source=m.ip, append_reject=False)
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


@nodes.route('/checkhost/', methods=['GET'])
@nodes.route('/checkhost/<hostname>', methods=['GET'])
def check_host(hostname=''):
    check_hostname(hostname)
    return jsonify({'status': 'OK'})


def process_rule(**kw):
    append_reject = kw.pop('append_reject', True)
    action = kw.pop('action', 'insert')
    source = kw.pop('source', None)
    kw['source'] = ' -s {0}'.format(source) if source else ''
    kw['action'] = {'insert': 'I', 'append': 'A', 'delete': 'D'}[action]
    kw['conj'] = {'insert': '||', 'append': '||', 'delete': '&&'}[action]

    cmd = ('iptables -C INPUT -p tcp --dport {port}'
           '{source} -j {target} > /dev/null 2>&1 '
           '{conj} iptables -{action} INPUT -p tcp --dport {port}'
           '{source} -j {target}')

    try:
        run(cmd.format(**kw))
        if append_reject:
            run(cmd.format(
                action='A', port=kw['port'], source='', target='REJECT', conj='||'))
        run('/sbin/service iptables save')
    except Exception:
        message = ERROR_TOKEN + cmd.format(**kw) + ';'
        if append_reject:
            message += (cmd.format(
                action='A', port=kw['port'], source='', target='REJECT', conj='||') + ';')
        message += '/sbin/service iptables save'
        return message


@save_failed(token=ERROR_TOKEN)
def handle_nodes(func, **kw):
    env.user = 'root'
    env.skip_bad_hosts = True
    env.key_filename = SSH_KEY_FILENAME
    nodes_ = kw.pop('nodes', [])
    if not nodes_:
        return {}
    with settings(hide('running', 'warnings', 'stdout', 'stderr'), warn_only=True):
        return execute(func, hosts=nodes_, **kw)


@nodes.route('/redeploy/<node_id>', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('redeploy', 'nodes')
@maintenance_protected
def redeploy_item(node_id):
    check_int_id(node_id)
    m = db.session.query(Node).get(node_id)
    tasks.add_new_node.delay(m.hostname, m.kube.id, m, redeploy=True)
    return jsonify({'status': 'OK'})
