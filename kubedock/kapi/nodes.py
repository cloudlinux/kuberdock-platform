
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

"""Management functions for nodes.
"""
import os
import socket

from flask import current_app

from kubedock.exceptions import InternalPodsCreationError
from . import ingress
from . import pstorage
from .node_utils import (
    add_node_to_db, delete_node_from_db, remove_ls_storage,
    cleanup_node_network_policies, revoke_celery_node_install_task,
    remove_node_install_log, remove_node_from_k8s)
from .service_pods import (
    create_dns_pod,
    create_logs_pod,
    create_policy_pod,
    delete_logs_pod,
)
from .. import tasks
from ..billing import kubes_to_limits
from ..billing.models import Kube
from ..core import db, ExclusiveLockContextManager
from ..domains.models import BaseDomain
from ..exceptions import APIError
from ..nodes.models import Node, NodeFlag, NodeFlagNames
from ..pods.models import PodIP
from ..settings import (
    MASTER_IP, KUBERDOCK_SETTINGS_FILE, NODE_INSTALL_LOG_FILE,
    NODE_INSTALL_TASK_ID, ZFS, AWS)
from ..users.models import User
from ..utils import (
    send_event_to_role,
    run_ssh_command,
    NODE_STATUSES,
    get_node_token,
    ip2int,
    get_current_host_ips,
    get_node_interface,
)


def create_node(ip, hostname, kube_id, public_interface=None,
                do_deploy=True, with_testing=False,
                ls_devices=None, ebs_volume=None,
                options=None):
    """Creates new node in database, kubernetes. Deploys all needed packages
    and settings on the new node, if do_deploy is specified.
    :param ip: optional IP address for the node. If it's not specified, then
        ip address will be retrieved by given hostname
    :param hostname: name of the node host
    :param public_interface: Network interface name on which public IPs
        will be bind
    :param kube_id: kube type identifier for the new node
    :param do_deploy: flag switches on deployment process on the node host
    :param with_testing: enables/disables testing repository for deployment
    :param ls_devices: list of block device names which should be used for
        local storage on the node (not works on CEPH-enabled cluster)
    :param ebs_volume: EBS volume name. Use existing Amazon EBS volume for
        node's local storage. Works only on AWS-clusters. If it is not
        defined on AWS cluster, then a new EBS volume will be created
        with some random name.
    :return: database entity for created node
    """
    # Store all hostnames in lowercase
    hostname = hostname.lower()
    if Node.get_by_name(hostname) is not None:
        raise APIError('Conflict, Node with hostname "{0}" already exists'
                       .format(hostname), status_code=409)

    if not MASTER_IP:
        raise APIError('There is no MASTER_IP specified in {0}.'
                       'Check that file has not been renamed by package '
                       'manager to .rpmsave or similar'
                       .format(KUBERDOCK_SETTINGS_FILE))

    if ZFS and not (AWS or ls_devices):
        raise APIError(
            'Kuberdock configured with ZFS backend, there must be at least '
            'one device specified during node creation.'
        )

    if ip is None:
        ip = socket.gethostbyname(hostname)
    all_master_ips = get_current_host_ips()
    if ip in all_master_ips:
        raise APIError('Looks like you are trying to add MASTER as NODE, '
                       'this kind of setup is not supported at this '
                       'moment')

    pod_ip = PodIP.query.filter_by(ip_address=ip2int(unicode(ip))).first()
    if pod_ip:
        raise APIError('Node IP ({0}) already assigned '
                       'to the Pod: "{1}"'.format(ip, pod_ip.pod.name))

    token = get_node_token()
    if token is None:
        raise APIError('Error reading Kubernetes Node auth token')

    _check_node_hostname(ip, hostname)
    _check_node_ip(ip, hostname)
    node = Node(
        ip=ip, hostname=hostname, kube_id=kube_id,
        public_interface=public_interface, state=NODE_STATUSES.pending
    )

    try:
        # clear old log before it pulled by SSE event
        os.remove(NODE_INSTALL_LOG_FILE.format(hostname))
    except OSError:
        pass

    node = add_node_to_db(node)

    log_pod = _create_internal_pods(hostname, token)
    _deploy_node(node, log_pod['podIP'], do_deploy, with_testing,
                 ls_devices=ls_devices, ebs_volume=ebs_volume, options=options)

    node.kube.send_event('change')
    return node


def _create_internal_pods(hostname, token):
    ku = User.get_internal()

    with ExclusiveLockContextManager('Nodes._create_internal_pods',
                                     blocking=True, ttl=3600) as lock:
        if not lock:
            raise InternalPodsCreationError(details={'node': hostname})
        log_pod = create_logs_pod(hostname, ku)
        current_app.logger.debug('Created log pod: {}'.format(log_pod))
        create_dns_pod(hostname, ku)
        create_policy_pod(hostname, ku, token)
        if BaseDomain.query.first() and not ingress.is_subsystem_up():
            ingress.prepare_ip_sharing()
        return log_pod


def mark_node_as_being_deleted(node_id):
    node = Node.query.filter(Node.id == node_id).first()
    if node is None:
        raise APIError('Node not found, id = {}'.format(node_id))
    _check_node_can_be_deleted(node)
    node.state = NODE_STATUSES.deletion
    db.session.commit()
    return node


def delete_node(node_id=None, node=None, force=False, verbose=True):
    """Deletes node."""

    # As long as the func is allowed to be called after mark_node_as_being_
    # deleted func there's no need to double DB request,
    # let's get the node object directly.
    if node is None:
        if node_id is None:
            raise APIError('Insufficient data for operation')
        node = Node.query.filter(Node.id == node_id).first()
        if node is None:
            raise APIError('Node not found, id = {}'.format(node_id))

    hostname = node.hostname
    if node_id is None:
        node_id = node.id

    if not force:
        _check_node_can_be_deleted(node)

    try:
        revoke_celery_node_install_task(node)
    except Exception as e:
        raise APIError('Couldn\'t cancel node deployment. Error: {}'.format(e))

    delete_logs_pod(node.hostname)

    try:
        delete_node_from_db(node)
    except Exception as e:
        raise APIError(u'Failed to delete node from DB: {}'.format(e))

    ls_clean_error = remove_ls_storage(hostname, raise_on_error=False)
    res = remove_node_from_k8s(hostname)
    if res['status'] == 'Failure' and res['code'] != 404:
        raise APIError('Failed to delete node in k8s: {0}, code: {1}. \n'
                       'Please check and remove it manually if needed.'
                       .format(res['message'], res['code']))

    remove_node_install_log(hostname)

    try:
        cleanup_node_network_policies(hostname)
    except:
        error_message = ("Failed to cleanup network policies "
                         "for the node: {}".format(hostname))
        current_app.logger.exception(error_message)
        send_event_to_role('notify:error',
                           {'message': error_message}, 'Admin')

    if ls_clean_error:
        error_message = 'Failed to clean Local storage volumes on ' \
                        'the node.\nYou have to clean it manually if needed:' \
                        '\n{}'.format(ls_clean_error)
        if verbose:
            current_app.logger.warning(error_message)
        send_event_to_role('notify:warning',
                           {'message': error_message}, 'Admin')
    send_event_to_role('node:deleted', {
        'id': node_id,
        'message': 'Node successfully deleted.'
    }, 'Admin')


def _check_node_can_be_deleted(node):
    """Check if the node could be deleted.
    If it can not, then raise APIError.
    Also tries to cleanup node from PD's that were marked to delete, but not
    yet physically deleted.
    """
    is_locked, reason = pstorage.check_node_is_locked(node.id, cleanup=True)
    if is_locked:
        raise APIError("Node '{}' can't be deleted. Reason: {}".format(
            node.hostname, reason
        ))
    if current_app.config['FIXED_IP_POOLS'] and node.ippool:
        pools = ' '.join(str(p) for p in node.ippool)
        raise APIError("Node '{}' can't be deleted. Has active pools "
                       "assigned: {}".format(node.hostname, pools))


def edit_node_hostname(node_id, ip, hostname):
    """Replaces host name for the node."""
    m = Node.get_by_id(node_id)
    if m is None:
        raise APIError("Error. Node {0} doesn't exists".format(node_id),
                       status_code=404)
    if ip != m.ip:
        raise APIError("Error. Node ip can't be reassigned, "
                       "you need delete it and create new.")
    hostname = hostname.lower()
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
    tasks.add_new_node.apply_async(node.id, redeploy=True,
                                   task_id=NODE_INSTALL_TASK_ID.format(
                                       node.hostname, node.id
                                   ))


def _check_node_hostname(ip, hostname):
    status, message = run_ssh_command(ip, "uname -n")
    if status:
        raise APIError(
            "Error while trying to get node name: {}".format(message))
    uname_hostname = message.strip()
    uname_hostname = uname_hostname.lower()
    if uname_hostname != hostname:
        if uname_hostname in hostname:
            status, h_message = run_ssh_command(ip, "hostname -f")
            if status:
                raise APIError(
                    "Error while trying to get node h_name: {}".format(
                        h_message))
            uname_hostname = h_message.strip()
            uname_hostname = uname_hostname.lower()
    if uname_hostname != hostname:
        raise APIError('Wrong node name. {} resolves itself by name {}'.format(
            hostname, uname_hostname))


def _check_node_ip(ip, hostname):
    status, message = run_ssh_command(ip, 'ip -o -4 address show')
    if status:
        raise APIError('Error while trying to get node IP address: '
                       '{0}'.format(message))
    node_interface = get_node_interface(message, ip)
    if node_interface is None:
        raise APIError(
            'Node hostname "{0}" is resolved to "{1}" '
            'and the Node is accessible by this IP '
            'but there is no such IP address '
            'on any Node network interface'.format(hostname, ip))


def _deploy_node(dbnode, log_pod_ip, do_deploy, with_testing,
                 ls_devices=None, ebs_volume=None, options=None):
    if do_deploy:
        tasks.add_new_node.apply_async(
            [dbnode.id, log_pod_ip],
            dict(
                with_testing=with_testing,
                ls_devices=ls_devices,
                ebs_volume=ebs_volume,
                deploy_options=options,
            ),
            task_id=NODE_INSTALL_TASK_ID.format(dbnode.hostname, dbnode.id)
        )
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
            dbnode.state = NODE_STATUSES.completed
            db.session.commit()
