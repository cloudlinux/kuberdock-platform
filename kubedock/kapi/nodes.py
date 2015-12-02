"""Management functions for nodes.
"""
import os
import math
import socket
from functools import wraps
from datetime import datetime

import requests
from fabric.api import run, settings, env, hide
from fabric.tasks import execute
from flask import current_app

from ..utils import send_event, from_binunit, run_ssh_command, get_api_url
from ..core import db
from ..nodes.models import Node, NodeFlag, NodeFlagNames, NodeMissedAction
from ..pods.models import Pod
from ..users.models import User
from ..billing.models import Kube
from ..billing import kubes_to_limits
from ..api import APIError
from ..settings import (
    MASTER_IP, KUBERDOCK_SETTINGS_FILE, KUBERDOCK_INTERNAL_USER,
    ELASTICSEARCH_REST_PORT, NODE_INSTALL_LOG_FILE, PORTS_TO_RESTRICT,
    SSH_KEY_FILENAME, ERROR_TOKEN)
from ..validation import check_internal_pod_data
from .podcollection import PodCollection
from .. import tasks

KUBERDOCK_LOGS_MEMORY_LIMIT = 256 * 1024 * 1024


def get_kuberdock_logs_pod_name(node):
    return 'kuberdock-logs-{0}'.format(node)


def create_node(ip, hostname, kube_id,
                do_deploy=True, with_testing=False):
    """Creates new node in database, kubernetes. Deploys all needed packages
    and settings on the new node, if do_deploy is specified.
    :param ip: optional IP address for the node. If it's not specified, then
        ip address will be retrieved by given hostname
    :param hostname: name of the node host
    :param kube_id: kube type identifier for the new node
    :param do_deploy: flag switches on deployment process on the node host
    :param with_testing: enables/disables testing repository for deployment
    :return: database entity for created node
    """
    if Node.get_by_name(hostname) is not None:
        raise APIError('Conflict, Node with hostname "{0}" already exists'
                       .format(hostname), status_code=409)
    if not MASTER_IP:
        raise APIError('There is no MASTER_IP specified in {0}.'
                       'Check that file has not been renamed by package '
                       'manager to .rpmsave or similar'
                       .format(KUBERDOCK_SETTINGS_FILE))
    if ip is None:
        ip = socket.gethostbyname(hostname)
    if ip == MASTER_IP:
        raise APIError('Looks like you are trying to add MASTER as NODE, '
                       'this kind of setups is not supported at this '
                       'moment')
    _check_node_hostname(ip, hostname)
    node = Node(ip=ip, hostname=hostname, kube_id=kube_id, state='pending')
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
    ku = User.query.filter(User.username == KUBERDOCK_INTERNAL_USER).first()
    logs_podname = get_kuberdock_logs_pod_name(hostname)
    internal_ku_token = ku.get_token()
    logs_config = get_kuberdock_logs_config(
        hostname, logs_podname,
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
        os.remove(NODE_INSTALL_LOG_FILE.format(hostname))
    except OSError:
        pass

    node = add_node_to_db(node)
    _deploy_node(node, do_deploy, with_testing)

    send_event('pull_nodes_state', 'ping')
    return node


def delete_node(node_id):
    """Deletes node."""
    node = Node.query.filter(Node.id == node_id).first()
    if node is None:
        raise APIError('Node not found, id = {}'.format(node_id))
    hostname = node.hostname
    ip = node.ip

    ku = User.query.filter_by(username=KUBERDOCK_INTERNAL_USER).first()

    logs_pod_name = get_kuberdock_logs_pod_name(node.hostname)
    logs_pod = db.session.query(Pod).filter_by(name=logs_pod_name,
                                               owner=ku).first()
    if logs_pod:
        PodCollection(ku).delete(logs_pod.id, force=True)

    nodes = [key for key in Node.get_ip_to_hostame_map() if key != ip]

    try:
        delete_node_from_db(node)
    except Exception as e:
        raise APIError(u'Failed to delete node from DB: {}'.format(e))

    for port in PORTS_TO_RESTRICT:
        handle_nodes(process_rule, nodes=nodes, action='delete',
            port=port, target='ACCEPT', source=ip, append_reject=False)
    res = tasks.remove_node_by_host(hostname)
    if res['status'] == 'Failure':
        raise APIError(
            'Failure. {0} Code: {1}'.format(res['message'], res['code']),
            status_code=200
        )
    try:
        os.remove(NODE_INSTALL_LOG_FILE.format(hostname))
    except OSError:
        pass


def get_nodes_collection():
    """Returns information for all known nodes.

    Side effect: If some node exists in kubernetes, but is missed in DB, then
    it will be created in DB (see documentation for _fix_missed_nodes function).

    Nodes description will be enriched with some additional fields:
        'status' will be retrieved from kubernetes
        'reason' is extended description for status, it is also based on info
            from kubernetes
        'install_log' will be readed from node installation log
        'resources' info about node resources, will be retrieved from kubernetes
    :return: list of dicts
    """
    nodes = Node.get_all()
    kub_hosts = {x['metadata']['name']: x for x in tasks.get_all_nodes()}
    nodes = _fix_missed_nodes(nodes, kub_hosts)
    nodes_list = []
    for node in nodes:
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
                    '2) no connection between node and master '
                    '(firewall, node reboot, etc.)\n'
                )

        if node_status == 'running':
            install_log = ''
        else:
            try:
                install_log = open(
                    NODE_INSTALL_LOG_FILE.format(node.hostname)
                ).read()
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
            'kube_type': node.kube_id,
            'status': node_status,
            'reason': node_reason,
            'install_log': install_log,
            'resources': resources
        })
    return nodes_list


def get_one_node(node_id):
    """Selects information about a node. Information will be extended like in
    get_nodes_collection function, except 'install_log' and 'reason' fields.
    :return: dict
    """
    m = Node.get_by_id(node_id)
    if not m:
        raise APIError("Error. Node {0} doesn't exists".format(node_id),
                       status_code=404)

    res = _get_k8s_node_by_host(m.hostname)
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
    return data


def edit_node_hostname(node_id, ip, hostname):
    """Replaces host name for the node."""
    m = Node.get_by_id(node_id)
    if m is None:
        raise APIError("Error. Node {0} doesn't exists".format(node_id),
                       status_code=404)
    if ip != m.ip:
        raise APIError("Error. Node ip can't be reassigned, "
                        "you need delete it and create new.")
    new_ip = socket.gethostbyname(hostname)
    if new_ip != m.ip:
        raise APIError("Error. Node ip can't be reassigned, "
                        "you need delete it and create new.")
    m.hostname = hostname
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise APIError(u'Failed to replace node hostname: {}'.format(e))
    return m


def redeploy_node(node_id):
    """Initiates node redeployment procedure."""
    node = Node.get_by_id(node_id)
    if not node:
        raise APIError('Node not found', 404)
    tasks.add_new_node.delay(node.id, redeploy=True)


def _get_k8s_node_by_host(host):
    try:
        r = requests.get(get_api_url('nodes', host, namespace=False))
        res = r.json()
        if not isinstance(res, dict) or 'status' not in res:
            raise Exception(u'Invalid response: {}'.format(res))
    except:
        current_app.logger.exception('Failed to get node "%s" from kubernetes',
                                     host)
        return {'status': 'Failure'}
    return res


def _fix_missed_nodes(nodes, kuberenetes_nodes_hosts):
    """Add nodes to database which exist in kubernetes, but missed for some
    unknown reasons in our DB. One of possible reasons:
        - kubelet add a node to kubernetes after deleting.
    We want to show such nodes in our interface, so the admin can see it.
    It is a workaround, and it seems there is more gracefull way to solve
    the problem. Here we actually hide the fact, that the node was created in
    some unusual way.

    """
    db_hosts = {item.hostname for item in nodes}
    default_kube_id = Kube.get_default_kube_type()
    res = list(nodes)

    for host in kuberenetes_nodes_hosts:
        if host not in db_hosts:
            try:
                resolved_ip = socket.gethostbyname(host)
            except socket.error:
                raise APIError(
                    "Hostname {0} can't be resolved to ip during auto-scan."
                    "Check /etc/hosts file for correct Node records"
                    .format(host))
            m = Node(ip=resolved_ip, hostname=host, kube_id=default_kube_id,
                     state='autoadded')
            add_node_to_db(m)
            res.append(m)
    return res


def _check_node_hostname(ip, hostname):
    status, message = run_ssh_command(ip, "uname -n")
    if status:
        raise APIError(
            "Error while trying to get node name: {}".format(message))
    uname_hostname = message.strip()
    if uname_hostname != hostname:
        raise APIError('Wrong node name. {} resolves itself by name {}'.format(
            hostname, uname_hostname))


def _node_is_active(x):
    try:
        cond = _get_node_condition(x)
        return cond['type'] == 'Ready' and cond['status'] == 'True'
    except (TypeError, KeyError):
        return False


def _get_node_condition(x):
    try:
        return x['status']['conditions'][0]
    except (TypeError, KeyError, IndexError):
        return {}


def _deploy_node(dbnode, do_deploy, with_testing):
    nodes = [key for key in Node.get_ip_to_hostame_map() if key != dbnode.ip]
    if do_deploy:
        tasks.add_new_node.delay(dbnode.id, with_testing, nodes)
    else:
        is_ceph_installed = tasks.is_ceph_installed_on_node(dbnode.hostname)
        if is_ceph_installed:
            NodeFlag.save_flag(dbnode.id, NodeFlagNames.CEPH_INSTALLED, 'true')
        err = tasks.add_node_to_k8s(
            dbnode.hostname, dbnode.kube_id, is_ceph_installed)
        if err:
            raise APIError('Error during adding node to k8s. {0}'
                           .format(err))
        else:
            # TODO write all possible states to class
            dbnode.state = 'completed'
            db.session.commit()

    for port in PORTS_TO_RESTRICT:
        handle_nodes(process_rule, nodes=nodes, action='insert',
                     port=port, target='ACCEPT', source=dbnode.ip)


def add_node_to_db(node):
    db.session.add(node)
    try:
        db.session.commit()
    except:
        db.session.rollback()
        raise
    return node


def delete_node_from_db(node):
    db.session.query(NodeFlag).filter(NodeFlag.node_id == node.id).delete()
    db.session.delete(node)
    try:
        db.session.commit()
    except:
        db.session.rollback()
        raise


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
                "image": "kuberdock/fluentd:1.4",
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
                        "name": "es-persistent-storage",
                        "mountPath": "/elasticsearch/data"
                    }
                ],
                "workingDir": "",
                "terminationMessagePath": None
            }
        ]
    }


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


def save_failed(token):
    """
    Decorator getting strings starting with token and saving'em to DB
    """
    def outer(func):
        @wraps(func)
        def inner(*args, **kw):
            data = func(*args, **kw)
            failed = [
                n for n in data.iteritems()
                if isinstance(n[1], basestring) and n[1].startswith(token)
            ]
            if not failed:
                return data
            time_stamp = datetime.utcnow()
            db.session.add_all(
                NodeMissedAction(
                    host=i[0],
                    command=i[1].replace(token, '', 1),
                    time_stamp=time_stamp
                )
                for i in failed
            )
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            return data
        return inner
    return outer


@save_failed(token=ERROR_TOKEN)
def handle_nodes(func, **kw):
    env.user = 'root'
    env.skip_bad_hosts = True
    env.key_filename = SSH_KEY_FILENAME
    nodes = kw.pop('nodes', [])
    if not nodes:
        return {}
    with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                  warn_only=True):
        return execute(func, hosts=nodes, **kw)


def process_rule(**kw):
    append_reject = kw.pop('append_reject', True)
    action = kw.pop('action', 'insert')
    source = kw.pop('source', None)
    kw['source'] = ' -s {0}'.format(source) if source else ''
    kw['action'] = {'insert': 'I', 'append': 'A', 'delete': 'D'}[action]
    kw['conj'] = {'insert': '||', 'append': '||', 'delete': '&&'}[action]

    getnodeip = ('FIRST_IFACE=$(ip -o link show |'
                 'awk -F: \'$3 ~ /LOWER_UP/ {gsub(/ /, "", $2);'
                 'if ($2 != "lo"){print $2;exit}}\');'
                 'FIRST_IP=$(ip -o -4 address show $FIRST_IFACE|'
                 'awk \'/inet/ {sub(/\/.*$/, "", $4);'
                 'print $4;exit;}\'); export $FIRST_IP;'
                 'echo $FIRST_IP > /tmp/qqqq;')

    cmd = ('iptables -C INPUT -p tcp --dport {port}'
           '{source} -d $FIRST_IP -j {target} > /dev/null 2>&1 '
           '{conj} iptables -{action} INPUT -p tcp --dport {port}'
           '{source} -d $FIRST_IP -j {target}')

    try:
        run(getnodeip + cmd.format(**kw))
        if append_reject:
            run(getnodeip + cmd.format(
                action='A', port=kw['port'], source='',
                target='REJECT', conj='||'
            ))
        run('/sbin/service iptables save')
    except Exception:
        message = ERROR_TOKEN + getnodeip + cmd.format(**kw) + ';'
        if append_reject:
            message += (getnodeip + cmd.format(
                action='A', port=kw['port'], source='',
                target='REJECT', conj='||') + ';'
            )
        message += '/sbin/service iptables save'
        return message
