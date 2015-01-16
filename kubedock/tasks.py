import json
import requests
import paramiko
from .settings import DEBUG, MINION_SSH_AUTH
from .api.sse import send_event
from .core import ConnectionPool
from .factory import make_celery
from celery.exceptions import TimeoutError

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
def delete_service(item):
    r = requests.delete('http://localhost:8080/api/v1beta1/services/'+item)
    return json.loads(r.text)
    
@celery.task()
def get_dockerfile(data):
    url = 'https://registry.hub.docker.com/u/%s/dockerfile/raw' % (data.strip('/'),)
    r = requests.get(url)
    return r.text


@celery.task()
def get_all_minions():
    r = requests.get('http://localhost:8080/api/v1beta1/minions')
    return r.json()


@celery.task()
def get_minion_by_ip(ip):
    r = requests.get('http://localhost:8080/api/v1beta1/minions/' + ip)
    return r.json()


@celery.task()
def remove_minion_by_ip(ip):
    r = requests.delete('http://localhost:8080/api/v1beta1/minions/' + ip)
    # TODO remove directly from etcd registry, may be fixed in new kubernetes and not needed
    requests.delete('http://127.0.0.1:4001/v2/keys/registry/minions/' + ip + '?recursive=true')
    return r.json()


@celery.task()
def add_new_minion(ip):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    send_event('install_logs', 'Connecting with ssh-key id_rsa...')
    if DEBUG:
        ssh.connect(hostname=ip, username='root', password=MINION_SSH_AUTH)
    else:
        ssh.connect(hostname=ip, username='root', key_filename=MINION_SSH_AUTH)    # not tested

    sftp = ssh.open_sftp()
    sftp.put('kub_install.sh', '/kub_install.sh')
    sftp.close()
    i, o, e = ssh.exec_command('bash /kub_install.sh')
    while not o.channel.exit_status_ready():
        if o.channel.recv_ready():
            send_event('install_logs', o.channel.recv(1024))
    s = o.channel.recv_exit_status()
    if s != 0:
        message = 'Installation script error. Exit status: {0}. Error: {1}'.format(s, e.read())
        send_event('install_logs', message)
        res = json.dumps({'status': 'error', 'data': message})
    else:
        send_event('install_logs', 'Adding minion completed successful.')
        res = requests.post('http://localhost:8080/api/v1beta1/minions/', json={'id': ip, 'apiVersion': 'v1beta1'}).json()
    ssh.exec_command('rm /kub_install.sh')
    ssh.close()
    return res


@celery.task()
def check_events():
    redis = ConnectionPool.get_connection()

    lock = redis.get('events_lock')
    if not lock:
        redis.setex('events_lock', 10, 'true')
    else:
        return

    m = redis.get('cached_minions')
    if not m:
        m = get_all_minions.delay()
        redis.set('cached_minions', json.dumps(m.wait()['items']))
        send_event('ping', 'ping')
    else:
        temp = get_all_minions.delay()
        try:
            temp = temp.get(timeout=4)['items']
            if temp != json.loads(m):
                redis.set('cached_minions', json.dumps(temp))
                send_event('ping', 'ping')
        except TimeoutError:
            pass

    redis.delete('events_lock')