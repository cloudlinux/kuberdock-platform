import json
import requests
import time
import operator
import sys
from collections import OrderedDict
from datetime import datetime

from .api.stream import send_event
from .core import ConnectionPool, db, ssh_connect
from .factory import make_celery
from .utils import update_dict
from .stats import StatWrap5Min
from .kubedata.kubestat import KubeUnitResolver, KubeStat
from .models import Pod, ContainerState
from .settings import KUBE_API_VERSION

from .utils import get_api_url


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
    # Gevent ssl incompatible with python 2.7.9
    # https://github.com/gevent/gevent/issues/477
    if sys.version_info[2] > 8:
        url = url.replace('https', 'http')
    r = requests.get(url, params=data)
    return r.text


@celery.task()
def get_container_images(term, url=None, page=None):
    return search_image(term, url, page)


def get_pods_nodelay(pod_id=None):
    url = get_api_url('pods')
    if pod_id is not None:
        url = get_api_url('pods', pod_id)
    r = requests.get(url)
    return json.loads(r.text)


def get_replicas_nodelay():
    r = requests.get(get_api_url('replicationControllers'))
    return json.loads(r.text)


def get_services_nodelay():
    r = requests.get(get_api_url('services'))
    return json.loads(r.text)


def create_containers_nodelay(data):
    kind = data['kind'][0].lower() + data['kind'][1:] + 's'
    r = requests.post(get_api_url(kind), data=json.dumps(data))
    return r.text


def create_service_nodelay(data):
    url = get_api_url('services').replace('v1beta2', 'v1beta3/namespaces/default')
    r = requests.post(url, data=json.dumps(data))
    # r = requests.post(get_api_url('services'), data=json.dumps(data))
    return r.text


def delete_pod_nodelay(item):
    r = requests.delete(get_api_url('pods', item))
    return json.loads(r.text)


def delete_replica_nodelay(item):
    r = requests.delete(get_api_url('replicationControllers', item))
    return json.loads(r.text)


def update_replica_nodelay(item, diff):
    url = get_api_url('replicationControllers', item)
    r = requests.get(url)
    data = json.loads(r.text, object_pairs_hook=OrderedDict)
    update_dict(data, diff)
    headers = {'Content-Type': 'application/json'}
    r = requests.put(url, data=json.dumps(data), headers=headers)
    return json.loads(r.text)


def delete_service_nodelay(item):
    r = requests.delete(get_api_url('services', item))
    return json.loads(r.text)


@celery.task()
def get_dockerfile(data):
    url = 'https://registry.hub.docker.com/u/{0}/dockerfile/raw'.format(
        data.strip('/'))
    r = requests.get(url)
    return r.text


def get_all_nodes():
    r = requests.get(get_api_url('nodes'))
    return r.json().get('items') or []


def get_node_by_host(host):
    r = requests.get(get_api_url('nodes', host))
    return r.json()


def remove_node_by_host(host):
    r = requests.delete(get_api_url('nodes', host))
    return r.json()


@celery.task()
def add_new_node(host, kube_type):
    send_event('install_logs',
               'Connecting to {0} with ssh with user "root" ...'
               .format(host))
    ssh, error_message = ssh_connect(host)
    if error_message:
        send_event('install_logs', error_message)
        return error_message

    sftp = ssh.open_sftp()
    sftp.put('kub_install.sh', '/kub_install.sh')
    sftp.put('/etc/kubernetes/kubelet_token.dat', '/kubelet_token.dat')
    sftp.put('/etc/pki/etcd/ca.crt', '/ca.crt')
    sftp.put('/etc/pki/etcd/etcd-client.crt', '/etcd-client.crt')
    sftp.put('/etc/pki/etcd/etcd-client.key', '/etcd-client.key')
    sftp.close()
    i, o, e = ssh.exec_command('bash /kub_install.sh')
    s_time = time.time()
    while not o.channel.exit_status_ready():
        if o.channel.recv_ready():
            for line in o.channel.recv(1024).split('\n'):
                send_event('install_logs', line)
        if (time.time() - s_time) > 15*60:   # 15 min timeout
            err = 'Timeout during install. Installation has failed.'
            send_event('install_logs', err)
            ssh.exec_command('rm /kub_install.sh')
            ssh.close()
            return err
        time.sleep(0.2)
    s = o.channel.recv_exit_status()
    ssh.exec_command('rm /kub_install.sh')
    if s != 0:
        res = 'Installation script error. Exit status: {0}. Error: {1}'\
            .format(s, e.read())
        send_event('install_logs', res)
    else:
        res = requests.post(get_api_url('nodes'),
                            json={'id': host,
                                  'apiVersion': KUBE_API_VERSION,
                                  'externalID': host,
                                  'labels': {
                                      'kuberdock-node-hostname': host,
                                      'kuberdock-kube-type': 'type_' +
                                                             str(kube_type)
                                  }
                            })
        if not res.ok:
            send_event('install_logs', 'ERROR adding node.')
            send_event('install_logs', res.text)
        else:
            send_event('install_logs', 'Adding Node completed successful.')
            send_event('install_logs', '===================================')
    ssh.close()
    return res.json()


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
                status = cond['status']
                res.append(status)
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
