import socket
import requests
import json
import uuid

from flask import current_app

from ..nodes.models import Node, NodeFlag, LocalStorageDevices
from ..system_settings.models import SystemSettings
from ..utils import from_binunit, from_siunit, get_api_url
from ..billing.models import Kube
from ..exceptions import APIError
from ..core import db, ssh_connect
from ..settings import (
    NODE_INSTALL_LOG_FILE, AWS, CEPH, PD_NAMESPACE, PD_NS_SEPARATOR,
    NODE_SCRIPT_DIR, NODE_LVM_MANAGE_SCRIPT)


def get_nodes_collection():
    """Returns information for all known nodes.

    Side effect: If some node exists in kubernetes, but is missed in DB, then
    it will be created in DB (see documentation for _fix_missed_nodes function)

    Nodes description will be enriched with some additional fields:
        'status' will be retrieved from kubernetes
        'reason' is extended description for status, it is also based on info
            from kubernetes
        'install_log' will be readed from node installation log
        'resources' info about node resources, will be retrieved from k8s
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
            resources['cpu'] = from_siunit(resources['cpu'])
        except (KeyError, ValueError):
            pass

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
        host = host.lower()
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
    db.session.query(LocalStorageDevices).filter(
        LocalStorageDevices.node_id == node.id
    ).delete()
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
            resources['cpu'] = from_siunit(resources['cpu'])
        except (KeyError, ValueError):
            pass
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
    cpu_multiplier = float(SystemSettings.get_by_name('cpu_multiplier'))
    memory_multiplier = float(SystemSettings.get_by_name('memory_multiplier'))

    try:
        if 'cpu' in resources:
            resources['cpu'] = str(resources['cpu'] / cpu_multiplier)
        if 'memory' in resources:
            resources['memory'] /= memory_multiplier
    except:
        current_app.logger.exception("Can't divide on multipliers")


def get_external_node_ip(node_ip, ssh_to_node, raise_on_error):
    """Returns IP v4 address of the node which is accessible from external
    network.
    Now only works for AWS, because there are explicit API to get this.
    Also, kubernetes may return ExternalIP in api/v1/nodes response, may be it
    is a better way to retrieve external IP.
    TODO: Also there are must be a way to get proper IP for generic KD
    installations.
    https://cloudlinux.atlassian.net/browse/AC-3704
    :param node_ip: Some node IP address which will be returned back if it is
        not an AWS cluster
    :param ssh_to_node: ssh connection to the node
    :param raise_on_error: exception which must be raised on errors

    """
    if not AWS:
        return node_ip

    aws_external_ipv4_endpoint = \
        'http://169.254.169.254/latest/meta-data/public-ipv4'
    try:
        _, o, e = ssh_to_node.exec_command(
            'curl {}'.format(aws_external_ipv4_endpoint),
            timeout=20)
        exit_status = o.channel.recv_exit_status()
    except Exception:
        # May happens in case of connection lost during operation
        current_app.logger.exception(
            'Failed to get external IP for AWS node: %s', node_ip)
        raise raise_on_error
    if exit_status != 0:
        current_app.logger.error(
            "Can't get AWS external ip for node %s. Exit code: %s. "
            "Error message: %s",
            node_ip, exit_status, e.read())
        raise raise_on_error
    return o.read().strip('\n')


def extend_ls_volume(hostname, devices=None, ebs_volume=None, size=None):
    """Adds volume to local storage of a node
    :param hostname: Host name of the node
    :param devices: List of block devices. That devices must be attached to
        the node, and will be added to local storage.
        Example: ['/dev/sdb', '/dev/sdc']
    :param ebs_volume: Name of existing Amazon EBS volume. This volume must
        not be attached to any instance, it will be used for extending node's
        local storage. (Only for AWS-clusters)
    :param size: size of newly created EBS volume. It will be used if none of
        parameters 'devices', 'ebs_volume' is defined. (Only for AWS-clusters)
        If no size is specified and no 'devices', 'ebs_volume' are specified,
        then will be used default size (settings.AWS_EBS_EXTEND_STEP):
        will be created new EBS volume with default size.
    :return: tuple of success flag and error message
    """
    node = Node.get_by_name(hostname)
    if not node:
        return False, 'Node with hostname "{}" not found'.format(hostname)

    ssh, error_message = ssh_connect(hostname)
    if error_message:
        return (
            False,
            'Failed to connect to node host: {}'.format(error_message))
    try:
        if CEPH:
            return False, 'Operation is not supported on CEPH-enabled cluster'
        if AWS and not devices:
            # On AWS we allow to add volume in three ways:
            #   1) specify existing volume name (must be not attached to any
            #   instance)
            #   2) do not specify volume and devices - will be created one new
            #   EBS volume
            #   3) specify device name of already attached volume (must be
            #   attached to the same instance)
            #
            #   Here is provided (1) & (2) methods.
            #   (3) method will be applied in 'else' branch.
            return setup_lvm_to_aws_node(
                ssh, node.id, EBS_volume_name=ebs_volume, size=size
            )
        else:
            if not devices:
                return False, 'You have to specify at least one device'
            return add_volume_to_node_ls(ssh, node.id, devices)
    finally:
        ssh.close()


def setup_lvm_to_aws_node(ssh, node_id, EBS_volume_name=None, size=None):
    """Attaches EBS volume to AWS instance. If EBS_volume_name is not
    specified, then creates new one with random name.
    Makes LVM volume group with that EBS volume and single LVM logical volume
    on the node.
    """
    from kubedock.settings import (
        AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_EBS_EXTEND_STEP)
    cmd = 'python2 {0}/{1} ebs-attach '\
          '--aws-access-key-id {2} --aws-secret-access-key {3}'.format(
              NODE_SCRIPT_DIR, NODE_LVM_MANAGE_SCRIPT,
              AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    if EBS_volume_name is None:
        # if no volume is specified, then create a new one
        EBS_volume_name = PD_NS_SEPARATOR.join(
            [PD_NAMESPACE, 'kdnode-{}-{}'.format(node_id, uuid.uuid4().hex)]
        )
        if size is None:
            size = AWS_EBS_EXTEND_STEP
        cmd += ' --size {0}'.format(size)
    cmd += ' --name {0}'.format(EBS_volume_name)
    _, o, e = ssh.exec_command(cmd)
    result = o.read()
    try:
        data = json.loads(result)
    except (ValueError, TypeError):
        return False, u'Unknown answer format from remote script: {}\n'\
                      u'==================\nSTDERR:\n{}'.format(
                          result, e.read())
    if data['status'] != 'OK':
        return False, u'Failed to attach EBS volume to instance: {}'.format(
            data.get('data', {}).get('message')
        )
    device = data.get('data', {}).get('device', None)
    if device is None:
        return False, u'Error: empty device name in EBS attached volume: {}'\
            .format(data)
    return add_volume_to_node_ls(
        ssh, node_id, [device], {device: EBS_volume_name}
    )


def add_volume_to_node_ls(ssh, node_id, devices, device_names=None):
    """Runs remote script to add volume to local storage.
    :param ssh: - ssh connection to remote host
    :param node_id: node identifier
    :param devices: list of devices (strings like '/dev/xxx') to extend local
        storage on the node
    :return: tuple of success flag and optional error message (if success flag
        is False)
    """
    _, o, e = ssh.exec_command(
        'python2 {0}/{1} add-volume --devices {2}'.format(
            NODE_SCRIPT_DIR, NODE_LVM_MANAGE_SCRIPT, ' '.join(devices)
        )
    )
    result = o.read()
    device_names = device_names or {}
    try:
        data = json.loads(result)
    except (ValueError, TypeError):
        return False, u'Unknown answer format from remote script: {}\n'\
                      u'=======================\nSTDERR:\n{}'.format(
                          result, e.read())
    pv_info = data.get('data', {}).get('PV', {})
    for device in devices:
        if device not in pv_info:
            continue
        LocalStorageDevices.add_device_if_not_exists(
            node_id, device, pv_info[device]['size'], device_names.get(device)
        )
    db.session.commit()
    return True, None


def remove_ls_volume(hostname, raise_on_error=True):
    """Performs clean actions on node deletion.
    Raises APIError exception if error occured and raise_on_error flag is set
    to True.
    """
    error_message = ''
    if CEPH:
        # CEPH-enabled cluster does not require any cleaning
        return error_message
    msg = 'Failed to clean storage on node: {}'
    ssh, connect_error = ssh_connect(hostname)
    if connect_error:
        error_message = msg.format(connect_error)
        if raise_on_error:
            raise APIError(error_message)
        return error_message
    cmd = 'python2 {0}/{1} remove-ls-vg'.format(
        NODE_SCRIPT_DIR, NODE_LVM_MANAGE_SCRIPT
    )
    if AWS:
        from kubedock.settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
        cmd += ' --detach-ebs '\
               '--aws-access-key-id {0} --aws-secret-access-key {1}'.format(
                   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    _, o, e = ssh.exec_command(cmd)
    if o.channel.recv_exit_status():
        error_message = msg.format(e.read())
        if raise_on_error:
            raise APIError(error_message)
    return error_message


def get_ls_info(hostname, raise_on_error=False):
    """Retrieves information about locastorage status on the node."""
    ssh, connect_error = ssh_connect(hostname)
    msg = 'Failed to get information about node LS: {}'
    if connect_error:
        error_message = msg.format(connect_error)
        if raise_on_error:
            raise APIError(error_message)
        return error_message

    cmd = 'python2 {0}/{1} get-info'.format(
        NODE_SCRIPT_DIR, NODE_LVM_MANAGE_SCRIPT
    )
    _, o, e = ssh.exec_command(cmd)
    if o.channel.recv_exit_status():
        error_message = msg.format(e.read())
        if raise_on_error:
            raise APIError(error_message)
    return json.loads(o.read())
