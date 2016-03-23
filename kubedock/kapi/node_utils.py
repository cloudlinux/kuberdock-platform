import socket
import requests

from flask import current_app

from ..nodes.models import Node, NodeFlag
from ..utils import from_binunit, get_api_url
from ..billing.models import Kube
from ..api import APIError
from ..core import db
from ..settings import NODE_INSTALL_LOG_FILE

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
    kub_hosts = {x['metadata']['name']: x for x in get_all_nodes()}
    nodes = _fix_missed_nodes(nodes, kub_hosts)
    nodes_list = []
    for node in nodes:
        node_status, node_reason = get_status(
            node, kub_hosts.get(node.hostname)
        )
        install_log = get_install_log(node_status, node.hostname)

        try:
            resources = kub_hosts[node.hostname]['status']['capacity']
        except KeyError:
            resources = {}

        try:
            resources['memory'] = from_binunit(resources['memory'])
        except (KeyError, ValueError):
            pass

        divide_on_multipliers(resources)

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


def get_status(node, k8s_node=None):
    """Get node status and reason.

    :param node: node model from database
    :param k8s_node: node from k8s
    :return: status, reason
    """
    if k8s_node is not None:
        if _node_is_active(k8s_node):
            if node.state == 'deletion':
                node_status = 'deletion'
                node_reason = 'Node marked as being deleting'
            else:
                node_status = 'running'
                node_reason = ''
        else:
            node_status = 'troubles'
            condition = _get_node_condition(k8s_node)
            if condition:
                if condition['status'] == 'Unknown':
                    node_reason = (
                        'Node state is Unknown\n'
                        'K8s message: {0}\n'
                        'Possible reasons:\n'
                        '1) node is down or rebooting more than 1 minute\n'
                        '2) kubelet.service on node is down\n'
                        '======================================'.format(
                            condition.get('message', 'empty')
                        )
                    )
                else:
                    node_reason = (
                        'Node state is {0}\n'
                        'Reason: "{1}"\n'
                        'Last transition time: {2}\n'
                        'Message: {3}\n'
                        '======================================'.format(
                            condition['status'],
                            condition['reason'],
                            condition['lastTransitionTime'],
                            condition.get('message', 'empty')
                        )
                    )
            else:
                # We can use "pending" here because if node not posts status
                # in 1m after adding to cluster k8s add "Unknown" condition
                # to it with reason "NodeStatusNeverUpdated" that we display
                # correctly as "troubles" with some possible reasons
                node_status = 'pending'
                node_reason = (
                    'Node is a member of KuberDock cluster but '
                    'does not provide information about its condition\n'
                    'Possible reasons:\n'
                    '1) node is in installation progress on final step\n'
                    '======================================'
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


def add_node_to_db(node):
    db.session.add(node)
    try:
        db.session.commit()
    except:
        db.session.rollback()
        raise
    return node


def delete_node_from_db(node):
    kube = node.kube  # get kube type before deletion to send event
    db.session.query(NodeFlag).filter(NodeFlag.node_id == node.id).delete()
    db.session.delete(node)
    try:
        db.session.commit()
    except:
        db.session.rollback()
        raise
    kube.send_event('change')


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
            return [
                i for i in conditions
                if i['status'] in ('True', 'Unknown')
            ][0]
        return conditions[0]
    except (TypeError, KeyError, IndexError):
        return {}


def get_install_log(node_status, hostname):
    if node_status == 'running':
        return ''
    else:
        try:
            with open(NODE_INSTALL_LOG_FILE.format(hostname), 'r') as f:
                return f.read()
        except IOError:
            return 'No install log available for this node.\n'


def get_one_node(node_id):
    """Selects information about a node. See `get_nodes_collection` for more
    info.
    :return: dict
    """
    node = Node.get_by_id(node_id)
    if not node:
        raise APIError("Error. Node {0} doesn't exists".format(node_id),
                       status_code=404)

    k8s_node = _get_k8s_node_by_host(node.hostname)
    if k8s_node['status'] == 'Failure':
        k8s_node = None

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

    divide_on_multipliers(resources)

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


def get_all_nodes():
    r = requests.get(get_api_url('nodes', namespace=False))
    return r.json().get('items') or []


def divide_on_multipliers(resources):
    try:
        if 'cpu' in resources:
            resources['cpu'] = str(int(resources['cpu'])/8)
        if 'memory' in resources:
            resources['memory'] = resources['memory']/4
    except:
        current_app.logger.exception("Can't divide on multipliers")
