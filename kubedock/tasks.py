import os
import ipaddress
import json
import operator
import re
import requests
import subprocess
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from sqlalchemy import event

# requests .json() errors handling workaround.
# requests module uses simplejson as json by default
# that raises JSONDecodeError if .json() method fails
# but if simplejson is not available requests uses json module
# that raises ValueError in this case
try:
    from simplejson import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

from flask import current_app
from .core import db, ssh_connect
from .utils import (
    update_dict, get_api_url, send_event, send_logs, k8s_json_object_hook,
    get_timezone,
)
from .stats import StatWrap5Min
from .kubedata.kubestat import KubeUnitResolver, KubeStat
from .models import Pod, ContainerState, PodState, PersistentDisk, User
from .nodes.models import Node, NodeAction, NodeFlag, NodeFlagNames
from .users.models import SessionData
from .rbac.models import Role
from .system_settings.models import SystemSettings
from .settings import (
    NODE_INSTALL_LOG_FILE, MASTER_IP, AWS, NODE_INSTALL_TIMEOUT_SEC,
    NODE_CEPH_AWARE_KUBERDOCK_LABEL, CEPH, CEPH_KEYRING_PATH,
    NODE_SSH_COMMAND_SHORT_EXEC_TIMEOUT)
from .kapi.collect import collect, send
from .kapi.pstorage import (
    delete_persistent_drives, remove_drives_marked_for_deletion,
    check_namespace_exists)
from .kapi.usage import update_states

from .kd_celery import celery, exclusive_task


class AddNodeTask(celery.Task):
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        with self.flask_app.app_context():
            node_id = kwargs.get('node_id', args[0])
            db_node = Node.get_by_id(node_id)
            db_node.state = 'troubles'
            db.session.commit()


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
    return r.text   # TODO must return json()


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


def remove_node_by_host(host):
    r = requests.delete(get_api_url('nodes', host, namespace=False))
    return r.json()


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
                'kuberdock-kube-type':
                    'type_' + str(kube_type)
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


@celery.task(base=AddNodeTask)
def add_new_node(node_id, with_testing=False, redeploy=False,
                 deploy_options=None):
    db_node = Node.get_by_id(node_id)
    admin_rid = Role.query.filter_by(rolename="Admin").one().id
    channels = [i.id for i in SessionData.query.filter_by(role_id=admin_rid)]
    initial_evt_sent = False
    host = db_node.hostname
    kube_type = db_node.kube_id
    cpu_multiplier = SystemSettings.get_by_name('cpu_multiplier')
    memory_multiplier = SystemSettings.get_by_name('memory_multiplier')
    with open(NODE_INSTALL_LOG_FILE.format(host), 'w') as log_file:
        try:
            current_master_kubernetes = subprocess.check_output(
                ['rpm', '-q', 'kubernetes-master']).strip()
        except subprocess.CalledProcessError as e:
            mes = 'Kuberdock needs correctly installed kubernetes' \
                  ' on master. {0}'.format(e.output)
            send_logs(node_id, mes, log_file, channels)
            db_node.state = 'completed'
            db.session.commit()
            return mes
        except OSError:     # no rpm
            current_master_kubernetes = 'kubernetes-master'
        current_master_kubernetes = current_master_kubernetes.replace(
            'master', 'node')

        try:
            timezone = get_timezone()
        except OSError as e:
            timezone = 'UTC'
            error_message = '{0}. Using "{1}"'.format(e, timezone)
            send_logs(node_id, error_message, log_file, channels)

        if redeploy:
            send_logs(node_id, 'Redeploy.', log_file, channels)
            send_logs(node_id, 'Remove node {0} from kubernetes...'.format(
                host), log_file, channels)
            result = remove_node_by_host(host)
            send_logs(node_id, json.dumps(result, indent=2), log_file,
                      channels)

        send_logs(node_id, 'Node kubernetes package will be'
                           ' "{0}" (same version as master kubernetes)'
                  .format(current_master_kubernetes), log_file, channels)

        send_logs(node_id, 'Connecting to {0} with ssh with user "root" ...'
                  .format(host), log_file, channels)
        # If we want to got reed of color codes in output we have to use vt220
        ssh, error_message = ssh_connect(host)
        if error_message:
            send_logs(node_id, error_message, log_file, channels)
            db_node.state = 'completed'
            db.session.commit()
            return error_message

        i, o, e = ssh.exec_command('ip -o -4 address show',
                                   timeout=NODE_SSH_COMMAND_SHORT_EXEC_TIMEOUT)
        node_interface = get_node_interface(o.read(), db_node.ip)
        sftp = ssh.open_sftp()
        sftp.put('fslimit.py', '/fslimit.py')
        sftp.put('make_elastic_config.py', '/make_elastic_config.py')
        sftp.put('node_install.sh', '/node_install.sh')
        sftp.put('node_network_plugin.sh', '/node_network_plugin.sh')
        sftp.put('node_network_plugin.py', '/node_network_plugin.py')
        sftp.put('pd.sh', '/pd.sh')
        sftp.put('kubelet_args.py', '/kubelet_args.py')
        sftp.put('/etc/kubernetes/configfile_for_nodes', '/configfile')
        sftp.put('/etc/pki/etcd/ca.crt', '/ca.crt')
        sftp.put('/etc/pki/etcd/etcd-client.crt', '/etcd-client.crt')
        sftp.put('/etc/pki/etcd/etcd-client.key', '/etcd-client.key')
        sftp.put('/etc/pki/etcd/etcd-dns.crt', '/etcd-dns.crt')
        sftp.put('/etc/pki/etcd/etcd-dns.key', '/etcd-dns.key')
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
        deploy_cmd = 'AWS={0} CUR_MASTER_KUBERNETES={1} MASTER_IP={2} '\
                     'FLANNEL_IFACE={3} TZ={4} NODENAME={5} '\
                     'CPU_MULTIPLIER={6} MEMORY_MULTIPLIER={7} '\
                     'bash /node_install.sh'
        if CEPH:
            deploy_cmd = 'CEPH_CONF={} '.format(
                TEMP_CEPH_CONF_PATH) + deploy_cmd
        # we pass ports and hosts to let the node know which hosts are allowed
        if with_testing:
            deploy_cmd = 'WITH_TESTING=yes ' + deploy_cmd

        # Via AC-3191 we need the way to pass some additional
        # parameters to node deploying.
        if deploy_options is not None:
            for key, value in deploy_options.items():
                new_param = "{0}_PARAMS='{1}' ".format(key, value)
                deploy_cmd = new_param + deploy_cmd

        i, o, e = ssh.exec_command(
            deploy_cmd.format(AWS, current_master_kubernetes, MASTER_IP,
                              node_interface, timezone, host,
                              cpu_multiplier, memory_multiplier,
                              timeout=NODE_SSH_COMMAND_SHORT_EXEC_TIMEOUT),
            get_pty=True)
        s_time = time.time()
        while not o.channel.exit_status_ready():
            data = o.channel.recv(1024)
            while data:
                # Here we want to send update event to all browsers but only
                # after any update from a node has come.
                if not initial_evt_sent:
                    send_event('node:change', {'id': db_node.id})
                    initial_evt_sent = True
                for line in data.split('\n'):
                    send_logs(node_id, line, log_file, channels)
                data = o.channel.recv(1024)
            if (time.time() - s_time) > NODE_INSTALL_TIMEOUT_SEC:
                err = 'Timeout during install. Installation has failed.'
                send_logs(node_id, err, log_file, channels)
                ssh.exec_command('rm /node_install.sh')
                ssh.close()
                db_node.state = 'completed'
                db.session.commit()
                return err
            time.sleep(0.2)

        try:
            # this raises an exception in case of a lost ssh connection
            # and node is in 'pending' state instead of 'troubles'
            s = o.channel.recv_exit_status()
            ssh.exec_command('rm /node_install.sh',
                             timeout=NODE_SSH_COMMAND_SHORT_EXEC_TIMEOUT)
        except Exception as e:
            send_logs(node_id, 'Error: {}\n'.format(e), log_file)

        if s != 0:
            res = 'Installation script error. Exit status: {0}.'.format(s)
            send_logs(node_id, res, log_file, channels)
        else:
            if CEPH:
                NodeFlag.save_flag(
                    node_id, NodeFlagNames.CEPH_INSTALLED, "true"
                )
                check_namespace_exists(node_ip=host)
            send_logs(node_id, 'Rebooting node...', log_file, channels)
            ssh.exec_command('reboot',
                             timeout=NODE_SSH_COMMAND_SHORT_EXEC_TIMEOUT)
            # Here we can wait some time before add node to k8s to prevent
            # "troubles" status if we know that reboot will take more then
            # 1 minute. For now delay will be just 2 seconds (fastest reboot)
            time.sleep(2)
            err = add_node_to_k8s(host, kube_type, CEPH)
            if err:
                send_logs(node_id, 'ERROR adding node.', log_file, channels)
                send_logs(node_id, err, log_file, channels)
            else:
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
        db_node.state = 'completed'
        db.session.commit()
        if s != 0:
            # Until node has been rebooted we try to delay update
            # status on front. So we update it only in error case

            # send update in common channel for all admins
            send_event('node:change', {'id': db_node.id})


@celery.task()
@exclusive_task(60 * 30)
def pull_hourly_stats():
    try:
        data = KubeStat(resolution=300).stats(KubeUnitResolver().all())
    except Exception:
        current_app.logger.exception(
            'Skip pulling statistics because of error.')
        return
    time_windows = set(map(operator.itemgetter('time_window'), data))
    rv = db.session.query(StatWrap5Min).filter(
        StatWrap5Min.time_window.in_(time_windows))
    existing_windows = set(map((lambda x: x.time_window), rv))
    for entry in data:
        if entry['time_window'] in existing_windows:
            continue
        db.session.add(StatWrap5Min(**entry))
    db.session.commit()


@celery.task()
def send_stat():
    send(collect())


def get_node_interface(data, node_ip):
    ip = ipaddress.ip_address(unicode(node_ip))
    patt = re.compile(r'(?P<iface>\w+)\s+inet\s+(?P<ip>[0-9\/\.]+)')
    for line in data.splitlines():
        m = patt.search(line)
        if m is None:
            continue
        iface = ipaddress.ip_interface(unicode(m.group('ip')))
        if ip == iface.ip:
            return m.group('iface')


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
    pods = requests.get(get_api_url('pods', namespace=False))
    pods = {pod['metadata'].get('labels', {}).get('kuberdock-pod-uid'): pod
            for pod in pods.json(object_hook=k8s_json_object_hook).get('items')
            }
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
    non_consistent_pss = db.session.query(PodState) \
        .join(PodState.pod).filter(
        Pod.status == 'deleted',
        PodState.end_time.is_(None))
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
        ['{0:.3f}'.format(t2-t1) for t1, t2 in zip(t[:-1], t[1:])]))
    current_app.logger.debug('Closed %s pod_states', closed_states)


def add_k8s_node_labels(nodename, labels):
    """Add given labels to the node in kubernetes
    :param nodename: node hostname
    :param labels: dict of labels to add
    """
    headers = {'Content-Type': 'application/strategic-merge-patch+json'}
    res = requests.patch(
        get_api_url('nodes', nodename, namespace=False),
        json={'metadata': {'labels': labels}},
        headers=headers
    )


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
        item.id for item in db.session.query(PersistentDisk.id).join(
            User).filter(User.deleted.is_(True))
    ]
    delete_persistent_drives(ids)


@celery.task(ignore_result=True)
def check_if_node_down(hostname):
    # In some cases kubelet doesn't post it's status, and restart may help
    # to make it alive. It's a workaround for kubelet bug.
    # TODO: research the bug and remove the workaround
    ssh, error_message = ssh_connect(hostname, timeout=3)
    if error_message:
        current_app.logger.debug(
            'Failed connect to node %s: %s',
            hostname, error_message
        )
        return
    i, o, e = ssh.exec_command('systemctl restart kubelet')
    exit_status = o.channel.recv_exit_status()
    if exit_status != 0:
        current_app.logger.debug(
            'Failed to restart kubelet on node: %s, exit status: %s',
            hostname, exit_status
        )


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
