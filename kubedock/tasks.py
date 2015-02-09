from collections import OrderedDict
import json
import requests
import paramiko
from paramiko import ssh_exception
import time
import socket
from .settings import DEBUG, MINION_SSH_AUTH
from .api.stream import send_event
from .core import ConnectionPool, db
from .factory import make_celery
from .utils import update_dict
from .stats import StatWrap5Min
from .kubedata.kubestat import KubeUnitResolver, KubeStat
import operator

celery = make_celery()

@celery.task()
def get_container_images(term, url=None):
    if url is None:
        url = 'https://registry.hub.docker.com/v1/search'
    data = {'q': term}
    r = requests.get(url, params=data)
    return r.text

@celery.task()
def get_pods(pod_id=None):
    url = 'http://localhost:8080/api/v1beta1/pods'
    if pod_id is not None:
        url = 'http://localhost:8080/api/v1beta1/pods/%s' % (pod_id,)
    r = requests.get(url)
    return json.loads(r.text)

@celery.task()
def get_replicas():
    r = requests.get('http://localhost:8080/api/v1beta1/replicationControllers')
    return json.loads(r.text)

@celery.task()
def get_services():
    r = requests.get('http://localhost:8080/api/v1beta1/services')
    return json.loads(r.text)

@celery.task()
def create_containers(data):
    kind = data['kind'][0].lower() + data['kind'][1:] + 's'
    r = requests.post('http://localhost:8080/api/v1beta1/%s' % (kind,),
                      data=json.dumps(data))
    return r.text

@celery.task()
def create_service(data):
    r = requests.post('http://localhost:8080/api/v1beta1/services',
                      data=json.dumps(data))
    return r.text

@celery.task()
def delete_pod(item):
    r = requests.delete('http://localhost:8080/api/v1beta1/pods/'+item)
    return json.loads(r.text)

@celery.task()
def delete_replica(item):
    r = requests.delete('http://localhost:8080/api/v1beta1/replicationControllers/'+item)
    return json.loads(r.text)

@celery.task()
def update_replica(item, diff):
    url = 'http://localhost:8080/api/v1beta1/replicationControllers/' + item
    r = requests.get(url)
    data = json.loads(r.text, object_pairs_hook=OrderedDict)
    update_dict(data, diff)
    headers = {'Content-Type': 'application/json'}
    r = requests.put(url, data=json.dumps(data), headers=headers)
    return json.loads(r.text)

@celery.task()
def delete_service(item):
    r = requests.delete('http://localhost:8080/api/v1beta1/services/'+item)
    return json.loads(r.text)
    
@celery.task()
def get_dockerfile(data):
    url = 'https://registry.hub.docker.com/u/%s/dockerfile/raw' % (data.strip('/'),)
    r = requests.get(url)
    return r.text


def get_all_minions():
    r = requests.get('http://localhost:8080/api/v1beta1/nodes')
    return r.json()['items']


def get_minion_by_host(host):
    r = requests.get('http://localhost:8080/api/v1beta1/nodes/' + host)
    return r.json()


def remove_minion_by_host(host):
    r = requests.delete('http://localhost:8080/api/v1beta1/nodes/' + host)
    return r.json()


@celery.task()
def add_new_minion(host):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if DEBUG:
            send_event('install_logs', 'Connecting to {0} with ssh with user = root and password = {1} ...'
                       .format(host, MINION_SSH_AUTH))
            ssh.connect(hostname=host, username='root', password=MINION_SSH_AUTH, timeout=10)
        else:
            send_event('install_logs', 'Connecting to {0} with ssh with user = root and ssh_key_filename = {1} ...'
                       .format(host, MINION_SSH_AUTH))
            ssh.connect(hostname=host, username='root', key_filename=MINION_SSH_AUTH, timeout=10)    # not tested
    except ssh_exception.AuthenticationException as e:
        send_event('install_logs', '{0} Check hostname, your credentials, and try again'.format(e))
        return 'Authentication failed'
    except socket.timeout:
        send_event('install_logs', 'Connection timeout. Check hostname and try again')
        return 'Timeout'
    except socket.error as e:
        send_event('install_logs', '{0}. Check hostname, your credentials, and try again'.format(e))
        return 'Connection error'

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
            send_event('install_logs', 'Timeout during install. Installation has failed.')
            ssh.exec_command('rm /kub_install.sh')
            ssh.close()
            return json.dumps({'status': 'error', 'data': 'Timeout during install. Installation has failed.'})
        time.sleep(0.2)
    s = o.channel.recv_exit_status()
    if s != 0:
        message = 'Installation script error. Exit status: {0}. Error: {1}'.format(s, e.read())
        send_event('install_logs', message)
        res = json.dumps({'status': 'error', 'data': message})
    else:
        res = requests.post('http://localhost:8080/api/v1beta1/nodes/', json={'id': host, 'apiVersion': 'v1beta1'}).json()
        send_event('install_logs', 'Adding minion completed successful.')
        send_event('install_logs', '===================================')
    ssh.exec_command('rm /kub_install.sh')
    ssh.close()
    return res


@celery.task()
def check_events():
    redis = ConnectionPool.get_connection()

    lock = redis.get('events_lock')
    if not lock:
        redis.setex('events_lock', 30+1, 'true')
    else:
        return

    ml = redis.get('cached_minions')
    if not ml:
        ml = get_all_minions()
        redis.set('cached_minions', json.dumps(ml))
        send_event('ping', 'ping')
    else:
        temp = get_all_minions()
        if temp != json.loads(ml):
            redis.set('cached_minions', json.dumps(temp))
            send_event('ping', 'ping')

    redis.delete('events_lock')
    
@celery.task()
def pull_hourly_stats():
    data = KubeStat(resolution=300).stats(KubeUnitResolver().all())
    time_windows = set(map(operator.itemgetter('time_window'), data))
    rv = db.session.query(StatWrap5Min).filter(StatWrap5Min.time_window.in_(time_windows))
    existing_windows = set(map((lambda x: x.time_window), rv))
    for entry in data:
        if entry['time_window'] in existing_windows:
            continue
        db.session.add(StatWrap5Min(**entry))
    db.session.commit()


def get_minion_log(ip, log_size=0):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if DEBUG:
            ssh.connect(hostname=ip, username='root',
                        password=MINION_SSH_AUTH, timeout=10)
        else:
            ssh.connect(hostname=ip, username='root',
                        key_filename=MINION_SSH_AUTH, timeout=10)
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
def get_minions_logs():
    redis = ConnectionPool.get_connection()

    minions_logs_timestamp = redis.get('minions_logs_timestamp')
    minions_logs_timestamp = (0. if minions_logs_timestamp is None
                              else float(minions_logs_timestamp))
    now = time.time()

    if now - minions_logs_timestamp > 30:
        redis.delete('minions_logged')
        redis.delete('minions_log_size')

    redis.setex('minions_logs_timestamp', 30, now)

    all_minions = get_all_minions()
    minions_logged = redis.lrange('minions_logged', 0, -1)

    for minion in all_minions:
        minion_id = minion['id']

        if minion['id'] in minions_logged:
            continue

        log_size = redis.hget('minions_log_size', minion_id)
        log_size = 0 if log_size is None else int(log_size)
        log_size, log_lines = get_minion_log(minion_id, log_size)
        redis.hset('minions_log_size', minion_id, log_size)
        redis.rpush('minions_logged', minion_id)
        event_name = 'minion-log-{0}'.format(minion_id)

        for line in log_lines:
            send_event(event_name, line)
        break
    else:
        redis.delete('minions_logged')
