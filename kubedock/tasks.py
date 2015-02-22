import json
import requests
import paramiko
import time
import socket
import operator
from collections import OrderedDict
from paramiko import ssh_exception

from .settings import DEBUG, NODE_SSH_AUTH
from .api.stream import send_event
from .core import ConnectionPool, db, ssh_connect
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


@celery.task()
def get_replicas():
    r = requests.get(get_api_url('replicationControllers'))
    return json.loads(r.text)


@celery.task()
def get_services():
    r = requests.get(get_api_url('services'))
    return json.loads(r.text)


@celery.task()
def create_containers(data):
    kind = data['kind'][0].lower() + data['kind'][1:] + 's'
    r = requests.post(get_api_url(kind), data=json.dumps(data))
    return r.text


@celery.task()
def create_service(data):
    r = requests.post(get_api_url('services'), data=json.dumps(data))
    return r.text


@celery.task()
def delete_pod(item):
    r = requests.delete(get_api_url('pods', item))
    return json.loads(r.text)


@celery.task()
def delete_replica(item):
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


@celery.task()
def delete_service(item):
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
def add_new_node(host):
    if DEBUG:
        send_event('install_logs',
                   'Connecting to {0} with ssh with user = root and '
                   'password = {1} ...'.format(host, NODE_SSH_AUTH))
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
        if (time.time() - s_time) > 5*60:   # 5 min timeout
            send_event('install_logs',
                       'Timeout during install. Installation has failed.')
            ssh.exec_command('rm /kub_install.sh')
            ssh.close()
            return json.dumps({
                'status': 'error',
                'data': 'Timeout during install. Installation has failed.'})
        time.sleep(0.2)
    s = o.channel.recv_exit_status()
    if s != 0:
        message = 'Installation script error. Exit status: {0}. ' \
                  'Error: {1}'.format(s, e.read())
        send_event('install_logs', message)
        res = json.dumps({'status': 'error', 'data': message})
    else:
        res = requests.post(get_api_url('nodes'),
                            json={'id': host, 'apiVersion': 'v1beta1'}).json()
        send_event('install_logs', 'Adding Node completed successful.')
        send_event('install_logs', '===================================')
    ssh.exec_command('rm /kub_install.sh')
    ssh.close()
    return res


@celery.task()
def check_events():
    redis = ConnectionPool.get_connection()

    lock = redis.get('events_lock')
    if not lock:
        redis.setex('events_lock', 30 + 1, 'true')
    else:
        return

    ml = redis.get('cached_nodes')
    if not ml:
        ml = get_all_nodes()
        redis.set('cached_nodes', json.dumps(ml))
        send_event('pull_nodes_state', 'ping')
    else:
        temp = get_all_nodes()
        if temp != json.loads(ml):
            redis.set('cached_nodes', json.dumps(temp))
            send_event('pull_nodes_state', 'ping')

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


def get_node_log(ip, log_size=0):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if DEBUG:
            ssh.connect(hostname=ip, username='root',
                        password=NODE_SSH_AUTH, timeout=10)
        else:
            ssh.connect(hostname=ip, username='root',
                        key_filename=NODE_SSH_AUTH, timeout=10)
    except (socket.timeout, socket.error,
            paramiko.ssh_exception.AuthenticationException):
        return -1, []
    sftp = ssh.open_sftp()
    log_stat = sftp.stat('/var/log/messages')
    log_lines = []
    if log_size > 0:
        if log_stat.st_size != log_size:
            log_file = sftp.open('/var/log/messages')
            if log_stat.st_size > log_size:
                log_file.seek(log_size)
            log_lines.extend(log_file.readlines())
    sftp.close()
    ssh.close()
    return log_stat.st_size, log_lines


@celery.task()
def get_nodes_logs():
    redis = ConnectionPool.get_connection()

    nodes_logs_timestamp = redis.get('nodes_logs_timestamp')
    nodes_logs_timestamp = (0. if nodes_logs_timestamp is None
                              else float(nodes_logs_timestamp))
    now = time.time()

    if now - nodes_logs_timestamp > 30:
        redis.delete('nodes_logged')
        redis.delete('nodes_log_size')

    redis.setex('nodes_logs_timestamp', 30, now)

    all_nodes = get_all_nodes()
    nodes_logged = redis.lrange('nodes_logged', 0, -1)

    for node in all_nodes:
        node_id = node['id']

        if node['id'] in nodes_logged:
            continue

        log_size = redis.hget('nodes_log_size', node_id)
        log_size = 0 if log_size is None else int(log_size)
        log_size, log_lines = get_node_log(node_id, log_size)
        redis.hset('nodes_log_size', node_id, log_size)
        redis.rpush('nodes_logged', node_id)
        event_name = 'node-log-{0}'.format(node_id)

        for line in log_lines:
            send_event(event_name, line)
        break
    else:
        redis.delete('nodes_logged')
