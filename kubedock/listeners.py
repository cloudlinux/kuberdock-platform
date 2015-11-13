import gevent
import json
import os
import requests
from websocket import (create_connection, WebSocketException,
                       WebSocketConnectionClosedException)

from .core import ConnectionPool
from .pods.models import Pod, PersistentDisk
from .settings import SERVICES_VERBOSE_LOG, PODS_VERBOSE_LOG
from .utils import (modify_node_ips, get_api_url, set_limit,
                    unregistered_pod_warning, send_event,
                    pod_without_id_warning, unbind_ip)
from .kapi.usage import save_pod_state, update_containers_state


MAX_ETCD_VERSIONS = 1000


def filter_event(data):
    metadata = data['object']['metadata']
    if metadata['name'] in ('kubernetes', 'kubernetes-ro'):
        return None

    return data


def process_endpoints_event(data, app):
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
        elif event_type == 'MODIFIED':      # when stop(delete) pod
            if SERVICES_VERBOSE_LOG >= 2:
                print 'SERVICE IN MODIF(pods 0)', service
            state = json.loads(service['metadata']['annotations']['public-ip-state'])
            if SERVICES_VERBOSE_LOG >= 2:
                print 'STATE(pods=0)==========', state
            if 'assigned-to' in state:
                unbind_ip(service_name, state, service,
                          SERVICES_VERBOSE_LOG, app)
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
        if SERVICES_VERBOSE_LOG >= 2:
            print 'STATE(pods=1)==========', state
        public_ip = state['assigned-public-ip']
        if not public_ip:
            # TODO change with "release ip" feature
            return
        assigned_to = state.get('assigned-to')
        podname = pods[0]['addresses'][0]['targetRef']['name']
        # Can't use task.get_pods_nodelay due cyclic imports
        kub_pod = requests.get(get_api_url('pods', podname,
                                           namespace=current_namespace))
        if not kub_pod.ok:
            # If 404 than it's double pod respawn case
            # Pod may be deleted at this moment
            return
        kub_pod = kub_pod.json()
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
        else:   # Happens after reboot node
            if current_host != assigned_to:     # migrate pod
                # This case is never happens, presumably due fact that pod is
                # never changes - old pod deleted and new pod created.
                # Maybe this case will be useful in "unbind at runtime" feature
                # or when we can switch kube_type
                if SERVICES_VERBOSE_LOG >= 2:
                    print 'MIGRATE POD from {0} to {1}'.format(assigned_to,
                                                               current_host)
                # Try to unbind ip from possibly failed node, even if we can't
                # we add ip to another node.
                unbind_ip(service_name, state, service,
                          SERVICES_VERBOSE_LOG, app)
                res2 = modify_node_ips(service_name, current_host, 'add', pod_ip,
                                       public_ip, ports, app)
                if res2 is True:
                    state['assigned-to'] = current_host
                    state['assigned-pod-ip'] = pod_ip
                    service['metadata']['annotations']['public-ip-state'] = json.dumps(state)
                    r = requests.put(get_api_url('services', service_name,
                                     namespace=current_namespace), service)
                else:
                    print 'Failed to bind new ip to {0}'.format(current_host)
    else:   # more? replica case
        pass


def get_pod_state(pod):
    res = [pod['status']['phase']]
    for container in pod['status'].get('containerStatuses', []):
        res.append(container.get('ready'))
    return json.dumps(res)


def send_pod_status_update(pod, pod_id, event_type, app):
    key_ = 'pod_state_' + pod_id
    with app.app_context():
        redis = ConnectionPool.get_connection()
        prev_state = redis.get(key_)
        if not prev_state:
            redis.set(key_, get_pod_state(pod))
        else:
            current = get_pod_state(pod)
            deleted = event_type == 'DELETED'
            if prev_state != current or deleted:
                redis.set(key_, 'DELETED' if deleted else current)
                db_pod = Pod.query.get(pod_id)
                if not db_pod:
                    unregistered_pod_warning(pod_id)
                    return
                owner = db_pod.owner.id
                send_event('pull_pods_state', 'ping')   # common for admins
                send_event('pull_pods_state', 'ping', channel='user_%s' % owner)


def process_pods_event(data, app):
    if PODS_VERBOSE_LOG >= 2:
        print 'POD EVENT', data
    event_type = data['type']
    pod = data['object']
    pod_id = pod['metadata'].get('labels', {}).get('kuberdock-pod-uid')
    if pod_id is None:
        with app.app_context():
            pod_without_id_warning(pod['metadata']['name'],
                                   pod['metadata']['namespace'])
        return

    send_pod_status_update(pod, pod_id, event_type, app)

    with app.app_context():
        if Pod.query.get(pod_id) is None:
            unregistered_pod_warning(pod_id)
            return

        host = pod['spec'].get('nodeName')
        if host is not None:
            save_pod_state(pod_id, event_type, host)

        if event_type in ('MODIFIED', 'DELETED'):
            if event_type == 'DELETED' or \
                    pod['status']['phase'].lower() in ('succeeded', 'failed'):
                PersistentDisk.free(pod_id)
            containers = pod['status'].get('containerStatuses', [])
            if containers:
                update_containers_state(pod_id, containers,
                                        deleted=(event_type == 'DELETED'))

    if event_type == 'MODIFIED':
        # fs limits
        containers = {}
        for container in pod['status'].get('containerStatuses', []):
            if 'containerID' in container:
                container_name = container['name']
                container_id = container['containerID'].split('docker://')[-1]
                containers[container_name] = container_id
        if containers:
            set_limit(host, pod_id, containers, app)


def get_node_state(node):
    res = []
    try:
        conditions = node['status']['conditions']
        for cond in conditions:
            res.append(cond.get('type', ''))
            res.append(cond.get('status', ''))
    except KeyError:
        res.append('')
    return json.dumps(res)


def process_nodes_event(data, app):
    event_type = data['type']
    node = data['object']
    key_ = 'node_state_' + node['metadata']['name']

    with app.app_context():
        redis = ConnectionPool.get_connection()
        prev_state = redis.get(key_)
        if not prev_state:
            redis.set(key_, get_node_state(node))
        else:
            current = get_node_state(node)
            deleted = event_type == 'DELETED'
            if prev_state != current or deleted:
                redis.set(key_, 'DELETED' if deleted else current)
                send_event('pull_nodes_state', 'ping')   # common ch for admins


def prelist_version(url):
    res = requests.get(url)
    if res.ok:
        return res.json()['metadata']['resourceVersion']
    else:
        gevent.sleep(0.1)
        raise Exception('ERROR during pre list resource version. '
                        'Request result is {0}'.format(res.text))


def listen_fabric(watch_url, list_url, func, verbose=1):
    fn_name = func.func_name
    redis_key = 'LAST_EVENT_' + fn_name

    def result(app):
        while True:
            try:
                if verbose >= 2:
                    print '==START WATCH {0} == pid: {1}'.format(
                        fn_name, os.getpid())
                with app.app_context():
                    redis = ConnectionPool.get_connection()
                last_saved = redis.get(redis_key)
                try:
                    if not last_saved:
                        last_saved = prelist_version(list_url)
                        redis.set(redis_key, last_saved)
                    ws = create_connection(watch_url + '&resourceVersion={0}'
                                           .format(last_saved))
                except WebSocketException as e:
                    print e.__repr__()
                    gevent.sleep(0.1)
                    continue
                while True:
                    content = ws.recv()
                    if verbose >= 3:
                        print '==EVENT CONTENT {0} ==: {1}'.format(
                            fn_name, content)
                    data = json.loads(content)
                    if data['type'].lower() == 'error' and \
                       '401' in data['object']['message']:
                        # Rewind to earliest possible
                        new_version = str(int(prelist_version(list_url)) -
                                          MAX_ETCD_VERSIONS)
                        redis.set(redis_key, new_version)
                        break
                    evt_version = data['object']['metadata']['resourceVersion']
                    last_saved = redis.get(redis_key)
                    if int(evt_version) > int(last_saved or '0'):
                        data = filter_event(data)
                        if data:
                            func(data, app)
                        redis.set(redis_key, evt_version)
            except KeyboardInterrupt:
                break
            except Exception as e:
                if not (isinstance(e, WebSocketConnectionClosedException) and
                        e.message == 'Connection is already closed.'):
                    print e.__repr__(), '...restarting listen {0}...'\
                        .format(fn_name)
                gevent.sleep(0.2)
    return result


listen_pods = listen_fabric(
    get_api_url('pods', namespace=False, watch=True),
    get_api_url('pods', namespace=False),
    process_pods_event,
    PODS_VERBOSE_LOG
)

listen_endpoints = listen_fabric(
    get_api_url('endpoints', namespace=False, watch=True),
    get_api_url('endpoints', namespace=False),
    process_endpoints_event,
    SERVICES_VERBOSE_LOG
)

listen_nodes = listen_fabric(
    get_api_url('nodes', namespace=False, watch=True),
    get_api_url('nodes', namespace=False),
    process_nodes_event,
    0
)
