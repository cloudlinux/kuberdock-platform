import ipaddress
import json
import operator
import re
import requests
import subprocess
import time

from collections import OrderedDict
from datetime import datetime

from .core import ConnectionPool, db, ssh_connect
from .factory import make_celery
from .utils import update_dict, get_api_url, send_event, send_logs
from .stats import StatWrap5Min
from .kubedata.kubestat import KubeUnitResolver, KubeStat
from .models import Pod, ContainerState, User
from .settings import NODE_INSTALL_LOG_FILE, MASTER_IP, AWS
from .settings import NODE_INSTALL_TIMEOUT_SEC
from .kapi.podcollection import PodCollection


DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


celery = make_celery()


def search_image(term, url=None, page=None):
    page = page or 1
    if url is None:
        url = 'https://registry.hub.docker.com/v1/search'
    else:
        if not url.rstrip('/').endswith('v1/search'):
            url = '{0}/v1/search'.format(url.rstrip('/'))
    data = {'q': term, 'n': 10, 'page': page}
    r = requests.get(url, params=data)
    return r.text


@celery.task()
def get_container_images(term, url=None, page=None):
    return search_image(term, url, page)


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
    if namespace:
        url = get_api_url('services', namespace=namespace, use_v3=True)
    else:
        url = get_api_url('services', use_v3=True)
    r = requests.get(url)
    return r.json()


def create_service_nodelay(data, namespace=None):
    r = requests.post(get_api_url('services', use_v3=True, namespace=namespace),
                      data=json.dumps(data))
    return r.text


def delete_pod_nodelay(item, namespace=None):
    if namespace:
        url = get_api_url('pods', item, namespace=namespace,  use_v3=True)
    else:
        url = get_api_url('pods', item)
    r = requests.delete(url)
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
    r = requests.delete(get_api_url('services', item, namespace=namespace,
                                    use_v3=True))
    return r.json()


@celery.task()
def get_dockerfile(name, tag=None):
    if '/' not in name:
        return get_dockerfile_official(name, tag)
    url = 'https://registry.hub.docker.com/u/{0}/dockerfile/raw'.format(name)
    r = requests.get(url)
    return r.text


info_pattern = re.compile('^(?P<tag>\S+):\s+(?:\S+://)?(?P<url>\S+?)'
                          '(?:@(?P<commit>\S*?))?(?:\s+(?P<dir>\S+?))?$')


def get_dockerfile_official(name, tag=None):
    if not tag:
        tag = 'latest'
    info_url = ('https://github.com/docker-library/official-images/'
                'raw/master/library/{0}'.format(name))
    r_info = requests.get(info_url)
    docker_url = ''
    for line in r_info.text.splitlines():
        info_match = info_pattern.match(line)
        if info_match:
            info = info_match.groupdict()
            if info.get('tag') == tag:
                docker_url = ('https://{0}/raw/{1}{2}/Dockerfile'.format(
                    info['url'],
                    info.get('commit', 'master'),
                    '/{0}'.format(info['dir']) if info['dir'] else '',
                ))
                break
    if docker_url:
        r_docker = requests.get(docker_url)
        return r_docker.text
    return ''


def get_all_nodes():
    r = requests.get(get_api_url('nodes', use_v3=True, namespace=False))
    return r.json().get('items') or []


def get_node_by_host(host):
    r = requests.get(get_api_url('nodes', host, use_v3=True, namespace=False))
    return r.json()


def remove_node_by_host(host):
    r = requests.delete(get_api_url('nodes', host, use_v3=True, namespace=False))
    return r.json()


def add_node_to_k8s(host, kube_type):
    """
    :param host: Node hostname
    :param kube_type: Kuberdock kube type (integer id)
    :return: Error text if error else False
    """
    # TODO handle connection errors except requests.RequestException
    res = requests.post(get_api_url('nodes', use_v3=True, namespace=False),
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
def add_new_node(host, kube_type, db_node, with_testing):

    with open(NODE_INSTALL_LOG_FILE.format(host), 'w') as log_file:

        try:
            current_master_kubernetes = subprocess.check_output(
                ['rpm', '-q', 'kubernetes']).strip()
        except subprocess.CalledProcessError as e:
            mes = 'Kuberdock needs correctly installed kubernetes' \
                  ' on master. {0}'.format(e.output)
            send_logs(host, mes, log_file)
            db_node.state = 'completed'
            db.session.add(db_node)
            db.session.commit()
            return mes
        except OSError:     # no rpm
            current_master_kubernetes = 'kubernetes'

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
        sftp.put('/etc/kubernetes/kubelet_token.dat', '/kubelet_token.dat')
        sftp.put('/etc/pki/etcd/ca.crt', '/ca.crt')
        sftp.put('/etc/pki/etcd/etcd-client.crt', '/etcd-client.crt')
        sftp.put('/etc/pki/etcd/etcd-client.key', '/etcd-client.key')
        sftp.close()
        deploy_cmd = 'AWS={0} CUR_MASTER_KUBERNETES={1} MASTER_IP={2} '\
                     'FLANNEL_IFACE={3} bash /node_install.sh'
        if with_testing:
            deploy_cmd = 'WITH_TESTING=yes ' + deploy_cmd
        i, o, e = ssh.exec_command(deploy_cmd.format(AWS,
                                                     current_master_kubernetes,
                                                     MASTER_IP, node_interface))
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
    for pod in Pod.query.filter(Pod.status != 'deleted').values(
            Pod.name, Pod.id, Pod.config):
        kubes = {}
        containers = json.loads(pod[2]).get('containers', [])
        for container in containers:
            if 'kubes' in container:
                kubes[container['name']] = container['kubes']
        db_pods[pod[0]] = {'uid': pod[1], 'kubes': kubes}
    items = data.get('items')
    res = []
    for item in items:
        current_state = item['currentState']
        try:
            pod_name = item['labels']['name']
        except KeyError:
            pod_name = item['id']
        if pod_name in db_pods:
            current_state['uid'] = db_pods[pod_name]['uid']
            if 'info' in current_state:
                for name, data in current_state['info'].items():
                    if name in db_pods[pod_name]['kubes']:
                        data['kubes'] = db_pods[pod_name]['kubes'][name]
            res.append(current_state)
    return res


def parse_nodes_statuses(items):
    res = []
    if not items:
        return res
    for item in items:
        try:
            conditions = item['status']['conditions']
            for cond in conditions:
                res.append(cond.get('type', ''))
        except KeyError:
            res.append('')
    return res


@celery.task()
def check_events():
    redis = ConnectionPool.get_connection()

    lock = redis.get('events_lock')
    if not lock:
        redis.setex('events_lock', 30 + 1, 'true')
    else:
        return

    nodes_list = redis.get('cached_nodes')
    if not nodes_list:
        nodes_list = get_all_nodes()
        nodes_list = parse_nodes_statuses(nodes_list)
        redis.set('cached_nodes', json.dumps(nodes_list))
        send_event('pull_nodes_state', 'ping')
    else:
        temp = get_all_nodes()
        temp = parse_nodes_statuses(temp)
        if temp != json.loads(nodes_list):
            redis.set('cached_nodes', json.dumps(temp))
            send_event('pull_nodes_state', 'ping')

    pods_list = redis.get('cached_pods')
    if not pods_list:
        pods_list = requests.get(get_api_url('pods')).json()
        pods_list = parse_pods_statuses(pods_list)
        redis.set('cached_pods', json.dumps(pods_list))
        send_event('pull_pods_state', 'ping')
    else:
        pods_list = json.loads(pods_list)
        temp = requests.get(get_api_url('pods')).json()
        temp = parse_pods_statuses(temp)
        if temp != pods_list:
            pods_list = temp
            redis.set('cached_pods', json.dumps(pods_list))
            send_event('pull_pods_state', 'ping')

    for pod in pods_list:
        if 'info' in pod:
            for container_name, container_data in pod['info'].items():
                kubes = container_data.get('kubes', 1)
                for s in container_data['state'].values():
                    start = s.get('startedAt')
                    if start is None:
                        continue
                    start = datetime.strptime(start, DATETIME_FORMAT)
                    end = s.get('finishedAt')
                    if end is not None:
                        end = datetime.strptime(end, DATETIME_FORMAT)
                    add_container_state(pod['uid'], container_name, kubes,
                                        start, end)

    cs1 = db.aliased(ContainerState, name='cs1')
    cs2 = db.aliased(ContainerState, name='cs2')
    cs_query = db.session.query(cs1, cs2.start_time).join(
        cs2, db.and_(cs1.pod_id == cs2.pod_id,
                     cs1.container_name == cs2.container_name,
                     cs1.kubes == cs2.kubes)
        ).filter(db.and_(cs1.start_time < cs2.start_time,
                         db.or_(cs1.end_time > cs2.start_time,
                                cs1.end_time.is_(None)))
                 ).order_by(cs1.start_time, cs2.start_time)
    prev_cs = None
    for cs1_obj, cs2_start_time in cs_query:
        if cs1_obj is not prev_cs:
            cs1_obj.end_time = cs2_start_time
        prev_cs = cs1_obj

    css = ContainerState.query.filter_by(end_time=None)
    pod_ids = [pod['uid'] for pod in pods_list]
    now = datetime.now().replace(microsecond=0)

    for cs in css:
        if cs.pod_id not in pod_ids:
            cs.end_time = now

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    redis.delete('events_lock')


def add_container_state(pod, container, kubes, start, end):
    cs = ContainerState.query.filter_by(pod_id=pod, container_name=container,
                                        kubes=kubes, start_time=start).first()
    if cs:
        cs.end_time = end
    else:
        cs = ContainerState(pod_id=pod, container_name=container,
                            kubes=kubes, start_time=start, end_time=end)
        db.session.add(cs)


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
        pod_collection.update(pod['id'], {'command': 'stop'})
        public_ip = (
            pod.get('public_ip') or                           # stopped pod
            pod.get('labels', {}).get('kuberdock-public-ip')  # running pod
        )
        if public_ip is not None:
            pod_collection._free_ip(public_ip)


@db.event.listens_for(User.active, 'set')
def user_lock_event(target, value, oldvalue, initiator):
    if value != oldvalue and not value:
        user_lock_task.delay(target)
