import datetime
from .. import factory
from .. import sessions
from ..rbac import get_user_role
from ..settings import SERVICES_VERBOSE_LOG
from ..utils import APIError, modify_node_ips, get_api_url

from flask.ext.login import current_user
from flask import jsonify
import json
import requests
import gevent
import os
from rbac.context import PermissionDenied


def create_app(settings_override=None, fake_sessions=False):
    skip_paths = []
    app = factory.create_app(__name__, __path__, settings_override)
    if fake_sessions:
        app.session_interface = sessions.FakeSessionInterface()
    else:
        app.session_interface = sessions.ManagedSessionInterface(
            sessions.DataBaseSessionManager(app.config['SECRET_KEY']),
            skip_paths, datetime.timedelta(days=1))

    # registering blueprings
    from .images import images
    from .stream import stream
    from .nodes import nodes
    from .stats import stats
    from .users import users
    from .notifications import notifications
    from .static_pages import static_pages
    from .usage import usage
    from .pricing import pricing
    from .ippool import ippool
    from .settings import settings
    from .podapi import podapi
    from .auth import auth
    from .pstorage import pstorage

    for bp in images, stream, nodes, stats, users, notifications, \
              static_pages, usage, pricing, ippool, settings, podapi, auth, \
              pstorage:
        app.register_blueprint(bp)

    #app.json_encoder = JSONEncoder
    app.errorhandler(404)(on_404)
    app.errorhandler(PermissionDenied)(on_permission_denied)
    app.errorhandler(APIError)(on_app_error)

    return app


def on_app_error(e):
    return jsonify({'status': 'error', 'data': e.message}), e.status_code


def on_permission_denied(e):
    message = e.kwargs['message'] or 'Denied to {0}'.format(get_user_role())
    return on_app_error(APIError('Error. {0}'.format(message), status_code=403))


def on_404(e):
    return on_app_error(APIError('Not found', status_code=404))


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


def listen_endpoints(app):
    while True:
        try:
            if SERVICES_VERBOSE_LOG >= 2:
                print '==START WATCH ENDPOINTS== pid:', os.getpid()
            r = requests.get(
                get_api_url('endpoints', namespace=False, watch=True),
                stream=True)
            if r.status_code != 200:
                gevent.sleep(0.1)
                print "CAN'T CONNECT TO KUBERNETES APISERVER WATCH. RECONNECT"
            while not r.raw.closed:
                content_length = r.raw.readline().strip()
                if content_length not in ('0', ''):
                    content = r.raw.read(int(content_length, 16)).strip()
                    data = json.loads(content)
                    data = filter_event(data)
                    process_endpoints_event(data, app)
                    if r.raw.readline() != '\r\n':
                        print 'Wrong end block in listen_endpoints. Reconnect.'
                        r.raw.close()
                else:
                    if SERVICES_VERBOSE_LOG >= 3:
                        print 'CONNECTION CLOSED:', r.raw.closed
                        if not r.raw.closed:
                            print 'Content_length {0}'.format(content_length)
            gevent.sleep(0.1)
            if SERVICES_VERBOSE_LOG >= 2:
                print 'CLOSED. RECONNECT(Listen pods events)'
        except KeyboardInterrupt:
            break
        except Exception as e:
            print e.__repr__(), '...restarting listen endpoints...'
            gevent.sleep(0.2)