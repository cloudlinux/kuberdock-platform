import ipaddress
import json
import operator
import re
import requests
import subprocess
import time
from collections import OrderedDict
from datetime import datetime, timedelta

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
from .nodes.models import NodeMissedAction, Node, NodeFlag, NodeFlagNames
from .settings import (
    NODE_INSTALL_LOG_FILE, MASTER_IP, AWS, NODE_INSTALL_TIMEOUT_SEC,
    PORTS_TO_RESTRICT, NODE_CEPH_AWARE_KUBERDOCK_LABEL)
from .kapi.collect import collect, send
from .kapi.pstorage import (
    delete_persistent_drives, remove_drives_marked_for_deletion)
from .kapi.usage import update_states

from .kd_celery import celery


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


def get_all_nodes():
    r = requests.get(get_api_url('nodes', namespace=False))
    return r.json().get('items') or []


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


@celery.task()
def add_new_node(node_id, with_testing=False, nodes=None, redeploy=False):

    db_node = Node.get_by_id(node_id)
    initial_evt_sent = False
    host = db_node.hostname
    kube_type = db_node.kube_id
    with open(NODE_INSTALL_LOG_FILE.format(host), 'w') as log_file:
        try:
            current_master_kubernetes = subprocess.check_output(
                ['rpm', '-q', 'kubernetes-master']).strip()
        except subprocess.CalledProcessError as e:
            mes = 'Kuberdock needs correctly installed kubernetes' \
                  ' on master. {0}'.format(e.output)
            send_logs(node_id, mes, log_file)
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
            send_logs(node_id, error_message, log_file)

        if redeploy:
            send_logs(node_id, 'Redeploy.', log_file)
            send_logs(node_id, 'Remove node {0} from kubernetes...'.format(host),
                      log_file)
            result = remove_node_by_host(host)
            send_logs(node_id, json.dumps(result, indent=2), log_file)

        send_logs(node_id, 'Current kubernetes package on master is'
                           ' "{0}". Will install same package.'
                           .format(current_master_kubernetes), log_file)

        send_logs(node_id, 'Connecting to {0} with ssh with user "root" ...'
                  .format(host), log_file)
        # If we want to got reed of color codes in output we have to use vt220
        ssh, error_message = ssh_connect(host)
        if error_message:
            send_logs(node_id, error_message, log_file)
            db_node.state = 'completed'
            db.session.commit()
            return error_message
        is_ceph_installed = _check_ceph_via_ssh(ssh)
        if is_ceph_installed:
            NodeFlag.save_flag(node_id, NodeFlagNames.CEPH_INSTALLED, "true")

        i, o, e = ssh.exec_command('ip -o -4 address show')
        node_interface = get_node_interface(o.read())
        sftp = ssh.open_sftp()
        sftp.put('fslimit.py', '/fslimit.py')
        sftp.put('make_elastic_config.py', '/make_elastic_config.py')
        sftp.put('node_install.sh', '/node_install.sh')
        sftp.put('node_network_plugin.sh', '/node_network_plugin.sh')
        sftp.put('node_network_plugin.py', '/node_network_plugin.py')
        sftp.put('docker-cleaner.sh', '/docker-cleaner.sh')
        sftp.put('pd.sh', '/pd.sh')
        sftp.put('/etc/kubernetes/configfile_for_nodes', '/configfile')
        sftp.put('/etc/pki/etcd/ca.crt', '/ca.crt')
        sftp.put('/etc/pki/etcd/etcd-client.crt', '/etcd-client.crt')
        sftp.put('/etc/pki/etcd/etcd-client.key', '/etcd-client.key')
        sftp.put('/etc/pki/etcd/etcd-dns.crt', '/etcd-dns.crt')
        sftp.put('/etc/pki/etcd/etcd-dns.key', '/etcd-dns.key')
        sftp.close()
        deploy_cmd = 'AWS={0} CUR_MASTER_KUBERNETES={1} MASTER_IP={2} '\
                     'FLANNEL_IFACE={3} TZ={4} NODENAME={5} '\
                     'bash /node_install.sh{6}'
        # we pass ports and hosts to let the node know which hosts are allowed
        data_for_firewall = reduce(
            (lambda x, y: x + ' {0}'.format(','.join(y))),
                [map(str, l) for l in PORTS_TO_RESTRICT, nodes if l], '')
        if with_testing:
            deploy_cmd = 'WITH_TESTING=yes ' + deploy_cmd
        i, o, e = ssh.exec_command(
            deploy_cmd.format(AWS, current_master_kubernetes, MASTER_IP,
                              node_interface, timezone, host,
                              data_for_firewall),
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
                    send_logs(node_id, line, log_file)
                data = o.channel.recv(1024)
            if (time.time() - s_time) > NODE_INSTALL_TIMEOUT_SEC:
                err = 'Timeout during install. Installation has failed.'
                send_logs(node_id, err, log_file)
                ssh.exec_command('rm /node_install.sh')
                ssh.close()
                db_node.state = 'completed'
                db.session.commit()
                return err
            time.sleep(0.2)
        s = o.channel.recv_exit_status()
        ssh.exec_command('rm /node_install.sh')
        if s != 0:
            res = 'Installation script error. Exit status: {0}.'.format(s)
            send_logs(node_id, res, log_file)
        else:
            send_logs(node_id, 'Rebooting node...', log_file)
            ssh.exec_command('reboot')
            err = add_node_to_k8s(host, kube_type, is_ceph_installed)
            if err:
                send_logs(node_id, 'ERROR adding node.', log_file)
                send_logs(node_id, err, log_file)
            else:
                send_logs(node_id, 'Adding Node completed successful.',
                          log_file)
                send_logs(node_id, '===================================', log_file)
                send_logs(node_id, '*** During reboot node may have status '
                                   '"troubles" and it will be changed '
                                   'automatically right after node reboot, '
                                   'when kubelet.service posts live status to '
                                   "master(if all works fine) and it's usually "
                                   'takes few minutes ***', log_file)
        ssh.close()
        db_node.state = 'completed'
        db.session.commit()
        if s != 0:
            # Until node has been rebooted we try to delay update
            # status on front. So we update it only in error case

            # send update in common channel for all admins
            send_event('node:change', {'id': db_node.id})


def parse_pods_statuses(data):
    """
    Get pod statuses from k8s pods list and database.

    :param data: k8s PodList
    :returns: dict -> with keys - kuberdock pod ids and values - structure
        like Pod.status, but with nodeName, kuberdock pod id and
        number of kubes for each container in Pod.status.containerStatuses.
    """
    db_pods = {}
    for pod_id, pod_config in Pod.query.filter(
            Pod.status != 'deleted').values(Pod.id, Pod.config):
        kubes = {}
        containers = json.loads(pod_config).get('containers', [])
        for container in containers:
            if 'kubes' in container:
                kubes[container['name']] = container['kubes']
        db_pods[pod_id] = {'kubes': kubes}

    res = {}
    for item in data.get('items'):
        pod_id = item['metadata'].get('labels', {}).get('kuberdock-pod-uid')
        if pod_id not in db_pods:  # skip deleted or alien pods
            continue

        current_state = item['status']
        current_state['nodeName'] = item['spec'].get('nodeName')
        current_state['uid'] = pod_id
        if 'containerStatuses' in current_state:
            for container in current_state['containerStatuses']:
                if container['name'] in db_pods[pod_id]['kubes']:
                    container['kubes'] = db_pods[pod_id]['kubes'][container['name']]
        res[pod_id] = current_state
    return res


@celery.task()
def pull_hourly_stats():
    try:
        data = KubeStat(resolution=300).stats(KubeUnitResolver().all())
    except Exception:
        data = []
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
def process_missed_actions():
    actions = db.session.query(NodeMissedAction).filter(
        NodeMissedAction.time_stamp > (datetime.utcnow()-timedelta(minutes=35))
        ).order_by(NodeMissedAction.time_stamp)
    for action in actions:
        ssh, error_message = ssh_connect(action.host)
        if error_message:
            continue
        i, o, e = ssh.exec_command(action.command)
        if o.channel.recv_exit_status() != 0:
            continue
        db.session.delete(action)
        ssh.close()
    db.session.commit()


@celery.task()
def send_stat():
    send(collect())


def get_node_interface(data):
    if not MASTER_IP:
        return
    ip = ipaddress.ip_address(unicode(MASTER_IP))
    patt = re.compile(r'(?P<iface>\w+)\s+inet\s+(?P<ip>[0-9\/\.]+)')
    for line in data.splitlines():
        m = patt.search(line)
        if m is None:
            continue
        iface = ipaddress.ip_interface(unicode(m.group('ip')))
        if ip in iface.network:
            return m.group('iface')


@celery.task()
def fix_pods_timeline():
    """
    Create ContainerStates that wasn't created and
    close the ones that must be closed.
    """
    t = [time.time()]
    css = ContainerState.query.filter(ContainerState.end_time.is_(None))
    t.append(time.time())
    # get pods from k8s
    pods = requests.get(get_api_url('pods', namespace=False))
    pods = parse_pods_statuses(pods.json(object_hook=k8s_json_object_hook))
    now = datetime.utcnow().replace(microsecond=0)
    t.append(time.time())

    updated_CS = set()
    # TODO: use /api/v1/events too (or instead this)
    # helps in the case when pods listener doesn't work or works too slow
    for pod_id, k8s_pod in pods.iteritems():
        updated_CS.update(update_states(
            pod_id, k8s_pod, host=k8s_pod['nodeName'], event_time=now))
    t.append(time.time())

    for cs in css:
        if cs in updated_CS:
            # pod was found in db and k8s, and k8s have info about this container
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
            cs.reason = 'Pod was stopped.'

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    t.append(time.time())
    current_app.logger.debug('Fixed pods timeline: {0}'.format(
        ['{0:.3f}'.format(t2-t1) for t1, t2 in zip(t[:-1], t[1:])]))


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
    """Checks CEPH client is installed on the node, and, if it is, then add
    appropriate flag to node's flags.
    """
    ssh, error_message = ssh_connect(hostname)
    if error_message:
        return
    return _check_ceph_via_ssh(ssh)


@celery.task(rate_limit="1/m")
def clean_deleted_drives():
    clean_drives_for_deleted_users()
    remove_drives_marked_for_deletion()


def clean_drives_for_deleted_users():
    ids = [
        item.id for item in db.session.query(PersistentDisk.id).join(
            User).filter(User.deleted == True)
    ]
    delete_persistent_drives(ids)



@celery.task(ignore_result=True)
def check_if_node_down(hostname, status):
    node = Node.query.filter_by(hostname=hostname).first()
    if node is None:
        return
    redis = ConnectionPool.get_connection()
    redis.set('node_unknown_state:'+hostname, 1)
    redis.expire('node_unknown_state:'+hostname, 180)
    ssh, error_message = ssh_connect(hostname, timeout=3)
    if error_message:
        redis.set('node_state_' + hostname, status)
        send_event('node:change', {'id': node.id})
        return
    i, o, e = ssh.exec_command('systemctl restart kubelet')
    if o.channel.recv_exit_status() != 0:
        redis.set('node_state_' + hostname, status)
        send_event('node:change', {'id': node.id})
