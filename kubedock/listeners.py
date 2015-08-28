import datetime
import gevent
import json
import os
import requests
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from websocket import create_connection, WebSocketException

from .core import db
from .pods.models import ContainerState, Pod
from .settings import SERVICES_VERBOSE_LOG, PODS_VERBOSE_LOG
from .tasks import fix_pods_timeline_heavy
from .utils import modify_node_ips, get_api_url, set_limit


DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


def filter_event(data):
    metadata = data['object']['metadata']
    if metadata['name'] in ('kubernetes', 'kubernetes-ro'):
        return None

    return data


def process_endpoints_event(data, app):
    if data is None:
        return
    if SERVICES_VERBOSE_LOG >= 2:
        print 'ENDPOINT EVENT', data
    service_name = data['object']['metadata']['name']
    current_namespace = data['object']['metadata']['namespace']
    r = requests.get(get_api_url('services', service_name,
                                 namespace=current_namespace))
    if r.status_code == 404:
        return
    service = r.json()
    event_type = data['type']
    pods = data['object']['subsets']
    if len(pods) == 0:
        if event_type == 'ADDED':
            # Handle here if public-ip added during runtime
            if SERVICES_VERBOSE_LOG >= 2:
                print 'SERVICE IN ADDED(pods 0)', service
        elif event_type == 'MODIFIED':      # when stop pod
            if SERVICES_VERBOSE_LOG >= 2:
                print 'SERVICE IN MODIF(pods 0)', service
            state = json.loads(service['metadata']['annotations']['public-ip-state'])
            if 'assigned-to' in state:
                res = modify_node_ips(service_name, state['assigned-to'], 'del',
                                      state['assigned-pod-ip'],
                                      state['assigned-public-ip'],
                                      service['spec']['ports'], app)
                if res is True:
                    del state['assigned-to']
                    del state['assigned-pod-ip']
                    service['metadata']['annotations']['public-ip-state'] = json.dumps(state)
                    # TODO what if resourceVersion has changed?
                    r = requests.put(get_api_url('services', service_name,
                                     namespace=current_namespace),
                                     json.dumps(service))
        elif event_type == 'DELETED':
            pass
            # Handle here if public-ip removed during runtime
        else:
            print 'Unknown event type in endpoints event listener:', event_type
    elif len(pods) == 1:
        state = json.loads(service['metadata']['annotations']['public-ip-state'])
        public_ip = state['assigned-public-ip']
        if not public_ip:
            # TODO change with "release ip" feature
            return
        assigned_to = state.get('assigned-to')
        podname = pods[0]['addresses'][0]['targetRef']['name']
        # Can't use task.get_pods_nodelay due cyclic imports
        kub_pod = requests.get(get_api_url('pods', podname,
                                           namespace=current_namespace)).json()
        ports = service['spec']['ports']
        # TODO what to do here when pod yet not assigned to node at this moment?
        # skip only this event or reconnect(like now)?
        current_host = kub_pod['spec']['nodeName']
        pod_ip = pods[0]['addresses'][0]['ip']
        if not assigned_to:
            res = modify_node_ips(service_name, current_host, 'add', pod_ip, public_ip, ports, app)
            if res is True:
                state['assigned-to'] = current_host
                state['assigned-pod-ip'] = pod_ip
                service['metadata']['annotations']['public-ip-state'] = json.dumps(state)
                r = requests.put(get_api_url('services', service_name,
                                 namespace=current_namespace),
                                 json.dumps(service))
        else:
            if current_host != assigned_to:     # migrate pod
                if SERVICES_VERBOSE_LOG >= 2:
                    print 'MIGRATE POD'
                res = modify_node_ips(service_name, assigned_to, 'del',
                                      state['assigned-pod-ip'],
                                      public_ip, ports, app)
                if res is True:
                    res2 = modify_node_ips(service_name, current_host, 'add', pod_ip,
                                           public_ip, ports, app)
                    if res2 is True:
                        state['assigned-to'] = current_host
                        state['assigned-pod-ip'] = pod_ip
                        service['metadata']['annotations']['public-ip-state'] = json.dumps(state)
                        r = requests.put(get_api_url('services', service_name,
                                         namespace=current_namespace), service)
    else:   # more? replica case
        pass


def process_pods_event(data, app):
    if data is None:
        return
    if PODS_VERBOSE_LOG >= 2:
        print 'POD EVENT', data
    event_type = data['type']
    pod = data['object']
    pod_name = pod['metadata']['labels']['name']
    with app.app_context():
        pod_id = Pod.query.filter_by(name=pod_name).value(Pod.id)

    if event_type in ('MODIFIED', 'DELETED'):

        # container state
        with app.app_context():
            for container in pod['status'].get('containerStatuses', []):
                container_name = container['name']
                kubes = container.get('kubes', 1)
                for state in container['state'].values():
                    start = state.get('startedAt')
                    if start is None:
                        continue
                    start = datetime.datetime.strptime(start, DATETIME_FORMAT)
                    end = state.get('finishedAt')
                    cs = ContainerState.query.filter_by(
                        pod_id=pod_id,
                        container_name=container_name,
                        kubes=kubes,
                        start_time=start,
                    ).first()
                    if end is not None:
                        end = datetime.datetime.strptime(end, DATETIME_FORMAT)
                    elif event_type == 'DELETED':
                        end = datetime.datetime.utcnow().replace(microsecond=0)
                    if cs:
                        cs.end_time = end
                    else:
                        cs = ContainerState(
                            pod_id=pod_id,
                            container_name=container_name,
                            kubes=kubes,
                            start_time=start,
                            end_time=end,
                        )
                        db.session.add(cs)
                    try:
                        prev_cs = ContainerState.query.filter(
                            ContainerState.pod_id == pod_id,
                            ContainerState.container_name == container_name,
                            ContainerState.start_time < start,
                            db.or_(ContainerState.end_time > start,
                                   ContainerState.end_time.is_(None)),
                        ).one()
                    except MultipleResultsFound:
                        fix_pods_timeline_heavy.delay()
                    except NoResultFound:
                        pass
                    else:
                        prev_cs.end_time = start
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

    if event_type == 'MODIFIED':
        # fs limits
        host = pod['spec'].get('nodeName')
        if host is None:
            return
        containers = {}
        for container in pod.get('containerStatuses', []):
            if 'containerID' in container:
                container_name = container['name']
                container_id = container['containerID'].partition('docker://')[2]
                containers[container_name] = container_id
        if containers:
            set_limit(host, pod_name, containers, app)


def listen_fabric(url, func, verbose=1):
    fn_name = func.func_name

    def result(app):
        while True:
            try:
                if verbose >= 2:
                    print '==START WATCH {0} == pid: {1}'.format(
                        fn_name, os.getpid())
                try:
                    ws = create_connection(url)
                except WebSocketException as e:
                    print e.__repr__()
                    gevent.sleep(0.1)
                    continue
                while True:
                    content = ws.recv()
                    if verbose >= 2:
                        print '==EVENT CONTENT {0} ==: {1}'.format(
                            fn_name, content)
                    data = json.loads(content)
                    data = filter_event(data)
                    func(data, app)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print e.__repr__(), '..restarting listen {0}...'.format(fn_name)
                gevent.sleep(0.2)
    return result


listen_pods = listen_fabric(
    get_api_url('pods', namespace=False, watch=True).replace('http', 'ws'),
    process_pods_event,
    PODS_VERBOSE_LOG
)

listen_endpoints = listen_fabric(
    get_api_url('endpoints', namespace=False, watch=True).replace('http', 'ws'),
    process_endpoints_event,
    SERVICES_VERBOSE_LOG
)
