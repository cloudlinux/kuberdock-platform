import traceback
import gevent
import json
import os
import requests
from datetime import datetime
from websocket import (create_connection, WebSocketException,
                       WebSocketConnectionClosedException)

from flask import current_app
from .core import ConnectionPool
from .nodes.models import Node
from .pods.models import Pod, PersistentDisk
from .users.models import User
from .settings import PODS_VERBOSE_LOG, KUBERDOCK_INTERNAL_USER
from .utils import (get_api_url, set_limit,
                    unregistered_pod_warning, send_event,
                    pod_without_id_warning, k8s_json_object_hook)
from .kapi.usage import update_states
from .kapi.podcollection import PodCollection
from . import tasks


MAX_ETCD_VERSIONS = 1000
ETCD_URL = 'http://127.0.0.1:4001/v2/keys/{0}'
ETCD_KUBERDOCK = 'kuberdock'
ETCD_NETWORK_PLUGIN = 'network/plugin'
ETCD_EXTENDED_STATUSES = 'extended_statuses'
ETCD_EXTENDED_STATUSES_URL = ETCD_URL.format('/'.join([
    ETCD_KUBERDOCK, ETCD_NETWORK_PLUGIN, ETCD_EXTENDED_STATUSES]))
ETCD_POD_STATES = 'pod_states'
ETCD_POD_STATES_URL = ETCD_URL.format('/'.join([
    ETCD_KUBERDOCK, ETCD_POD_STATES]))


def filter_event(data):
    metadata = data['object']['metadata']
    if metadata['name'] in ('kubernetes', 'kubernetes-ro'):
        return None

    return data


def get_pod_state(pod):
    res = [pod['status']['phase']]
    for container in pod['status'].get('containerStatuses', []):
        res.append(container.get('ready'))
    return json.dumps(res)


def send_pod_status_update(pod, db_pod, event_type, app):
    key_ = 'pod_state_' + db_pod.id

    redis = ConnectionPool.get_connection()
    prev_state = redis.get(key_)
    if not prev_state:
        redis.set(key_, get_pod_state(pod))
    else:
        current = get_pod_state(pod)
        deleted = event_type == 'DELETED'
        if prev_state != current or deleted:
            redis.set(key_, 'DELETED' if deleted else current)
            owner = db_pod.owner.id
            event = ('pod:delete'
                     if db_pod.status in ('deleting', 'deleted') else
                     'pod:change')
            send_event(event, {'id': db_pod.id})   # common for admins
            send_event(event, {'id': db_pod.id},
                       channel='user_{0}'.format(owner))


def process_pods_event(data, app, event_time=None, live=True):
    if PODS_VERBOSE_LOG >= 2:
        print 'POD EVENT', data
    if not event_time:
        event_time = datetime.utcnow()
    event_type = data['type']
    pod = data['object']
    pod_id = pod['metadata'].get('labels', {}).get('kuberdock-pod-uid')
    deleted = event_type == 'DELETED'

    if pod_id is None:
        with app.app_context():
            pod_without_id_warning(pod['metadata']['name'],
                                   pod['metadata']['namespace'])
        return

    # save states in database
    with app.app_context():
        db_pod = Pod.query.get(pod_id)
        if db_pod is None:
            unregistered_pod_warning(pod_id)
            return

        # if live, we need to send events to frontend
        if live:
            send_pod_status_update(pod, db_pod, event_type, app)

        host = pod['spec'].get('nodeName')

        phase = pod['status'].get('phase', '').lower()
        #if deleted or phase in ('succeeded', 'failed'):
            #PersistentDisk.free(pod_id)
        update_states(pod_id, pod['status'], event_type=event_type,
                      host=host, event_time=event_time)

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
    hostname = node['metadata']['name']
    key_ = 'node_state_' + hostname
    pending_key = 'node_unknown_state:' + hostname
    with app.app_context():
        redis = ConnectionPool.get_connection()
        prev_state = redis.get(key_)
        curr_state = get_node_state(node)
        if prev_state != curr_state:
            if 'unknown' in curr_state.lower():
                # update event after we've learnt node state
                if not redis.exists(pending_key):
                    tasks.check_if_node_down.delay(hostname, curr_state)
            else:
                if event_type == 'DELETED':
                    redis.set(key_, 'DELETED')
                else:
                    redis.delete(pending_key)
                    redis.set(key_, curr_state)
                # send update in common channel for all admins
                node = Node.query.filter_by(hostname=hostname).first()
                if node is not None:
                    send_event('node:change', {'id': node.id})


def process_events_event(data, app):
    """Process events from 'events' endpoint. At now only looks for
    involved object 'Pod' and reason 'failedScheduling' - we have to detect
    situation when scheduler can't find a node for a pod. It may be occured,
    for example, when there no nodes with enough resources.
    We will stop that pod and send notification for a user.

    """
    event_type = data['type']
    # Ignore all types except 'ADDED'. For some (unknown?) reason kubernetes
    # send multiple events with type 'DELETED' when failed pod was deleted
    if event_type != 'ADDED':
        return
    event = data['object']
    obj = event['involvedObject']
    if obj.get('kind') != 'Pod':
        return
    reason = event['reason']
    if reason != 'failedScheduling':
        return
    pod_id = obj.get('namespace')
    reason = event['message']
    if 'PodFitsResources' in reason:
        reason = 'There are no enough resources for the pod'
    elif 'MatchNodeSelector' in reason:
        reason = 'There are no suitable nodes for the pod'
    else:
        return

    with app.app_context():
        pod = Pod.query.get(pod_id)
        pod_name = pod.name
        if pod is None:
            unregistered_pod_warning(pod_id)
            return
        user = User.query.filter(User.id == pod.owner_id).first()
        if user is None:
            current_app.logger.warning(
                'Unknown user for pod %s',
                pod_id
            )
            return

        if user.username == KUBERDOCK_INTERNAL_USER:
            return

        # personalized user message
        message = 'Failed to start pod "{0}", reason: {1}'.format(
            pod_name, reason
        )
        send_event('notify:error', {'message': message},
                   channel='user_{0}'.format(user.id))

        # message for admins
        message = 'Failed to start pod "{0}", user "{1}", reason: {2}'.format(
            pod_name, user.username, reason
        )
        send_event('notify:error', {'message': message})
        try:
            pods = PodCollection(user)
            params = {'command': 'stop'}
            pods.update(pod_id, params)
        except:
            current_app.logger.exception(
                'Failed to stop pod %s, %s',
                pod_id, pod_name
            )


def prelist_version(url):
    res = requests.get(url)
    if res.ok:
        return res.json()['metadata']['resourceVersion']
    else:
        gevent.sleep(0.1)
        raise Exception('ERROR during pre list resource version. '
                        'Request result is {0}'.format(res.text))


def listen_fabric(watch_url, list_url, func, verbose=1, k8s_json_object_hook=None):
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
                    ws = create_connection(watch_url + '&resourceVersion={0}'
                                           .format(last_saved))
                    # Only after connection to ensure last_saved was correct
                    # before save it to redis
                    redis.set(redis_key, last_saved)
                except WebSocketException as e:
                    print e.__repr__()
                    gevent.sleep(0.1)
                    continue
                while True:
                    content = ws.recv()
                    if verbose >= 3:
                        print '==EVENT CONTENT {0} ==: {1}'.format(
                            fn_name, content)
                    data = json.loads(content, object_hook=k8s_json_object_hook)
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
                    print('{0}\n...restarting listen {1}...'
                          .format(traceback.format_exc(), fn_name))
                gevent.sleep(0.2)
    return result


def listen_fabric_etcd(url, func, list_func=None, verbose=1):
    fn_name = func.func_name

    def result(app):
        index = 0
        while True:
            try:
                if verbose >= 2:
                    print '==START WATCH {0}==pid:{1}'.format(
                        fn_name, os.getpid())
                if not index and list_func:
                    index = list_func(app)
                r = requests.get(url, params={'wait': True,
                                              'recursive': True,
                                              'waitIndex': index})
                if verbose >= 3:
                    print '==EVENT CONTENT {0} ==: {1}'.format(
                        fn_name, r.text)
                data = r.json()
                # The event in requested index is outdated and cleared
                if data.get('errorCode') == 401:
                    print "The event in requested index is outdated and "\
                            "cleared. Skip all events and wait for new one"
                    index = 0
                    continue
                func(data, app)
                index = int(data['node']['modifiedIndex']) + 1
            except KeyboardInterrupt:
                break
            except Exception as e:
                print repr(e), '...restarting listen {0}...'.format(fn_name)
                gevent.sleep(0.2)
    return result


def prelist_extended_statuses(app):
    """ Check if there are already some extended statuses stored in etcd and
    process them. Get etcd index from header and return it.
    """
    res = requests.get(ETCD_EXTENDED_STATUSES_URL, params={'recursive': True,
                                                           'sorted': True})
    try:
        if res.ok:
            data = res.json()
            etcd_index = res.headers['x-etcd-index']
            for namespace in data['node'].get('nodes', []):
                for pod in namespace.get('nodes', []):
                    process_extended_statuses(
                        {'action': 'set', 'node': pod}, app)
            return int(etcd_index) + 1
        elif res.json().get('errorCode') != 100:
            raise ValueError()
    except ValueError:
        raise Exception("Error while prelist expod states:{}".format(res.text))


def process_extended_statuses(data, app):
    """Get extended statuses from etcd key and prepare it for kuberdock process.
    Delete delete namespace dir from etcd after processing.
    """
    if data['action'] != 'set':
        return
    key = data['node']['key']
    _, namespace, pod = key.rsplit('/', 2)
    status = data['node']['value']
    print '=== Namespace: {0} | Pod: {1} | Status: {2} ==='.format(
        namespace, pod, status)
    # TODO: don't do this if we have several pods in one namespace
    r = requests.delete(
        ETCD_URL.format(key.rsplit('/', 1)[0]),
        params={'recursive': True, 'dir': True})
    if not r.ok:
        print "error while delete:{}".format(r.text)


def prelist_pod_states(app):
    """ Check if there are already some pod states stored in etcd and
    process them. Get etcd index from header and return it.
    """
    res = requests.get(ETCD_POD_STATES_URL,
                       params={'recursive': True, 'sorted': True})
    try:
        if res.ok:
            data = res.json()
            etcd_index = res.headers['x-etcd-index']
            for node in data['node'].get('nodes', []):
                # TODO: for now send all prelist event to process, but there are no
                # need to send old events to frontend, just need to save them
                # to db. Need to have separate method or filter old events by time.
                process_pod_states(
                    {'action': 'set', 'node': node}, app, live=False)
            return int(etcd_index) + 1
        elif res.json().get('errorCode') != 100:
            raise ValueError()
    except ValueError:
        raise Exception("Error while prelist pod states: {}".format(res.text))


def process_pod_states(data, app, live=True):
    """ Get pod event from etcd event and prepare it for kuberdock process.
    Delete pod event from etcd after processing.
    """
    if data['action'] != 'set':
        return
    key = data['node']['key']
    _, ts = key.rsplit('/', 1)
    obj = data['node']['value']
    k8s_obj = json.loads(obj, object_hook=k8s_json_object_hook)
    k8s_obj = filter_event(k8s_obj)
    event_time = datetime.fromtimestamp(float(ts))
    process_pods_event(k8s_obj, app, event_time, live)
    r = requests.delete(ETCD_URL.format(key))
    if not r.ok:
        print "error while delete:{}".format(r.text)


listen_nodes = listen_fabric(
    get_api_url('nodes', namespace=False, watch=True),
    get_api_url('nodes', namespace=False),
    process_nodes_event,
    0
)

listen_events = listen_fabric(
    get_api_url('events', namespace=False, watch=True),
    get_api_url('events', namespace=False),
    process_events_event,
    1
)

listen_extended_statuses = listen_fabric_etcd(
    ETCD_EXTENDED_STATUSES_URL,
    process_extended_statuses,
    prelist_extended_statuses,
    1
)

listen_pod_states = listen_fabric_etcd(
    ETCD_POD_STATES_URL,
    process_pod_states,
    prelist_pod_states,
    PODS_VERBOSE_LOG
)
