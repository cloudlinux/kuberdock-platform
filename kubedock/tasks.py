import ipaddress
import json
import operator
import re
import requests
import subprocess
import time
import urlparse

from collections import OrderedDict
from datetime import datetime, timedelta
from distutils.util import strtobool

# requests .json() errors handling workaround.
# requests module uses simplejson as json by default
# that raises JSONDecodeError if .json() method fails
# but if simplejson is not available requests uses json module
# that raises ValueError in this case
try:
    from simplejson import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

from .core import ConnectionPool, db, ssh_connect
from .factory import make_celery
from .utils import (
    update_dict, get_api_url, send_event, send_logs, POD_STATUSES)
from .stats import StatWrap5Min
from .kubedata.kubestat import KubeUnitResolver, KubeStat
from .models import Pod, ContainerState, User
from .nodes.models import NodeMissedAction
from .settings import NODE_INSTALL_LOG_FILE, MASTER_IP, AWS, \
                        NODE_INSTALL_TIMEOUT_SEC, PORTS_TO_RESTRICT
from .kapi.podcollection import PodCollection

celery = make_celery()


def search_image(term, url='https://registry.hub.docker.com', page=1, page_size=10):
    url = urlparse.urlsplit(url)._replace(path='/v2/search/repositories').geturl()
    params = {'query': term, 'page_size': page_size, 'page': page}
    return requests.get(url, params=params).json()


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


def get_node_by_host(host):
    r = requests.get(get_api_url('nodes', host, namespace=False))
    return r.json()


def remove_node_by_host(host):
    r = requests.delete(get_api_url('nodes', host, namespace=False))
    return r.json()


def add_node_to_k8s(host, kube_type):
    """
    :param host: Node hostname
    :param kube_type: Kuberdock kube type (integer id)
    :return: Error text if error else False
    """
    # TODO handle connection errors except requests.RequestException
    res = requests.post(get_api_url('nodes', namespace=False),
                        json={
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
                        })
    return res.text if not res.ok else False


@celery.task()
def add_new_node(host, kube_type, db_node,
                 with_testing=False, nodes=None, redeploy=False):

    with open(NODE_INSTALL_LOG_FILE.format(host), 'w') as log_file:
        try:
            current_master_kubernetes = subprocess.check_output(
                ['rpm', '-q', 'kubernetes-master']).strip()
        except subprocess.CalledProcessError as e:
            mes = 'Kuberdock needs correctly installed kubernetes' \
                  ' on master. {0}'.format(e.output)
            send_logs(host, mes, log_file)
            db_node.state = 'completed'
            db.session.add(db_node)
            db.session.commit()
            return mes
        except OSError:     # no rpm
            current_master_kubernetes = 'kubernetes-master'
        current_master_kubernetes = current_master_kubernetes.replace(
            'master', 'node')

        if redeploy:
            send_logs(host, 'Redeploy.', log_file)
            send_logs(host, 'Remove node {0} from kubernetes...'.format(host),
                      log_file)
            result = remove_node_by_host(host)
            send_logs(host, json.dumps(result, indent=2), log_file)

        send_logs(host, 'Current kubernetes package on master is'
                        ' "{0}". Will install same package.'
                        .format(current_master_kubernetes), log_file)

        send_logs(host, 'Connecting to {0} with ssh with user "root" ...'
                  .format(host), log_file)
        ssh, error_message = ssh_connect(host)
        if error_message:
            send_logs(host, error_message, log_file)
            db_node.state = 'completed'
            db.session.add(db_node)
            db.session.commit()
            return error_message

        i, o, e = ssh.exec_command('ip -o -4 address show')
        node_interface = get_node_interface(o.read())
        sftp = ssh.open_sftp()
        sftp.put('node_install.sh', '/node_install.sh')
        sftp.put('pd.sh', '/pd.sh')
        sftp.put('/etc/kubernetes/configfile_for_nodes', '/configfile')
        sftp.put('/etc/pki/etcd/ca.crt', '/ca.crt')
        sftp.put('/etc/pki/etcd/etcd-client.crt', '/etcd-client.crt')
        sftp.put('/etc/pki/etcd/etcd-client.key', '/etcd-client.key')
        sftp.close()
        deploy_cmd = 'AWS={0} CUR_MASTER_KUBERNETES={1} MASTER_IP={2} '\
                     'FLANNEL_IFACE={3} bash /node_install.sh{4}'
        # we pass ports and hosts to let the node know which hosts are allowed
        data_for_firewall = reduce(
            (lambda x, y: x + ' {0}'.format(','.join(y))),
                [map(str, l) for l in PORTS_TO_RESTRICT, nodes if l], '')
        if with_testing:
            deploy_cmd = 'WITH_TESTING=yes ' + deploy_cmd
        i, o, e = ssh.exec_command(deploy_cmd.format(AWS,
                                                     current_master_kubernetes,
                                                     MASTER_IP, node_interface,
                                                     data_for_firewall))
        s_time = time.time()
        while not o.channel.exit_status_ready():
            if o.channel.recv_ready():
                for line in o.channel.recv(1024).split('\n'):
                    send_logs(host, line, log_file)
            if (time.time() - s_time) > NODE_INSTALL_TIMEOUT_SEC:
                err = 'Timeout during install. Installation has failed.'
                send_logs(host, err, log_file)
                ssh.exec_command('rm /node_install.sh')
                ssh.close()
                db_node.state = 'completed'
                db.session.add(db_node)
                db.session.commit()
                return err
            time.sleep(0.2)
        s = o.channel.recv_exit_status()
        ssh.exec_command('rm /node_install.sh')
        if s != 0:
            res = 'Installation script error. Exit status: {0}. Error: {1}'\
                .format(s, e.read())
            send_logs(host, res, log_file)
        else:
            err = add_node_to_k8s(host, kube_type)
            if err:
                send_logs(host, 'ERROR adding node.', log_file)
                send_logs(host, err, log_file)
            else:
                send_logs(host, 'Adding Node completed successful.',
                          log_file)
                send_logs(host, '===================================', log_file)
        ssh.close()
        db_node.state = 'completed'
        db.session.add(db_node)
        db.session.commit()


def parse_pods_statuses(data):
    db_pods = {}
    for pod_id, pod_config in Pod.query.filter(
            Pod.status != 'deleted').values(Pod.id, Pod.config):
        kubes = {}
        containers = json.loads(pod_config).get('containers', [])
        for container in containers:
            if 'kubes' in container:
                kubes[container['name']] = container['kubes']
        db_pods[pod_id] = {'kubes': kubes}
    items = data.get('items')
    res = []
    for item in items:
        current_state = item['status']
        try:
            pod_id = item['metadata']['labels']['kuberdock-pod-uid']
        except KeyError:
            pod_id = item['metadata']['name']   # don't match our needs at all
        if pod_id in db_pods:
            current_state['uid'] = pod_id
            if 'containerStatuses' in current_state:
                for container in current_state['containerStatuses']:
                    if container['name'] in db_pods[pod_id]['kubes']:
                        container['kubes'] = db_pods[pod_id]['kubes'][container['name']]
            res.append(current_state)
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
        NodeMissedAction.time_stamp > (datetime.now()-timedelta(minutes=35))
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


@celery.task(ignore_result=True)
def user_lock_task(user):
    pod_collection = PodCollection(user)
    for pod in pod_collection.get(as_json=False):
        if pod.get('status') != POD_STATUSES.stopped:
            pod_collection.update(pod['id'], {'command': 'stop'})
        public_ip = (
            pod.get('public_ip') or                           # stopped pod
            pod.get('labels', {}).get('kuberdock-public-ip')  # running pod
        )
        if public_ip is not None:
            pod_collection._free_ip(public_ip)


@db.event.listens_for(User.active, 'set')
def user_lock_event(target, value, oldvalue, initiator):
    if not isinstance(value, bool):
        value = bool(strtobool(value))
    if value != oldvalue and not value:
        user_lock_task.delay(target)
        target.logout()


@db.event.listens_for(User.suspended, 'set')
def user_suspend_event(target, value, oldvalue, initiator):
    if not isinstance(value, bool):
        value = bool(strtobool(value))
    if value != oldvalue and value is True:
        user_lock_task.delay(target)


@celery.task()
def fix_pods_timeline():
    css = ContainerState.query.filter(ContainerState.end_time.is_(None))
    pods_list = requests.get(get_api_url('pods', namespace=False)).json()
    pods_list = parse_pods_statuses(pods_list)
    pod_ids = [pod['uid'] for pod in pods_list]
    now = datetime.utcnow().replace(microsecond=0)

    for cs in css:
        cs_next = ContainerState.query.filter(
            ContainerState.pod_id == cs.pod_id,
            ContainerState.container_name == cs.container_name,
            ContainerState.start_time > cs.start_time,
        ).order_by(
            ContainerState.start_time,
        ).first()
        if cs_next:
            cs.end_time = cs_next.start_time
        elif cs.pod_id not in pod_ids:
            cs.end_time = now

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


@celery.task()
def fix_pods_timeline_heavy():
    """
    Fix time lines overlapping
    This task should not be performed during normal operation
    """
    redis = ConnectionPool.get_connection()

    if redis.get('fix_pods_timeline_heavy'):
        return

    redis.setex('fix_pods_timeline_heavy', 3600, 'true')

    t0 = datetime.now()

    cs1 = db.aliased(ContainerState, name='cs1')
    cs2 = db.aliased(ContainerState, name='cs2')
    cs_query = db.session.query(cs1, cs2.start_time).join(
        cs2, db.and_(cs1.pod_id == cs2.pod_id,
                     cs1.container_name == cs2.container_name)
        ).filter(db.and_(cs1.start_time < cs2.start_time,
                         db.or_(cs1.end_time > cs2.start_time,
                                cs1.end_time.is_(None)))
                 ).order_by(cs1.pod_id, cs1.container_name,
                            db.desc(cs1.start_time), cs2.start_time)

    prev_cs = None
    for cs1_obj, cs2_start_time in cs_query:
        if cs1_obj is not prev_cs:
            cs1_obj.end_time = cs2_start_time
        prev_cs = cs1_obj

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    print('fix_pods_timeline_heavy: {0}'.format(datetime.now() - t0))

    redis.delete('fix_pods_timeline_heavy')
