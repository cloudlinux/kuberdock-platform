"""Management functions for nodes.
"""
import os
import math
import socket

import requests
from flask import current_app

from ..utils import send_event, from_binunit, run_ssh_command, get_api_url
from ..core import db
from ..nodes.models import Node, NodeFlag, NodeFlagNames
from ..pods.models import Pod
from ..users.models import User
from ..billing.models import Kube
from ..billing import kubes_to_limits
from ..api import APIError
from ..settings import (
    MASTER_IP, KUBERDOCK_SETTINGS_FILE, KUBERDOCK_INTERNAL_USER,
    ELASTICSEARCH_REST_PORT, NODE_INSTALL_LOG_FILE)
from ..validation import check_internal_pod_data
from .podcollection import PodCollection
from .licensing import is_valid as license_valid
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

    try:
        # clear old log before it pulled by SSE event
        os.remove(NODE_INSTALL_LOG_FILE.format(hostname))
    except OSError:
        pass

    node = add_node_to_db(node)
    _deploy_node(node, do_deploy, with_testing)

    ku = User.query.filter(User.username == KUBERDOCK_INTERNAL_USER).first()
    logs_podname = get_kuberdock_logs_pod_name(hostname)
    logs_pod = db.session.query(Pod).filter_by(name=logs_podname,
                                               owner=ku).first()
    if not logs_pod:
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
    return node


def mark_node_as_being_deleted(node_id):
    node = Node.query.filter(Node.id == node_id).first()
    if node is None:
        raise APIError('Node not found, id = {}'.format(node_id))
    node.state = 'deletion'
    db.session.commit()
    return node


def delete_node(node_id=None, node=None):
    """Deletes node."""

    # As long as the func is allowed to be called after mark_node_as_being_deleted
    # func there's no need to double DB request, let's get the node object directly.
    if node is None:
        if node_id is None:
            raise APIError('Insufficient data for operation')
        node = Node.query.filter(Node.id == node_id).first()
        if node is None:
            raise APIError('Node not found, id = {}'.format(node_id))

    hostname = node.hostname
    if node_id is None:
        node_id = node.id

    ku = User.query.filter_by(username=KUBERDOCK_INTERNAL_USER).first()

    logs_pod_name = get_kuberdock_logs_pod_name(node.hostname)
    logs_pod = db.session.query(Pod).filter_by(name=logs_pod_name,
                                               owner=ku).first()
    if logs_pod:
        PodCollection(ku).delete(logs_pod.id, force=True)

    try:
        delete_node_from_db(node)
    except Exception as e:
        raise APIError(u'Failed to delete node from DB: {}'.format(e))

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
    send_event('node:deleted', {
        'id': node_id,
        'message': 'Node successfully deleted'})


def get_install_log(node_status, hostname):
    if node_status == 'running':
        return ''
    else:
        try:
            with open(NODE_INSTALL_LOG_FILE.format(hostname), 'r') as f:
                return f.read()
        except IOError:
            return 'No install log available for this node.\n'


def get_status(node, res=None):
    """Get node status and reason.

    :param node: node model from database
    :param res: node from k8s
    :return: status, reason
    """
    if res is not None:
        if _node_is_active(res):
            if node.state == 'deletion':
                node_status = 'deletion'
                node_reason = 'Node marked as being deleting'
            else:
                node_status = 'running'
                node_reason = ''
        else:
            node_status = 'troubles'
            condition = _get_node_condition(res)
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
    return node_status, node_reason


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
        node_status, node_reason = get_status(node, kub_hosts.get(node.hostname))
        install_log = get_install_log(node_status, node.hostname)

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
    """Selects information about a node. See `get_nodes_collection` for more info.
    :return: dict
    """
    node = Node.get_by_id(node_id)
    if not node:
        raise APIError("Error. Node {0} doesn't exists".format(node_id),
                       status_code=404)

    k8s_node = _get_k8s_node_by_host(node.hostname)
    if k8s_node['status'] == 'Failure':
        k8s_node = None
        if node.state != 'pending':
            raise APIError(
                "Error. Node exists in db but don't exists in kubernetes",
                status_code=404)

    node_status, node_reason = get_status(node, k8s_node)
    install_log = get_install_log(node_status, node.hostname)

    if k8s_node is None:
        resources = {}
    else:
        resources = k8s_node['status'].get('capacity', {})
        try:
            resources['memory'] = from_binunit(resources['memory'])
        except (KeyError, ValueError):
            pass

    data = {
        'id': node.id,
        'ip': node.ip,
        'hostname': node.hostname,
        'kube_type': node.kube_id,
        'status': node_status,
        'reason': node_reason,
        'install_log': install_log,
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
        if uname_hostname in hostname:
            status, h_message = run_ssh_command(ip, "hostname -f")
            if status:
                raise APIError(
                    "Error while trying to get node h_name: {}".format(h_message))
            uname_hostname = h_message.strip()
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
        conditions = x['status']['conditions']
        if len(conditions) > 1:
            return [i for i in conditions if i['status'] == 'True'][0]
        return conditions[0]
    except (TypeError, KeyError, IndexError):
        return {}


def _deploy_node(dbnode, do_deploy, with_testing):
    if do_deploy:
        tasks.add_new_node.delay(dbnode.id, with_testing)
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
                "image": "kuberdock/fluentd:1.5",
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
                "kubes": storage_kubes,
                "image": "kuberdock/elasticsearch:2.2",
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
        "volumes": [
            {
                "name": "kubernetes-config",
                # path is allowed only for kuberdock-internal
                "localStorage": {"path": "/etc/kubernetes"}
            },
            {
                "name": "etcd-pki",
                # path is allowed only for kuberdock-internal
                "localStorage": {"path": "/etc/pki/etcd"}
            }
        ],
        "containers": [
            {
                "command": [
                    "/usr/local/bin/etcd",
                    "-data-dir",
                    "/var/etcd/data",
                    "-listen-client-urls",
                    "https://0.0.0.0:2379,http://127.0.0.1:4001",
                    "-advertise-client-urls",
                    "https://0.0.0.0:2379,http://127.0.0.1:4001",
                    "-initial-cluster-token",
                    "skydns-etcd",
                    "--ca-file",
                    "/etc/pki/etcd/ca.crt",
                    "--cert-file",
                    "/etc/pki/etcd/etcd-dns.crt",
                    "--key-file",
                    "/etc/pki/etcd/etcd-dns.key"
                ],
                "kubes": 1,
                "image": "gcr.io/google_containers/etcd:2.0.9",
                "name": "etcd",
                "env": [],
                "ports": [
                    {
                        "isPublic": False,
                        "protocol": "TCP",
                        "containerPort": 2379
                    }
                ],
                "volumeMounts": [
                    {
                        "name": "etcd-pki",
                        "mountPath": "/etc/pki/etcd"
                    }
                ],
                "workingDir": "",
                "terminationMessagePath": None
            },
            {
                "command": [
                    "/kube2sky",
                    "-domain={0}".format(domain),
                    "-kubecfg_file=/etc/kubernetes/configfile",
                    "-kube_master_url=https://10.254.0.1",
                ],
                "kubes": 1,
                "image": "gcr.io/google_containers/kube2sky:1.11",
                "name": "kube2sky",
                "env": [],
                "ports": [],
                "volumeMounts": [
                    {
                        "name": "kubernetes-config",
                        "mountPath": "/etc/kubernetes"
                    }
                ],
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
