
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import gevent
import json
import os
import requests
from datetime import datetime
from socket import error as socket_error
from paramiko.ssh_exception import SSHException
from websocket import (create_connection, WebSocketException,
                       WebSocketConnectionClosedException)

from flask import current_app
from .core import ConnectionPool, ssh_connect, db
from .billing.models import Kube
from .nodes.models import Node
from .pods.models import Pod, PersistentDisk
from .users.models import User
from .settings import KUBERDOCK_INTERNAL_USER
from .utils import (get_api_url, unregistered_pod_warning,
                    send_event_to_role, send_event_to_user,
                    pod_without_id_warning, k8s_json_object_hook,
                    send_pod_status_update, POD_STATUSES, nested_dict_utils,
                    session_scope)
from .kapi.usage import update_states
from .kapi.podcollection import PodCollection, set_public_address
from .kapi.lbpoll import LoadBalanceService
from .kapi.pstorage import (
    get_storage_class_by_volume_info, LocalStorage, STORAGE_CLASS)
from .kapi import helpers
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
MAX_ATTEMPTS = 10
# How ofter we will send error about listener reconnection to sentry
ERROR_TIMEOUT = 3 * 60  # in seconds
LISTENER_PROBLEM_MSG = ("Problems in the listeners module have been "
                        "encountered. Please contact KuberDock Support"
                        "(see Settings, the License page)")


def filter_event(data, app):
    # Type of event is an optional field
    evt_type = data.get('type')
    with app.app_context():
        if evt_type == u'ERROR' or evt_type is None:
            current_app.logger.warning(
                'An error detected in events: %s', data
            )
            return None

        # Object is an optional field. Name in metadata is optional too.
        metadata = data.get('object', {}).get('metadata', {})
        name = metadata.get('name')
        if name in ('kubernetes', 'kubernetes-ro') or name is None:
            if name is None:
                current_app.logger.warning(
                    'Empty name in event object metadata: %s', data
                )
            return None

        return data


def get_pod_state(pod):
    res = [pod['status']['phase']]
    for container in pod['status'].get('containerStatuses', []):
        res.append(container.get('ready'))
    return json.dumps(res)


def process_pods_event(data, app, event_time=None, live=True):
    if not event_time:
        event_time = datetime.utcnow()
    event_type = data['type']
    pod = data['object']
    pod_id = pod['metadata'].get('labels', {}).get('kuberdock-pod-uid')

    if pod_id is None:
        pod_without_id_warning(pod['metadata']['name'],
                               pod['metadata']['namespace'])
        return

    # save states in database
    db_pod = Pod.query.get(pod_id)
    if db_pod is None:
        unregistered_pod_warning(pod_id)
        return

    # if live, we need to send events to frontend
    if db_pod.status == POD_STATUSES.stopping and event_type == 'DELETED':
        helpers.set_pod_status(pod_id, POD_STATUSES.stopped, send_update=live)
    elif live:
        send_pod_status_update(get_pod_state(pod), db_pod, event_type)

    host = pod['spec'].get('nodeName')

    update_states(pod, event_type=event_type, event_time=event_time)

    if event_type == 'MODIFIED':
        # fs limits
        containers = {}
        for container in pod['status'].get('containerStatuses', []):
            # Compose containers dict to set limits. Set limits only on running
            # containers.
            # We do not check field 'ready', because it may be not 'True' even
            # a pod is running - it is possible when readiness probe fails, but
            # a container is already running.
            if ('containerID' in container and
                    'running' in container.get('state', {})):
                container_name = container['name']
                container_id = container['containerID'].split('docker://')[-1]
                containers[container_name] = container_id
        if containers:
            set_limit(host, pod_id, containers, app)


# TODO: put it in some other place if needed.
# It was moved from utils to resolve
# circular imports (Kube model)
def set_limit(host, pod_id, containers, app):
    ssh, errors = ssh_connect(host)
    if errors:
        current_app.logger.warning(
            "Can't connect to {}, {}".format(host, errors))
        return False
    spaces = dict(
        (i, (s, u)) for i, s, u in Kube.query.values(
            Kube.id, Kube.disk_space, Kube.disk_space_units
        )
    )  # workaround

    pod = Pod.query.filter_by(id=pod_id).first()

    if pod is None:
        unregistered_pod_warning(pod_id)
        return False

    config = json.loads(pod.config)
    kube_type = pod.kube_id
    # kube = Kube.query.get(kube_type) this query raises an exception
    limits = []
    for container in config['containers']:
        container_name = container['name']
        if container_name not in containers:
            continue
        # disk_space = kube.disk_space * container['kubes']
        space, unit = spaces.get(kube_type, (0, 'GB'))
        disk_space = space * container['kubes']
        disk_space_unit = unit[0].lower() if unit else ''
        if disk_space_unit not in ('', 'k', 'm', 'g', 't'):
            disk_space_unit = ''
        disk_space_str = '{0}{1}'.format(disk_space, disk_space_unit)
        limits.append((containers[container_name], disk_space_str))
    limits_repr = ' '.join('='.join(limit) for limit in limits)
    try:
        _, o, e = ssh.exec_command(
            'python /var/lib/kuberdock/scripts/fslimit.py containers '
            '{0}'.format(limits_repr)
        )
        exit_status = o.channel.recv_exit_status()
        if exit_status > 0:
            current_app.logger.error(
                'Error fslimit.py with exit status {}, {},{}'.format(
                    exit_status, o.read(), e.read()))
            return False
    except SSHException:
        current_app.logger.warning("Can't set fslimit", exc_info=True)
        return False
    finally:
        ssh.close()
    return True


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
            # Flag shows that we must send notification to admin interface
            # for this change of node's state.
            must_send_event = True
            if 'unknown' in curr_state.lower():
                # Do nothing if the node is pending
                if redis.exists(pending_key):
                    return
                current_app.logger.debug(
                    'Node %s state is unknown and pending key does not exist',
                    hostname
                )
                # If the node has switched to 'unknown' from some another state
                # (or if there was no previous state),
                # then mark it as pending.
                redis.set(pending_key, 1)
                redis.expire(pending_key, 180)
                # Additionally check node is running
                tasks.check_if_node_down.delay(hostname)
            else:
                # The node is in some known state, so clear pending flag for it
                # if exists.
                redis.delete(pending_key)
                if event_type == 'DELETED':
                    curr_state = 'DELETED'
                    must_send_event = False
                # Must be already fixed in updated libcalico
                # try:
                #     # Workaround for
                #     # https://github.com/projectcalico/calico-containers/
                #     # issues/1190
                #     drop_endpoint_traffic_to_node(hostname)
                # except:
                #     current_app.logger.exception(
                #         'Failed to change node ({}) setting in etcd'.format(
                #             hostname
                #         )
                #     )

            current_app.logger.debug('Node event: save new state: %s, %s',
                                     key_, curr_state)
            redis.set(key_, curr_state)
            if must_send_event:
                # send update in common channel for all admins
                node = Node.query.filter_by(hostname=hostname).first()
                if node is not None:
                    current_app.logger.debug('Node %s - %s: fire change event',
                                             hostname, node.id)
                    send_event_to_role('node:change', {'id': node.id}, 'Admin')
            tasks.process_node_actions.delay(node_host=hostname)


def mark_restore_as_finished(pod_id):
    """
    Removes backup related data from POD spec. Is called after a restored POD
    successfully started which means that the restore process was successful.
    """
    pod_config = helpers.get_pod_config(pod_id)
    volumes_config = pod_config.get('volumes', [])
    volumes_public_config = pod_config.get('volumes_public', [])
    if volumes_config or volumes_public_config:
        for vc in volumes_config + volumes_public_config:
            nested_dict_utils.delete(
                vc, 'annotation.backupUrl', remove_empty_keys=True)
        updated_pod_data = PodCollection().update(pod_id, {
            'command': 'change_config',
            'volumes': volumes_config,
            'volumes_public': volumes_public_config,
        })
        current_app.logger.debug('mark_restore_as_finished: '
                                 'Removed backup-urls for pod %s. '
                                 'Updated pod data: %s',
                                 pod_id, updated_pod_data)
    else:
        current_app.logger.debug('mark_restore_as_finished: Nothing to do')


def process_events_event(data, app):
    """Process events from 'events' endpoint. At now only looks for
    involved object 'Pod' and reason 'failedScheduling' - we have to detect
    situation when scheduler can't find a node for a pod. It may be occurred,
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
    pod_id = obj.get('namespace')
    if reason == 'Started':
        with app.app_context():
            mark_restore_as_finished(pod_id)
        return

    if reason == 'FailedMount':
        # TODO: must be removed after Attach/Detach Controller
        # is added in k8s 1.3 version.
        with app.app_context():
            pod = Pod.query.get(pod_id)
            if pod is None:
                unregistered_pod_warning(pod_id)
                return
            storage = STORAGE_CLASS()
            for pd in pod.persistent_disks:
                storage.unlock_pd(pd)
    elif reason == 'FailedScheduling':
        with app.app_context():
            pod = Pod.query.get(pod_id)
            if pod is None:
                unregistered_pod_warning(pod_id)
                return
            pod_name = pod.name
            user = User.query.filter(User.id == pod.owner_id).first()
            if user is None:
                current_app.logger.warning('Unknown user for pod %s', pod_id)
                return

            if user.username == KUBERDOCK_INTERNAL_USER:
                return

            message = event['message']
            not_enough_resources_keywords = [
                'PodCount', 'CPU', 'Memory', 'PublicIP'
            ]

            node = pod.get_dbconfig('node')
            if any(item in message for item in not_enough_resources_keywords):
                reason = 'There are no enough resources for the pod'
            elif 'MatchNodeSelector' in message:
                if node is None:
                    reason = 'There are no suitable nodes for the pod'
                else:
                    if 'failed to fit in any node' in message:
                        reason = 'Suitable node is not ready'
                    else:
                        reason = (
                            'Unable to access Persistent volume(s): {0}'.format(
                                ', '.join('"{0}"'.format(d.name) for d in
                                          pod.persistent_disks)
                            )
                        )
            else:
                return

            # personalized user message
            message = 'Failed to run pod "{0}", reason: {1}'.format(
                pod_name, reason
            )
            send_event_to_user('notify:error', {'message': message}, user.id)

            # message for admins
            message = 'Failed to run pod "{0}", user "{1}", reason: {2}'
            message = message.format(pod_name, user.username, reason)

            if node is not None:
                message += ' (pinned to node "{0}")'.format(node)

            send_event_to_role('notify:error', {'message': message}, 'Admin')
            try:
                pods = PodCollection(user)
                params = {'command': 'stop'}
                pods.update(pod_id, params)
            except:
                current_app.logger.exception(
                    'Failed to stop pod %s, %s',
                    pod_id, pod_name
                )


def has_local_storage(volumes):
    if not volumes:
        return False
    for volume in volumes:
        cls = get_storage_class_by_volume_info(volume)
        if cls == LocalStorage:
            return True
    return False


def process_service_event_k8s(data, app):
    event_type = data['type']
    if event_type not in ('MODIFIED', 'ADDED'):
        return

    service = data['object']
    pod_id = service['spec'].get('selector', {}).get('kuberdock-pod-uid')
    if not pod_id:
        return
    with app.app_context():
        hostname = LoadBalanceService.get_public_dns(service)
        if hostname:
            set_public_address(hostname, pod_id, send=True)


def update_pod_direct_access(pods, pod, obj):
    """Update direct access attributes for pod"""
    try:
        conditions = obj.get('status', {}).get('conditions', ())
        if pod.status != POD_STATUSES.stopping:
            for c in conditions:
                if c['type'] == 'Ready' and c['status'] == 'True':
                    pods.update_direct_access(pod)
                    break
    except:
        current_app.logger.exception(
            "Failed to update direct access pod {}".format(pod))


def pin_pod_to_node(spec, node, pods, pod):
    """Binds pods and persistent disks to a node in a case when starts a pod
    with volumes on local storage backend.
    """
    try:
        pod_volumes = pod.get_dbconfig('volumes')
        if not has_local_storage(pod_volumes):
            return
        # Try to set node_id for every local PD of the pod, if they are not
        # set at the moment.
        # Set node selectors for the pod only if they are not set.
        dbnode = Node.get_by_name(node)
        if dbnode:
            PersistentDisk.bind_to_node(pod.id, dbnode.id)
        else:
            current_app.logger.warning('Unknown node with name "%s"', node)

        node_selector = spec.get(
            'nodeSelector', {}).get('kuberdock-node-hostname')
        if node_selector or pod.get_dbconfig('node'):
            return
        pods.update(pod.id, {'command': 'change_config', 'node': node})
    except:
        current_app.logger.exception(
            'Failed to pin pod "%s" to node "%s"', pod.id, node
        )
    else:
        current_app.logger.debug(
            'Pin pod "%s" to node "%s"', pod.id, node
        )


def process_pods_event_k8s(data, app):
    event_type = data['type']
    if event_type != 'MODIFIED':
        return

    obj = data['object']
    pod_id = obj.get('metadata', {}).get('labels', {}).get('kuberdock-pod-uid')
    if not pod_id:
        return

    spec = obj.get('spec', {})

    with app.app_context():
        pod = Pod.query.filter_by(id=pod_id).first()
        node = spec.get('nodeName')
        if not node or not pod:
            return
        user = User.query.filter(User.id == pod.owner_id).first()
        if user is None:
            current_app.logger.warning('Unknown user for pod %s', pod_id)
            return
        pods = PodCollection(user)
        update_pod_direct_access(pods, pod, obj)
        pin_pod_to_node(spec, node, pods, pod)


def prelist_version(url):
    res = requests.get(url)
    if res.ok:
        return res.json()['metadata']['resourceVersion']
    else:
        gevent.sleep(0.1)
        raise Exception('ERROR during pre list resource version. '
                        'Request result is {0}'.format(res.text))


def listen_fabric(watch_url, list_url, func, k8s_json_object_hook=None):
    fn_name = func.func_name
    redis_key = 'LAST_EVENT_' + fn_name

    def result(app):
        retry = 0
        last_reconnect = datetime.fromtimestamp(0)
        with app.app_context():
            while True:
                try:
                    current_app.logger.debug(
                        'START WATCH {0} == pid: {1}'.format(
                            fn_name, os.getpid()))
                    redis = ConnectionPool.get_connection()
                    last_saved = redis.get(redis_key)
                    try:
                        if not last_saved:
                            last_saved = prelist_version(list_url)
                        ws = create_connection(watch_url +
                                               '&resourceVersion={0}'
                                               .format(last_saved))
                        # Only after connection to ensure last_saved was correct
                        # before save it to redis
                        redis.set(redis_key, last_saved)
                    except (socket_error, WebSocketException) as e:
                        now = datetime.now()
                        logger = current_app.logger.warning
                        if (now - last_reconnect).total_seconds() > ERROR_TIMEOUT:
                            last_reconnect = now
                            logger = current_app.logger.error
                        logger("WebSocker error({})".format(fn_name),
                               exc_info=True)

                        gevent.sleep(0.1)
                        continue
                    while True:
                        content = ws.recv()
                        data = json.loads(content,
                                          object_hook=k8s_json_object_hook)
                        if data['type'].lower() == 'error' and \
                           '401' in data['object']['message']:
                            # Rewind to earliest possible
                            new_version = str(int(prelist_version(list_url)) -
                                              MAX_ETCD_VERSIONS)
                            redis.set(redis_key, new_version)
                            break
                        data = filter_event(data, app)
                        if not data:
                            continue
                        evt_version = data['object']['metadata']['resourceVersion']
                        last_saved = redis.get(redis_key)
                        if int(evt_version) > int(last_saved or '0'):
                            if retry < MAX_ATTEMPTS:
                                # Because listeners aren't managed by flask we
                                # have to do all transaction management manually
                                with session_scope(db.session):
                                    func(data, app)
                            else:
                                send_event_to_role(
                                    'notify:error',
                                    {'message': LISTENER_PROBLEM_MSG},
                                    'Admin')
                                current_app.logger.error(
                                    'skip event {}'.format(data), exc_info=True)

                            redis.set(redis_key, evt_version)
                        retry = 0
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    retry += 1
                    if not (isinstance(e, WebSocketConnectionClosedException)
                            and e.message == 'Connection is already closed.'):
                        now = datetime.now()
                        logger = current_app.logger.warning
                        if (now - last_reconnect).total_seconds() > ERROR_TIMEOUT:
                            last_reconnect = now
                            logger = current_app.logger.error
                        logger('restarting listen: {}'.format(fn_name),
                               exc_info=True)
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
    """Get extended statuses from etcd key and prepare it for kuberdock
    process.
    Delete delete namespace dir from etcd after processing.
    """
    if data['action'] != 'set':
        return
    key = data['node']['key']
    _, namespace, pod = key.rsplit('/', 2)
    status = data['node']['value']
    current_app.logger.debug('Namespace: {0} | Pod: {1} | Status: {2}'.format(
        namespace, pod, status))
    # TODO: don't do this if we have several pods in one namespace
    r = requests.delete(
        ETCD_URL.format(key.rsplit('/', 1)[0]),
        params={'recursive': True, 'dir': True})
    if not r.ok:
        current_app.logger.warning("error while delete:{}".format(r.text))


def listen_fabric_etcd(url):

    def result(app):
        last_reconnect = datetime.fromtimestamp(0)
        with app.app_context():
            while True:
                try:
                    res = requests.get(url,
                                       params={
                                           'recursive': True, 'sorted': True})
                    if res.ok:
                        data = res.json()
                        etcd_index = res.headers['x-etcd-index']
                        nodes = data['node'].get('nodes', tuple())
                        if nodes:
                            process_records(app, nodes)
                            # we proceed all event, now we need to get
                            # list again
                            continue
                        else:
                            # list is empty, need to wait for new events
                            requests.get(url, params={
                                'wait': True, 'recursive': True,
                                'waitIndex': etcd_index})
                            # we have new event, need to get list again
                            continue
                except KeyboardInterrupt:
                    break
                except requests.exceptions.RequestException:
                    now = datetime.now()
                    logger = current_app.logger.warning
                    if (now-last_reconnect).total_seconds() > ERROR_TIMEOUT:
                        last_reconnect = now
                        logger = current_app.logger.exception
                    logger('Error while etcd connect', exc_info=True)
                except Exception:
                    current_app.logger.warning(
                        "Error while get keys", exc_info=True)
                # if we get here, that mean some exception occurred or
                # we can't get list of keys.
                # we sleep and try to get list of keys again
                gevent.sleep(1)
    return result


def process_records(app, nodes):
    for node in nodes:
        # TODO: for now send all prelist event to process,
        # but there are no need to send old events to frontend,
        # just need to save them to db. Need to have separate method
        # or filter old events by time.
        try:
            key = node['key']
            for _ in range(MAX_ATTEMPTS):
                _, ts = key.rsplit('/', 1)
                obj = node['value']
                k8s_obj = json.loads(obj, object_hook=k8s_json_object_hook)
                k8s_obj = filter_event(k8s_obj, app)
                event_time = datetime.fromtimestamp(float(ts))
                if k8s_obj is not None:
                    try:
                        process_pods_event(k8s_obj, app, event_time, live=True)
                        break
                    except Exception:
                        current_app.logger.warning(
                            "Error while process event {}".format(node),
                            exc_info=True)

            else:
                # max_attempts exceeded, we skip event
                send_event_to_role(
                    'notify:error', {'message': LISTENER_PROBLEM_MSG}, 'Admin')
                current_app.logger.error(
                    'skip event {}'.format(node), exc_info=True)
        except:
            current_app.logger.exception(
                "Error while parse event {}".format(node))
        finally:
            # at the end we remove node anyway
            r = requests.delete(ETCD_URL.format(key))
            # don't know what we can do more, just log it
            if not r.ok:
                current_app.logger.warning(
                    "error while delete:{}".format(r.text))


listen_pods = listen_fabric(
    get_api_url('pods', namespace=False, watch=True),
    get_api_url('pods', namespace=False),
    process_pods_event_k8s
)

listen_services = listen_fabric(
    get_api_url('services', namespace=False, watch=True),
    get_api_url('services', namespace=False),
    process_service_event_k8s
)

listen_nodes = listen_fabric(
    get_api_url('nodes', namespace=False, watch=True),
    get_api_url('nodes', namespace=False),
    process_nodes_event
)

listen_events = listen_fabric(
    get_api_url('events', namespace=False, watch=True),
    get_api_url('events', namespace=False),
    process_events_event
)

# we don't use it for now
# listen_extended_statuses = listen_fabric_etcd(
#     ETCD_EXTENDED_STATUSES_URL,
#     process_extended_statuses,
#     prelist_extended_statuses
# )

listen_pod_states = listen_fabric_etcd(ETCD_POD_STATES_URL)
