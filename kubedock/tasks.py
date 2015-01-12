import json
import requests
from .factory import make_celery

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
