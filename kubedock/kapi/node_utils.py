
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import socket
import requests
import json
import uuid
import re
import os

from flask import current_app

from paramiko.ssh_exception import SSHException

from ..nodes.models import Node, NodeFlag, LocalStorageDevices
from ..system_settings.models import SystemSettings
from ..utils import from_binunit, from_siunit, get_api_url, NODE_STATUSES, Etcd
from ..billing.models import Kube
from ..exceptions import APIError
from ..core import db, ssh_connect
from ..settings import (
    NODE_INSTALL_LOG_FILE, AWS, CEPH, PD_NAMESPACE, PD_NS_SEPARATOR,
    NODE_STORAGE_MANAGE_CMD, ZFS, ETCD_CALICO_HOST_ENDPOINT_KEY_PATH_TEMPLATE,
    ETCD_CALICO_HOST_CONFIG_KEY_PATH_TEMPLATE, ETCD_NETWORK_POLICY_NODES,
    KD_NODE_HOST_ENDPOINT_ROLE, NODE_CEPH_AWARE_KUBERDOCK_LABEL,
    NODE_INSTALL_TASK_ID)
from ..kd_celery import celery
from .network_policies import get_node_host_endpoint_policy
from .node import Node as K8SNode


def get_nodes_collection(kube_type=None):
    """Returns information for all known nodes.

    :param kube_type: If provided, nodes are filtered by this kube type.
    :type kube_type: int

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
    if kube_type is None:
        nodes = Node.get_all()
    else:
        nodes = Node.query.filter_by(kube_id=kube_type)

    kub_hosts = {x['metadata']['name']: x for x in get_all_nodes()}
    # AC-3349 Fix. The side effect described above was fixed in some previous
    # patches and this part is not needed any more.
    # nodes = _fix_missed_nodes(nodes, kub_hosts)
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
            'public_interface': node.public_interface,
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
                     state=NODE_STATUSES.autoadded)
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
            if node.state == NODE_STATUSES.deletion:
                res_node_status = NODE_STATUSES.deletion
                node_status_message = 'Node marked as being deleting'
            else:
                res_node_status = NODE_STATUSES.running
                node_status_message = ''
        else:
            res_node_status = NODE_STATUSES.troubles
            condition = _get_node_condition(k8s_node)
            if condition:
                if condition['status'] == 'Unknown':
                    node_status_message = (
                        'Node state is Unknown\n'
                        'K8s message: {0}\n'
                        'Possible reasons:\n'
                        '1) node is down or rebooting more than 1 minute\n'
                        '2) kubelet.service on node is down\n'
                        '3) Some error has happened in Kuberdock during node '
                        'deploy. See Kuberdock server logs\n'
                        '======================================'.format(
                            condition.get('message', 'empty')
                        )
                    )
                else:
                    node_status_message = (
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
                res_node_status = NODE_STATUSES.pending
                node_status_message = (
                    'Node is a member of KuberDock cluster but '
                    'does not provide information about its condition. '
                    "This status shouldn't last too long.\n"
                    'Possible reasons:\n'
                    '1) node is in installation progress on final step\n'
                    '======================================'
                )
    else:
        if node.state == NODE_STATUSES.pending:
            res_node_status = NODE_STATUSES.pending
            node_status_message = (
                'Node is not a member of KuberDock cluster\n'
                'Possible reasons:\n'
                '1) Node is in installation progress\n'
                '2) Some error has happened in Kuberdock during node deploy. '
                'See Kuberdock server logs\n'
            )
        else:
            res_node_status = NODE_STATUSES.troubles
            node_status_message = (
                'Node is not a member of KuberDock cluster\n'
                'Possible reasons:\n'
                '1) Some error has happened in Kuberdock during node deploy. '
                'See Kuberdock server logs\n'
                '2) No connection between node and master '
                '(firewall, node reboot, etc.)\n'
            )

    return res_node_status, node_status_message


def node_status_running(k8snode):
    k8snode_info = get_one_node(k8snode.id)
    return k8snode_info['status'] == NODE_STATUSES.running


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
    if node_status == NODE_STATUSES.running:
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
        'public_interface': node.public_interface,
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
    except SSHException:
        # May happens in case of connection lost during operation
        current_app.logger.warning(
            'Network error while try to get external IP for AWS node: %s',
            node_ip)
        raise raise_on_error
    except Exception:
        current_app.logger.exception(
            'Unknown error while try to get external IP for AWS node: %s',
            node_ip)
        raise raise_on_error
    if exit_status != 0:
        current_app.logger.error(
            "Can't get AWS external ip for node %s. Exit code: %s. "
            "Error message: %s",
            node_ip, exit_status, e.read())
        raise raise_on_error
    return o.read().strip('\n')


def extend_ls_volume(hostname, devices=None, ebs_volume=None, size=None,
                     ebs_volume_type=None, ebs_volume_iops=None):
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
    :param ebs_volume_type: volume type for EBS volume. It will be used if none
        of parameters 'devices', 'ebs_volume' is defined. (Only for
        AWS-clusters). If it is not specified, then will be used default value
        from AWS_DEFAULT_EBS_VOLUME_TYPE
    :param ebs_volume_iops: integer value for EBS volume iops. It is applicable
        only for ebs_volume_type = 'io1'. If it is not specified, then will be
        used default value from AWS_DEFAULT_EBS_VOLUME_IOPS
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
            return setup_storage_to_aws_node(
                ssh, node.id, EBS_volume_name=ebs_volume, size=size,
                volume_type=ebs_volume_type, volume_iops=ebs_volume_iops
            )
        else:
            if not devices:
                return False, 'You have to specify at least one device'
            return add_volume_to_node_ls(ssh, node.id, devices)
    finally:
        ssh.close()


def setup_storage_to_aws_node(ssh, node_id, EBS_volume_name=None, size=None,
                              volume_type=None, volume_iops=None):
    """Attaches EBS volume to AWS instance. If EBS_volume_name is not
    specified, then creates new one with random name.
    Makes LVM volume group with that EBS volume and single LVM logical volume
    on the node.
    """
    from kubedock.settings import (
        AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_EBS_EXTEND_STEP,
        AWS_DEFAULT_EBS_VOLUME_TYPE, AWS_DEFAULT_EBS_VOLUME_IOPS,
        AWS_IOPS_PROVISION_VOLUME_TYPES)
    cmd = NODE_STORAGE_MANAGE_CMD + ' ebs-attach '\
        '--aws-access-key-id {0} --aws-secret-access-key {1}'.format(
            AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    if EBS_volume_name is None:
        # if no volume is specified, then create a new one
        EBS_volume_name = PD_NS_SEPARATOR.join(
            [PD_NAMESPACE, 'kdnode-{}-{}'.format(node_id, uuid.uuid4().hex)]
        )
        if size is None:
            size = AWS_EBS_EXTEND_STEP
        cmd += ' --size {0}'.format(size)
        if not volume_type:
            volume_type = AWS_DEFAULT_EBS_VOLUME_TYPE
        cmd += ' --volume-type {0}'.format(volume_type)
        if volume_type in AWS_IOPS_PROVISION_VOLUME_TYPES:
            if not volume_iops:
                volume_iops = AWS_DEFAULT_EBS_VOLUME_IOPS
            cmd += ' --iops {0}'.format(volume_iops)

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
        NODE_STORAGE_MANAGE_CMD + ' add-volume --devices {}'.format(
            ' '.join(devices)
        )
    )
    result = o.read()
    device_names = device_names or {}
    try:
        data = json.loads(result)
        if data['status'] != 'OK':
            return (
                False,
                'Failed to add volume: {} '.format(data['data']['message'])
            )
    except (ValueError, TypeError, KeyError):
        return False, u'Unknown answer format from remote script: {}\n'\
                      u'=======================\nSTDERR:\n{}'.format(
                          result, e.read())
    data = data.get('data', {})
    if ZFS:
        pv_info = data.get('zpoolDevs', {})
    else:
        pv_info = data.get('PV', {})
    for device in devices:
        if device not in pv_info:
            continue
        LocalStorageDevices.add_device_if_not_exists(
            node_id, device, pv_info[device]['size'], device_names.get(device)
        )
    db.session.commit()
    return True, None


def remove_ls_storage(hostname, raise_on_error=True):
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
    cmd = NODE_STORAGE_MANAGE_CMD + ' remove-storage'
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


def _exec_on_host(hostname, command, err_message_prefix):
    ssh, connect_error = ssh_connect(hostname)
    if connect_error:
        error_message = u'{}: {}'.format(err_message_prefix, connect_error)
        raise APIError(error_message)

    _, o, e = ssh.exec_command(command)
    if o.channel.recv_exit_status():
        error_message = u'{}: {}'.format(err_message_prefix, e.read())
        raise APIError(error_message)
    return o.read()


def get_ls_info(hostname):
    """Retrieves information about locastorage status on the node."""
    msg = u'Failed to get information about node LS on "{}"'.format(hostname)
    cmd = NODE_STORAGE_MANAGE_CMD + ' get-info'
    result = _exec_on_host(hostname, cmd, msg)
    return json.loads(result)


def get_block_device_list(hostname):
    """Retrieves list of block devices available on the given host.
    :return: a dict. Keys are - block device names, values are dicts with
    block device info:
        NAME - block device name
        SIZE - block device size in bytes
        TYPE - block device type (disk or part)
        MOUNTPOINT - mounpoint of the device if it is already mounted
        DEVICE - path to the device in form of /dev/<device name>
    """
    cmd = 'lsblk -P -b'
    result = _exec_on_host(
        hostname,
        cmd,
        'Failed to get information about block devices on "{}"'.format(
            hostname)
    )
    # We will get a string for each device in form of
    # NAME="sda" MAJ:MIN="8:0" RM="0" SIZE="16106127360" RO="0" TYPE="disk"
    #   -> MOUNTPOINT=""
    # or
    # NAME="sda2" MAJ:MIN="8:2" RM="0" SIZE="15580790784" RO="0" TYPE="part"
    # MOUNTPOINT=""
    # So we have to split the whole output by lines and extract for each line
    # the next keys
    NAME = 'NAME'
    SIZE = 'SIZE'
    TYPE = 'TYPE'
    MOUNTPOINT = 'MOUNTPOINT'
    use_keys = {NAME, SIZE, TYPE, MOUNTPOINT}
    # Additional output key where will be written device path with '/dev'
    # prefix
    DEVICE = 'DEVICE'

    # Also we list only block devices of the following types
    ACCEPTABLE_BLK_TYPES = ['disk', 'part']

    # Try to split the line to 'key="value"' parts.
    # FIXME: we will fail in cases when value contains escaped doublequotes.
    key_value_pattern = re.compile(r'([A-Z]+="[^"]*")\s?')

    devices = {}
    for line in result.splitlines():
        parts = key_value_pattern.findall(line)
        if len(parts) < len(use_keys):
            continue
        device = {}
        for keyvalue in parts:
            try:
                key, value = keyvalue.split('=', 1)
            except ValueError:
                continue
            if key not in use_keys:
                continue
            device[key] = value.strip('"')

        if not use_keys.issubset(device):
            current_app.logger.warning(
                u"Unknown output of lsblk. host = '{}', value = '{}'".format(
                    hostname, line
                )
            )
            continue
        if device[TYPE] not in ACCEPTABLE_BLK_TYPES:
            continue
        try:
            device[SIZE] = int(device[SIZE])
        except (KeyError, TypeError, ValueError):
            device[SIZE] = 0

        device[DEVICE] = u'/dev/{}'.format(device[NAME])
        # It would be very nice to set a flag pointed that device is in use -
        # So we may avoid adding devices in-use to (for example) zpool.
        # But actually it is not trivial, a nice explanation is here:
        # http://unix.stackexchange.com/a/111791
        # device['BUSY'] = bool(device.get(MOUNTPOINT))
        devices[device[NAME]] = device
    return devices


def create_calico_host_endpoint(node_hostname, node_ipv4):
    """Creates host endpoint for the node"""
    # If the node is added as host endpoint, then by default there will be
    # dropped all traffic (incoming and outgoing) to the node.
    # So there must be added an appropriate policy to role 'kdnode' and it
    # must be set during KD cluster deployment.
    node_endpoint = {
        "expected_ipv4_addrs": [node_ipv4],
        "labels": {"role": KD_NODE_HOST_ENDPOINT_ROLE},
        "profile_ids": []
    }
    etcd_path = ETCD_CALICO_HOST_ENDPOINT_KEY_PATH_TEMPLATE.format(
        hostname=node_hostname
    )
    Etcd(etcd_path).put(None, value=node_endpoint)


def drop_endpoint_traffic_to_node(node_hostname):
    """Drops all connections from pods to the node where those pods are
    running.
    It must be 'DROP' by default (according to calico docs), but
    actually it is set to RETURN
    FIXME: actually works until rebooting, see
    https://github.com/projectcalico/calico-containers/issues/1190
    """
    ETCD_ENDPOINT_TO_HOST_ACTION_KEY = 'DefaultEndpointToHostAction'
    etcd_path = ETCD_CALICO_HOST_CONFIG_KEY_PATH_TEMPLATE.format(
        hostname=node_hostname
    )
    Etcd(etcd_path).put(
        ETCD_ENDPOINT_TO_HOST_ACTION_KEY, value='DROP', asjson=False
    )


# Total number of nodes policies
# Each node policy path is
# ETCD_NETWORK_POLICY_NODES + <number> + '-' + <node name>
NODES_POLICY_COUNT = 2


def add_permissions_to_node_host_endpoint(node_hostname, node_ipv4):
    """Adds permissions to host endpoints.
    We allow here inbound traffic from host endpoint interface in KD cluster.
    """
    policies = get_node_host_endpoint_policy(node_hostname, node_ipv4)
    for i in range(NODES_POLICY_COUNT):
        Etcd(ETCD_NETWORK_POLICY_NODES).put(
            '{}-{}'.format(i, node_hostname),
            value=policies[i]
        )


def complete_calico_node_config(node_hostname, node_ipv4):
    """Sets necessary records to etcd to complete node configuration in
    calico:
        * creates host endpoint for the node;
        * sets DefaultEndpointToHostAction to DROP to prevent traffic from
          pods to the node on which those pods run.
    """
    create_calico_host_endpoint(node_hostname, node_ipv4)
    drop_endpoint_traffic_to_node(node_hostname)
    add_permissions_to_node_host_endpoint(node_hostname, node_ipv4)


def cleanup_node_network_policies(node_hostname):
    """Cleanup for calico node's policies after node deletion.
    """
    for i in range(NODES_POLICY_COUNT):
        Etcd(ETCD_NETWORK_POLICY_NODES).delete(
            '{}-{}'.format(i, node_hostname)
        )


def stop_node_k8_services(ssh):
    """Tries to stop docker daemon and kubelet service on the node
    :param ssh: ssh connection to the node
    """
    services = ('kubelet', 'kube-proxy', 'docker')
    cmd = 'systemctl stop '
    for service in services:
        _, o, e = ssh.exec_command(cmd + service)
        if o.channel.recv_exit_status():
            current_app.logger.warning(
                u"Failed to stop service '{}' on a failed node: {}".format(
                    service, e.read())
            )


def stop_aws_storage(ssh):
    """Stops aws storage (zpool or lvm export),
    detaches ebs volumes of the storage.
    """
    cmd = NODE_STORAGE_MANAGE_CMD + ' export-storage'
    from kubedock.settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
    cmd += ' --detach-ebs '\
        '--aws-access-key-id {0} --aws-secret-access-key {1}'.format(
            AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    _, o, e = ssh.exec_command(cmd)
    if o.channel.recv_exit_status():
        current_app.logger.error(
            'Failed to stop zpool on AWS node: {0}'.format(e.read())
        )
        return False
    result = o.read()
    try:
        data = json.loads(result)
    except (ValueError, TypeError):
        current_app.logger.error(
            'Unknown answer format from remote script: {0}\n'
            '==================\nSTDERR:\n{1}'.format(result, e.read())
        )
        return False
    if data['status'] != 'OK':
        current_app.logger.error(
            'Failed to stop storage: {0}'.format(
                data.get('data', {}).get('message')
            )
        )
        return False
    return True


def import_aws_storage(ssh, volumes, force_detach=False):
    """Imports aws storage to node given by ssh
    """
    cmd = NODE_STORAGE_MANAGE_CMD + ' import-aws-storage'
    from kubedock.settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
    cmd += ' --aws-access-key-id {0} --aws-secret-access-key {1}'.format(
        AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
    )
    if force_detach:
        cmd += ' --force-detach'
    cmd += ' --ebs-volumes {0}'.format(' '.join(volumes))
    current_app.logger.debug('Executing command: {}'.format(cmd))
    _, o, e = ssh.exec_command(cmd)
    if o.channel.recv_exit_status():
        current_app.logger.error(
            u"Failed to import zpool on AWS node: {}".format(e.read())
        )
        return False
    result = o.read()
    try:
        data = json.loads(result)
    except (ValueError, TypeError):
        current_app.logger.error(
            'Unknown answer format from remote script: {0}\n'
            '==================\nSTDERR:\n{1}'.format(result, e.read())
        )
        return False
    if data['status'] != 'OK':
        current_app.logger.error(
            'Failed to import storage: {0}'.format(
                data.get('data', {}).get('message')
            )
        )
        return False
    current_app.logger.debug(
        'Result of importing storage: {0}'.format(o.read())
    )
    return True


def move_aws_node_storage(from_node_ssh, to_node_ssh,
                          from_node, to_node):
    """Moves EBS volumes with KD zpool from one node to another on AWS setup.
    """
    # Flag show should we force detach volumes before attaching it to new
    # instance. It will be set in case if ssh to source node is unavailable,
    # so we can't detach volumes on that node.
    force_detach = False
    if from_node_ssh:
        # If we can get ssh to the old node, then try to do some preparations
        # before moving volumes:
        # * export zpool (also should unmount volumes)
        # * detach EBS volumes
        current_app.logger.debug(
            "Stopping node '{0}' storage".format(from_node.hostname)
        )
        if not stop_aws_storage(from_node_ssh):
            force_detach = True
    else:
        current_app.logger.debug(
            'Failed node is inaccessible. EBS volumes will be force detached'
        )
        force_detach = True

    ls_devices = db.session.query(LocalStorageDevices).filter(
        LocalStorageDevices.node_id == from_node.id
    ).all()
    volumes = [item.volume_name for item in ls_devices]
    current_app.logger.debug(
        "Importing on node '{0}' volumes: {1}".format(to_node.hostname,
                                                      volumes)
    )
    if not import_aws_storage(to_node_ssh, volumes, force_detach=force_detach):
        return False
    for dev in ls_devices:
        dev.node_id = to_node.id
    return True


def add_node_to_k8s(host, kube_type, is_ceph_installed=False):
    """
    :param host: Node hostname
    :param kube_type: Kuberdock kube type (integer id)
    :return: Error text if error else False
    """
    # TODO handle connection errors except requests.RequestException
    data = {
        'metadata': {
            'name': host,
            'labels': {
                'kuberdock-node-hostname': host,
                'kuberdock-kube-type': 'type_' + str(kube_type)
            },
            'annotations': {
                K8SNode.FREE_PUBLIC_IP_COUNTER_FIELD: '0'
            }
        },
        'spec': {
            'externalID': host,
        }
    }
    if is_ceph_installed:
        data['metadata']['labels'][NODE_CEPH_AWARE_KUBERDOCK_LABEL] = 'True'
    res = requests.post(get_api_url('nodes', namespace=False),
                        json=data)
    return res.text if not res.ok else False


def set_node_schedulable_flag(node_hostname, schedulable):
    """Marks given node as schedulable or unschedulable depending of
    'schedulable' flag value.
    :param node_hostname: name of the node in kubernetes
    :param schedulable: bool flag, if it is True, then node will be marked as
        schedulable, if Flase - unschedulable
    """
    url = get_api_url('nodes', node_hostname, namespace=False)
    try_times = 100
    for _ in range(try_times):
        try:
            node = requests.get(url).json()
            node['spec']['unschedulable'] = not schedulable
            res = requests.put(url, data=json.dumps(node))
        except (requests.RequestException, ValueError, KeyError):
            continue
        if res.ok:
            return True
    return False


def remove_node_from_k8s(host):
    r = requests.delete(get_api_url('nodes', host, namespace=False))
    return r.json()


def remove_node_install_log(hostname):
    try:
        os.remove(NODE_INSTALL_LOG_FILE.format(hostname))
    except OSError:
        pass


def revoke_celery_node_install_task(node):
    celery.control.revoke(
        task_id=NODE_INSTALL_TASK_ID.format(node.hostname, node.id),
        terminate=True,
    )
