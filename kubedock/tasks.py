import json
import requests
import time
import operator
from collections import OrderedDict

from .settings import DEBUG, NODE_SSH_AUTH
from .api.stream import send_event
from .core import ConnectionPool, db, ssh_connect, fast_cmd
from .factory import make_celery
from .utils import update_dict
from .stats import StatWrap5Min
from .kubedata.kubestat import KubeUnitResolver, KubeStat

from .utils import get_api_url

celery = make_celery()


def search_image(term, url=None):
    if url is None:
        url = 'https://registry.hub.docker.com/v1/search'
    else:
        if not url.rstrip('/').endswith('v1/search'):
            url = '{0}/v1/search'.format(url.rstrip('/'))
    data = {'q': term}
    r = requests.get(url, params=data)
    return r.text


@celery.task()
def get_container_images(term, url=None):
    return search_image(term, url)


@celery.task()
def get_pods(pod_id=None):
    url = get_api_url('pods')
    if pod_id is not None:
        url = get_api_url('pods', pod_id)
    r = requests.get(url)
    return json.loads(r.text)


def get_pods_nodelay(pod_id=None):
    url = get_api_url('pods')
    if pod_id is not None:
        url = get_api_url('pods', pod_id)
    r = requests.get(url)
    return json.loads(r.text)


@celery.task()
def get_replicas():
    r = requests.get(get_api_url('replicationControllers'))
    return json.loads(r.text)


def get_replicas_nodelay():
    r = requests.get(get_api_url('replicationControllers'))
    return json.loads(r.text)


@celery.task()
def get_services():
    r = requests.get(get_api_url('services'))
    return json.loads(r.text)


def get_services_nodelay():
    r = requests.get(get_api_url('services'))
    return json.loads(r.text)


@celery.task()
def create_containers(data):
    kind = data['kind'][0].lower() + data['kind'][1:] + 's'
    r = requests.post(get_api_url(kind), data=json.dumps(data))
    return r.text


def create_containers_nodelay(data):
    kind = data['kind'][0].lower() + data['kind'][1:] + 's'
    r = requests.post(get_api_url(kind), data=json.dumps(data))
    return r.text


@celery.task()
def create_service(data):
    r = requests.post(get_api_url('services'), data=json.dumps(data))
    return r.text


def create_service_nodelay(data):
    r = requests.post(get_api_url('services'), data=json.dumps(data))
    return r.text


@celery.task()
def delete_pod(item):
    r = requests.delete(get_api_url('pods', item))
    return json.loads(r.text)


def delete_pod_nodelay(item):
    r = requests.delete(get_api_url('pods', item))
    return json.loads(r.text)


@celery.task()
def delete_replica(item):
    r = requests.delete(get_api_url('replicationControllers', item))
    return json.loads(r.text)


def delete_replica_nodelay(item):
    r = requests.delete(get_api_url('replicationControllers', item))
    return json.loads(r.text)


@celery.task()
def update_replica(item, diff):
    url = get_api_url('replicationControllers', item)
    r = requests.get(url)
    data = json.loads(r.text, object_pairs_hook=OrderedDict)
    update_dict(data, diff)
    headers = {'Content-Type': 'application/json'}
    r = requests.put(url, data=json.dumps(data), headers=headers)
    return json.loads(r.text)


def update_replica_nodelay(item, diff):
    url = get_api_url('replicationControllers', item)
    r = requests.get(url)
    data = json.loads(r.text, object_pairs_hook=OrderedDict)
    update_dict(data, diff)
    headers = {'Content-Type': 'application/json'}
    r = requests.put(url, data=json.dumps(data), headers=headers)
    return json.loads(r.text)


@celery.task()
def delete_service(item):
    r = requests.delete(get_api_url('services', item))
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


def get_dockerfile_nodelay(data):
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


def compute_capacity(cpu_count, cpu_mhz, mem_total):
    CPU_SCALE_FACTOR = 0.2
    MEM_PART_FACTOR = 1.0
    return {
        'cpu': int(round(cpu_count * cpu_mhz * CPU_SCALE_FACTOR)),
        'memory': int(round(mem_total * MEM_PART_FACTOR))
    }


@celery.task()
def add_new_node(host):
    if DEBUG:
        send_event('install_logs',
                   'Connecting to {0} with ssh with user root ...'
                   .format(host))
    else:
        send_event('install_logs',
                   'Connecting to {0} with ssh with user = root and '
                   'ssh_key_filename = {1} ...'.format(host, NODE_SSH_AUTH))
    ssh, error_message = ssh_connect(host)
    if error_message:
        send_event('install_logs', error_message)
        return error_message

    sftp = ssh.open_sftp()
    sftp.put('kub_install.sh', '/kub_install.sh')
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
        ok, data = fast_cmd(ssh, 'lscpu | grep ^CPU\(s\) | cut -f 2 -d\:')
        if not ok:
            send_event('install_logs', "Can't retrieve cpu count using lscpu")
            ssh.close()
            return data
        cpu_count = int(data.strip())

        # TODO this MHz is not true
        ok, data = fast_cmd(ssh, 'lscpu | grep ^CPU\ MHz | cut -f 2 -d\:')
        if not ok:
            send_event('install_logs', "Can't retrieve cpu MHz using lscpu")
            ssh.close()
            return data
        cpu_mhz = float(data.strip())

        ok, data = fast_cmd(ssh, 'cat /proc/meminfo | grep MemTotal |'
                                 ' cut -f 2 -d\: | cut -f 1 -dk')
        if not ok:
            send_event('install_logs', "Can't retrieve MemTotal using /proc")
            ssh.close()
            return data
        mem_total = int(data.strip()) * 1024  # was in Kb

        cap = compute_capacity(cpu_count, cpu_mhz, mem_total)

        res = requests.post(get_api_url('nodes'),
                            json={'id': host,
                                  'apiVersion': 'v1beta1',
                                  'resources': {
                                      'capacity': cap
                                  },
                                  'labels': {
                                      'kuberdock-node-hostname': host
                                  }
                            }).json()
        send_event('install_logs', 'Adding Node completed successful.')
        send_event('install_logs', '===================================')
    ssh.close()
    return res


def parse_pods_statuses(data):
    items = data.get('items')
    res = []
    if not items:
        return res
    for item in items:
        current_state = item.get('currentState')
        if not current_state:
            res.append({})
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
        temp = requests.get(get_api_url('pods')).json()
        temp = parse_pods_statuses(temp)
        if temp != json.loads(pods_list):
            redis.set('cached_pods', json.dumps(temp))
            send_event('pull_pods_state', 'ping')

    redis.delete('events_lock')


@celery.task()
def pull_hourly_stats():
    data = KubeStat(resolution=300).stats(KubeUnitResolver().all())
    time_windows = set(map(operator.itemgetter('time_window'), data))
    rv = db.session.query(StatWrap5Min).filter(
        StatWrap5Min.time_window.in_(time_windows))
    existing_windows = set(map((lambda x: x.time_window), rv))
    for entry in data:
        if entry['time_window'] in existing_windows:
            continue
        db.session.add(StatWrap5Min(**entry))
    db.session.commit()
