
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

import json
import os
import socket
import subprocess
import time
from collections import OrderedDict
from datetime import datetime, timedelta

import requests
from flask import current_app
from sqlalchemy import event

from . import dns_management
from .core import db, ssh_connect
from .kapi import migrate_pod_utils, node_utils_aws
from .kapi.collect import collect, send
from .kapi.helpers import KubeQuery, raise_if_failure
from .kapi.node import Node as K8SNode
from .kapi.node_utils import (
    add_node_to_k8s, remove_node_from_k8s,
    setup_storage_to_aws_node, add_volume_to_node_ls,
    complete_calico_node_config)
from .kapi.pstorage import (
    delete_persistent_drives, remove_drives_marked_for_deletion,
    check_namespace_exists)
from .kapi.usage import update_states
from .kd_celery import celery, exclusive_task
from .models import Pod, ContainerState, PodState, PersistentDisk, User
from .nodes.models import Node, NodeAction, NodeFlag, NodeFlagNames
from .rbac.models import Role
from .settings import (
    NODE_INSTALL_LOG_FILE, MASTER_IP, AWS, NODE_INSTALL_TIMEOUT_SEC,
    CEPH, CEPH_KEYRING_PATH,
    CEPH_POOL_NAME, CEPH_CLIENT_USER,
    KUBERDOCK_INTERNAL_USER, NODE_SSH_COMMAND_SHORT_EXEC_TIMEOUT,
    CALICO, NODE_STORAGE_MANAGE_DIR, ZFS, WITH_TESTING)
from .system_settings.models import SystemSettings
from .updates.helpers import get_maintenance
from .users.models import SessionData
from .utils import (
    update_dict, get_api_url, send_event, send_event_to_role, send_logs,
    k8s_json_object_hook, get_timezone, NODE_STATUSES, POD_STATUSES,
)


class NodeInstallException(Exception):
    pass


class AddNodeTask(celery.Task):
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        with self.flask_app.app_context():
            node_id = kwargs.get('node_id', args[0])
            db_node = Node.get_by_id(node_id)
            db_node.state = NODE_STATUSES.troubles
            db.session.commit()
            send_event('node:change', {'id': db_node.id})


def get_pods_nodelay(pod_id=None, namespace=None):
    url = get_api_url('pods', namespace=namespace)
    if pod_id is not None:
        url = get_api_url('pods', pod_id, namespace=namespace)
    r = requests.get(url)
    return r.json()


def get_replicas_nodelay():
    r = requests.get(get_api_url('replicationControllers'))
    return r.json()


def get_services_nodelay(namespace=None):
    r = requests.get(get_api_url('services', namespace=namespace))
    return r.json()


def create_service_nodelay(data, namespace=None):
    r = requests.post(get_api_url('services', namespace=namespace),
                      data=json.dumps(data))
    return r.text  # TODO must return json()


def delete_pod_nodelay(item, namespace=None):
    r = requests.delete(get_api_url('pods', item, namespace=namespace))
    return r.json()


def delete_replica_nodelay(item):
    r = requests.delete(get_api_url('replicationControllers', item))
    return r.json()


def update_replica_nodelay(item, diff):
    url = get_api_url('replicationControllers', item)
    r = requests.get(url)
    data = json.loads(r.text, object_pairs_hook=OrderedDict)
    update_dict(data, diff)
    headers = {'Content-Type': 'application/json'}
    r = requests.put(url, data=json.dumps(data), headers=headers)
    return r.json()


def delete_service_nodelay(item, namespace=None):
    r = requests.delete(get_api_url('services', item, namespace=namespace))
    return r.json()


def deploy_node(fast, node_id, log_pod_ip):
    if fast:
        return node_utils_aws.deploy_node(node_id, log_pod_ip)
    else:
        return add_new_node(node_id, log_pod_ip, with_testing=WITH_TESTING,
                            skip_storate=True)


@celery.task(base=AddNodeTask)
def add_new_node(node_id, log_pod_ip, with_testing=False, redeploy=False,
                 ls_devices=None, ebs_volume=None, deploy_options=None,
                 skip_storate=False):
    db_node = Node.get_by_id(node_id)
    admin_rid = Role.query.filter_by(rolename="Admin").one().id
    channels = [i.id for i in SessionData.query.filter_by(role_id=admin_rid)]
    initial_evt_sent = False
    host = db_node.hostname
    kube_type = db_node.kube_id
    cpu_multiplier = SystemSettings.get_by_name('cpu_multiplier')
    memory_multiplier = SystemSettings.get_by_name('memory_multiplier')
    ku = User.query.filter(User.username == KUBERDOCK_INTERNAL_USER).first()
    token = ku.get_token() if ku else ''
    with open(NODE_INSTALL_LOG_FILE.format(host), 'w') as log_file:
        try:
            current_master_kubernetes_rpm = subprocess.check_output(
                ['rpm', '-q', 'kubernetes-master']).strip()
        except subprocess.CalledProcessError as e:
            err = 'KuberDock has incorrectly installed kubernetes' \
                  ' on master. {0}'.format(e.output)
            raise NodeInstallException(err)

        node_kubernetes_rpm = current_master_kubernetes_rpm.replace(
            'master', 'node')

        try:
            timezone = get_timezone()
        except OSError as e:
            raise NodeInstallException(
                'Cannot get master timezone: {}'.format(repr(e)))

        if redeploy:
            send_logs(node_id, 'Redeploy.', log_file, channels)
            send_logs(node_id, 'Remove node {0} from kubernetes...'.format(
                host), log_file, channels)
            result = remove_node_from_k8s(host)
            send_logs(node_id, json.dumps(result, indent=2), log_file,
                      channels)

        send_logs(
            node_id,
            'Node kubernetes package will be "{0}" (same version '
            'as master kubernetes)'.format(node_kubernetes_rpm),
            log_file, channels)

        send_logs(
            node_id,
            'Connecting to {0} with ssh with user "root" ...'.format(host),
            log_file, channels)

        # If we want to get rid of color codes in output we have to use vt220
        ssh, err = ssh_connect(host)
        if err:
            raise NodeInstallException(err)

        sftp = ssh.open_sftp()
        sftp.get_channel().settimeout(NODE_SSH_COMMAND_SHORT_EXEC_TIMEOUT)
        sftp.put('fslimit.py', '/fslimit.py')
        sftp.put('make_elastic_config.py', '/make_elastic_config.py')
        sftp.put('node_install.sh', '/node_install.sh')
        sftp.put('node_install_common.sh', '/node_install_common.sh')
        if not CALICO:
            sftp.put('node_network_plugin.sh', '/node_network_plugin.sh')
            sftp.put('node_network_plugin.py', '/node_network_plugin.py')
        # TODO refactor to copy all folder ones, or make kdnode package
        sftp.put('node_scripts/kd-ssh-user.sh', '/kd-ssh-user.sh')
        sftp.put('node_scripts/kd-docker-exec.sh', '/kd-docker-exec.sh')
        sftp.put('node_scripts/kd-ssh-user-update.sh',
                 '/kd-ssh-user-update.sh')
        sftp.put('node_scripts/kd-ssh-gc', '/kd-ssh-gc')

        # Copy node storage manage scripts
        remote_path = '/' + NODE_STORAGE_MANAGE_DIR
        try:
            sftp.stat(remote_path)
        except IOError:
            sftp.mkdir(remote_path)
        scripts = [
            'aws.py', 'common.py', '__init__.py', 'manage.py',
            'node_lvm_manage.py', 'node_zfs_manage.py'
        ]
        for script in scripts:
            sftp.put(NODE_STORAGE_MANAGE_DIR + '/' + script,
                     remote_path + '/' + script)

        # TODO this is obsoleted, remove later:
        sftp.put('pd.sh', '/pd.sh')

        sftp.put('kubelet_args.py', '/kubelet_args.py')
        sftp.put('/etc/kubernetes/configfile_for_nodes', '/configfile')
        sftp.put('/etc/pki/etcd/ca.crt', '/ca.crt')
        sftp.put('/etc/pki/etcd/etcd-client.crt', '/etcd-client.crt')
        sftp.put('/etc/pki/etcd/etcd-client.key', '/etcd-client.key')
        sftp.put('/etc/pki/etcd/etcd-dns.crt', '/etcd-dns.crt')
        sftp.put('/etc/pki/etcd/etcd-dns.key', '/etcd-dns.key')

        # AC-3652 Node backup
        sftp.put('backup_node.py', '/usr/bin/kd-backup-node')
        sftp.put('backup_node_merge.py', '/usr/bin/kd-backup-node-merge')

        if CEPH:
            TEMP_CEPH_CONF_PATH = '/tmp/kd_ceph_config'
            CEPH_CONF_SRC_PATH = '/var/lib/kuberdock/conf'
            try:
                sftp.stat(TEMP_CEPH_CONF_PATH)
            except IOError:
                sftp.mkdir(TEMP_CEPH_CONF_PATH)
            sftp.put(os.path.join(CEPH_CONF_SRC_PATH, 'ceph.conf'),
                     os.path.join(TEMP_CEPH_CONF_PATH, 'ceph.conf'))
            keyring_fname = os.path.basename(CEPH_KEYRING_PATH)
            sftp.put(
                os.path.join(CEPH_CONF_SRC_PATH, keyring_fname),
                os.path.join(TEMP_CEPH_CONF_PATH, keyring_fname)
            )

        sftp.close()

        deploy_vars = {
            'NODE_IP': db_node.ip,
            'AWS': AWS,
            'NODE_KUBERNETES': node_kubernetes_rpm,
            'MASTER_IP': MASTER_IP,
            'TZ': timezone,
            'NODENAME': host,
            'CPU_MULTIPLIER': cpu_multiplier,
            'MEMORY_MULTIPLIER': memory_multiplier,
            'FIXED_IP_POOLS': current_app.config['FIXED_IP_POOLS'],
            'TOKEN': token,
            'LOG_POD_IP': log_pod_ip,
            'PUBLIC_INTERFACE': db_node.public_interface or ''
        }
        deploy_cmd = 'bash /node_install.sh'

        if CEPH:
            deploy_vars['CEPH_CONF'] = TEMP_CEPH_CONF_PATH
        elif ZFS:
            deploy_vars['ZFS'] = 'yes'

        if CALICO:
            deploy_vars['CALICO'] = CALICO

        if with_testing:
            deploy_vars['WITH_TESTING'] = 'yes'

        # Via AC-3191 we need the way to pass some additional
        # parameters to node deploying.
        if deploy_options is not None:
            for k, v in deploy_options.items():
                k = '{}_PARAMS'.format(k)
                deploy_vars[k] = v

        set_vars_str = ' '.join('{key}="{value}"'.format(key=k, value=v)
                                for k, v in deploy_vars.items())
        cmd = '{set_vars} {deploy_cmd}'.format(set_vars=set_vars_str,
                                               deploy_cmd=deploy_cmd)

        s_time = time.time()
        i, o, e = ssh.exec_command(cmd,
                                   timeout=NODE_INSTALL_TIMEOUT_SEC,
                                   get_pty=True)
        try:
            while not o.channel.exit_status_ready():
                data = o.channel.recv(1024)
                while data:
                    # Here we want to send update event to all browsers but
                    # only after any update from a node has come.
                    if not initial_evt_sent:
                        send_event('node:change', {'id': db_node.id})
                        initial_evt_sent = True
                    for line in data.split('\n'):
                        send_logs(node_id, line, log_file, channels)
                    data = o.channel.recv(1024)
                    if (time.time() - s_time) > NODE_INSTALL_TIMEOUT_SEC:
                        raise socket.timeout()
                time.sleep(0.2)
        except socket.timeout:
            raise NodeInstallException(
                "Timeout hit during node install {} cmd".format(cmd))

        ret_code = o.channel.recv_exit_status()
        if ret_code != 0:
            raise NodeInstallException(
                "Node install failed cmd {} with retcode {}".format(
                    cmd, ret_code))

        ssh.exec_command('rm /node_install.sh',
                         timeout=NODE_SSH_COMMAND_SHORT_EXEC_TIMEOUT)
        ssh.exec_command('rm /node_install_common.sh',
                         timeout=NODE_SSH_COMMAND_SHORT_EXEC_TIMEOUT)

        if CEPH:
            NodeFlag.save_flag(
                node_id, NodeFlagNames.CEPH_INSTALLED, "true"
            )
            if not check_namespace_exists(node_ip=host):
                err_message = (
                    u'ERROR: '
                    u'CEPH pool "{0}" does not exists and can not be created. '
                    u'Create it manually, give rwx rights to user "{1}" '
                    u'and try again.\n'
                    u'If the pool already exists, then check the user {1} has '
                    u'rwx rights to it.'
                    .format(CEPH_POOL_NAME, CEPH_CLIENT_USER)
                )
                send_logs(node_id, err_message, log_file, channels)
                raise NodeInstallException(err_message)
        else:
            if skip_storate:
                send_logs(node_id, 'Skip storage setup, node is reserving...',
                          log_file, channels)
            else:
                send_logs(node_id, 'Setup persistent storage...', log_file,
                          channels)
                setup_node_storage(ssh, node_id, ls_devices, ebs_volume,
                                   channels)

        complete_calico_node_config(host, db_node.ip)

        send_logs(node_id, 'Rebooting node...', log_file, channels)
        ssh.exec_command(
            'reboot', timeout=NODE_SSH_COMMAND_SHORT_EXEC_TIMEOUT)

        # Here we can wait some time before add node to k8s to prevent
        # "troubles" status if we know that reboot will take more then
        # 1 minute. For now delay will be just 2 seconds (fastest reboot)
        time.sleep(2)

        err = add_node_to_k8s(host, kube_type, CEPH)
        if err:
            raise NodeInstallException(
                'ERROR adding node.', log_file, channels)

        send_logs(node_id, 'Adding Node completed successful.',
                  log_file, channels)
        send_logs(node_id, '===================================',
                  log_file, channels)
        send_logs(node_id, '*** During reboot node may have status '
                           '"troubles" and it will be changed '
                           'automatically right after node reboot, '
                           'when kubelet.service posts live status to '
                           'master(if all works fine) and '
                           'it\'s usually takes few minutes ***',
                  log_file, channels)

        ssh.close()

        db_node.state = NODE_STATUSES.completed
        db.session.commit()
        send_event('node:change', {'id': db_node.id})


def setup_node_storage(ssh, node_id, devices=None, ebs_volume=None,
                       log_channels=None):
    current_app.logger.debug(
        'setup_node_storage: devices = {}'.format(devices))
    if AWS:
        res, message = setup_storage_to_aws_node(
            ssh, node_id, EBS_volume_name=ebs_volume
        )
        if not res:
            raise NodeInstallException(
                'Failed to setup storage to AWS node: {}'.format(message))
        return

    if not devices:
        send_logs(node_id,
                  'No devices defined to local storage. Skip LVM setup.',
                  log_channels)
        return

    res, message = add_volume_to_node_ls(ssh, node_id, devices)
    current_app.logger.debug(
        'setup_node_storage: res = {}, message = {}'.format(res, message))
    if not res:
        raise NodeInstallException(
            'Failed to setup storage on the node: {}'.format(message))


@celery.task()
def send_stat():
    pass
    # send(collect())


@celery.task()
@exclusive_task(60 * 30)
def fix_pods_timeline():
    """
    Create ContainerStates that wasn't created and
    close the ones that must be closed.
    Close PodStates that wasn't closed.
    """
    t = [time.time()]
    css = ContainerState.query.filter(ContainerState.end_time.is_(None))
    t.append(time.time())
    # get pods from k8s
    # we need to get only KuberDock pods
    pods = KubeQuery().get(['pods'], {'labelSelector': 'kuberdock-pod-uid'})
    raise_if_failure(pods, "Can't get pods")
    pods = {
        pod['metadata']['labels']['kuberdock-pod-uid']:
            k8s_json_object_hook(pod) for pod in pods.get('items', [])}
    now = datetime.utcnow().replace(microsecond=0)
    t.append(time.time())

    updated_CS = set()
    for k8s_pod in pods.itervalues():
        updated_CS.update(update_states(k8s_pod, event_time=now))
    t.append(time.time())

    for cs in css:
        if cs in updated_CS:
            # pod was found in db and k8s,
            # and k8s have info about this container
            continue  # ContainerState was fixed in update_states()
        cs_next = ContainerState.query.join(PodState).filter(
            PodState.pod_id == cs.pod_state.pod_id,
            ContainerState.container_name == cs.container_name,
            ContainerState.start_time > cs.start_time,
        ).order_by(ContainerState.start_time).first()
        if cs_next:
            cs.fix_overlap(cs_next.start_time)
        elif pods.get(cs.pod_state.pod_id) is None:
            # it's the last CS and pod not found in k8s
            cs.end_time = now
            cs.exit_code, cs.reason = ContainerState.REASONS.pod_was_stopped

    # Close states for deleted pods if not closed.
    # Actually it is needed to be run once, but let it be run regularly.
    # Needed because there was bug in k8s2etcd service.
    # Sometime later it can be deleted (now is 2016-04-06).
    non_consistent_pss = db.session.query(PodState).join(PodState.pod).filter(
        Pod.status == POD_STATUSES.deleted,
        PodState.end_time.is_(None)
    )
    closed_states = 0
    for ps in non_consistent_pss:
        ps.end_time = datetime.utcnow()
        closed_states += 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    t.append(time.time())
    current_app.logger.debug('Fixed pods timeline: {0}'.format(
        ['{0:.3f}'.format(t2 - t1) for t1, t2 in zip(t[:-1], t[1:])]))
    current_app.logger.debug('Closed %s pod_states', closed_states)


def add_k8s_node_labels(nodename, labels):
    """Add given labels to the node in kubernetes
    :param nodename: node hostname
    :param labels: dict of labels to be patched.
    Look https://tools.ietf.org/html/rfc7386 for dict format
    """
    node = K8SNode(hostname=nodename)
    node.patch_labels(labels)


def _check_ceph_via_ssh(ssh):
    _, out, _ = ssh.exec_command('which rbd')
    return not out.channel.recv_exit_status()


def is_ceph_installed_on_node(hostname):
    """Checks CEPH client is installed on the node. Returns True if it is
    installed, otherwise - False.
    """
    ssh, error_message = ssh_connect(hostname)
    if error_message:
        return
    return _check_ceph_via_ssh(ssh)


@celery.task(rate_limit="1/m")
@exclusive_task(60 * 120)
def clean_deleted_drives():
    clean_drives_for_deleted_users()
    remove_drives_marked_for_deletion()


def clean_drives_for_deleted_users():
    ids = [
        item.id
        for item
        in db.session.query(PersistentDisk.id)
            .join(User).filter(User.deleted.is_(True))
    ]
    delete_persistent_drives(ids)


@celery.task(ignore_result=True)
def check_if_node_down(hostname):
    """ In some cases kubelet doesn't post it's status, and restart may help
    to make it alive. It's a workaround for kubelet bug.
    TODO: research the bug and remove the workaround
    """
    # Do not try to recover if maintenance mode is on
    if get_maintenance():
        current_app.warning(
            "Skip recover kubelet on '{}', because of maintenance mode is on"
            .format(hostname)
        )
        return
    node_is_failed = False
    ssh, error_message = ssh_connect(hostname, timeout=3)
    if error_message:
        current_app.logger.debug(
            'Failed connect to node %s: %s',
            hostname, error_message
        )
        node_is_failed = True
        ssh = None
    else:
        i, o, e = ssh.exec_command('systemctl restart kubelet')
        exit_status = o.channel.recv_exit_status()
        if exit_status != 0:
            node_is_failed = True
            current_app.logger.debug(
                'Failed to restart kubelet on node: %s, exit status: %s',
                hostname, exit_status
            )
    if node_is_failed:
        migrate_pod_utils.manage_failed_node(hostname, ssh, deploy_node)


@celery.task()
@exclusive_task(60 * 30, blocking=True)
def process_node_actions(action_type=None, node_host=None):
    actions = db.session.query(NodeAction).filter(
        NodeAction.timestamp > (datetime.utcnow() - timedelta(minutes=35))
    ).order_by(NodeAction.timestamp)
    if action_type is not None:
        actions = actions.filter(NodeAction.type == action_type)
    if node_host is not None:
        actions = actions.filter(NodeAction.host == node_host)
    for action in actions:
        ssh, error_message = ssh_connect(action.host)
        if error_message:
            continue
        i, o, e = ssh.exec_command(action.command)
        if o.channel.recv_exit_status() == 0:
            db.session.delete(action)
        ssh.close()
    db.session.commit()


node_multipliers = {
    'cpu_multiplier': '--cpu-multiplier',
    'memory_multiplier': '--memory-multiplier',
}


@event.listens_for(SystemSettings.value, 'set')
def update_node_multiplier(target, value, oldvalue, initiator):
    if target.name in node_multipliers:
        NodeAction.query.filter_by(type=target.name).delete()
        command = ('/usr/bin/env python '
                   '/var/lib/kuberdock/scripts/kubelet_args.py '
                   '{0}={1}'.format(node_multipliers[target.name], value))
        timestamp = datetime.utcnow()
        for node in Node.query:
            action = NodeAction(
                host=node.hostname,
                command=command,
                timestamp=timestamp,
                type=target.name,
            )
            db.session.add(action)
        db.session.commit()
        process_node_actions.delay(action_type=target.name)


@celery.task()
def make_backup():
    for node in Node.query.all():
        ssh, err = ssh_connect(node.ip)
        if err:
            continue
        i, o, e = ssh.exec_command('kd-backup-node /var/data', get_pty=True)
        with open('/tmp/out.txt', 'a') as f:
            try:
                while not o.channel.exit_status_ready():
                    data = o.channel.recv(1024)
                    while data:
                        f.write(data)
                        data = o.channel.recv(1024)
                    time.sleep(0.2)
            except socket.timeout:
                continue


@celery.task(bind=True, max_retries=5, default_retry_delay=10,
             ignore_results=True)
def create_wildcard_dns_record(self, base_domain):
    domain = '*.{}'.format(base_domain)
    if current_app.config['AWS']:
        ok, message = dns_management.create_or_update_record(
            domain, 'CNAME')
    else:
        ok, message = dns_management.create_or_update_record(
            domain, 'A')
    if not ok:
        if self.request.retries < self.max_retries:
            self.retry(args=(base_domain,))
        msg = 'Failed to create DNS record for domain "{domain}": {reason}'
        send_event_to_role(
            'notify:error',
            {'message': msg.format(domain=base_domain, reason=message)},
            'Admin')


@celery.task(bind=True, max_retries=5, default_retry_delay=10,
             ignore_results=True)
def delete_wildcard_dns_record(self, base_domain):
    domain = '*.{}'.format(base_domain)
    if current_app.config['AWS']:
        ok, message = dns_management.delete_record(
            domain, 'CNAME')
    else:
        ok, message = dns_management.delete_record(
            domain, 'A')
    if not ok:
        if self.request.retries < self.max_retries:
            self.retry(args=(base_domain,))
        msg = 'Failed to delete DNS record for domain "{domain}": {reason}'
        send_event_to_role(
            'notify:error',
            {'message': msg.format(domain=base_domain, reason=message)},
            'Admin')
