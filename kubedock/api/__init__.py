import datetime
from .. import factory
from .. import sessions
from ..rbac import get_user_role
from ..settings import NODE_TOBIND_EXTERNAL_IPS, KUBE_MASTER_URL
from ..settings import SERVICES_VERBOSE_LOG
from ..core import ssh_connect, db
from ..utils import APIError, modify_node_ips, get_api_url

from flask.ext.login import current_user
from flask import jsonify
import json
import requests
import gevent
import os
import sys
import signal
import psutil
from rbac.context import PermissionDenied
from kubedock.settings import LOCK_FILE_NAME


def create_app(settings_override=None):
    skip_paths = []
    app = factory.create_app(__name__, __path__, settings_override)
    # app.session_interface = sessions.ManagedSessionInterface(
    #     sessions.DataBaseSessionManager(app.config['SECRET_KEY']),
    #     skip_paths, datetime.timedelta(days=1))
    
    # registering blueprings
    from .images import images
    from .pods import pods
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

    for bp in images, pods, stream, nodes, stats, users, notifications, \
              static_pages, usage, pricing, ippool, settings:
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




# TODO OLD algo for fallback ===================================================
def process_event(kub_event):
    try:
        kub_event = json.loads(kub_event)
    except ValueError:
        print 'Wrong event data in process_event: "{0}"'.format(kub_event)
        return True
    try:
        public_ip = kub_event['object']['labels']['kuberdock-public-ip']
    except KeyError:
        public_ip = False
    if (not public_ip) or (kub_event['type'] == "ADDED"):
        return False
    pod_ip = kub_event['object']['currentState'].get('podIP')
    if not pod_ip:
        return True
    annot_ports = json.loads(kub_event['object']['annotations']['kuberdock-ports'])

    ARPING = 'arping -I {0} -A {1} -c 10 -w 1'
    IP_ADDR = 'ip addr {0} {1}/32 dev {2}'
    IPTABLES = 'iptables -t nat -{0} PREROUTING ' \
               '-i {1} ' \
               '-p {2} -d {3} ' \
               '--dport {4} -j DNAT ' \
               '--to-destination {5}:{6}'
    if kub_event['type'] == "MODIFIED":
        # TODO when label removed from pod this becomes wrong
        # In case of 'release public ip' feature
        cmd = 'add'
    elif kub_event['type'] == "DELETED":
        cmd = 'del'
    else:
        print 'Skip event type %s' % kub_event['type']
        return False
    ssh, errors = ssh_connect(kub_event['object']['currentState']['host'])
    if errors:
        print errors
        return False
    ssh.exec_command(IP_ADDR.format(cmd, public_ip, NODE_TOBIND_EXTERNAL_IPS))
    if cmd == 'add':
        ssh.exec_command(ARPING.format(NODE_TOBIND_EXTERNAL_IPS, public_ip))
    for port_spec in annot_ports:
        containerPort = port_spec['targetPort']
        publicPort = port_spec.get('port', containerPort)
        protocol = port_spec.get('protocol', 'tcp')
        if cmd == 'add':
            print '==ADDED PORTS==', publicPort, containerPort, protocol
            i, o, e = ssh.exec_command(
                IPTABLES.format('C', NODE_TOBIND_EXTERNAL_IPS, protocol,
                                public_ip,
                                publicPort,
                                pod_ip,
                                containerPort))
            exit_status = o.channel.recv_exit_status()
            if exit_status != 0:
                ssh.exec_command(
                    IPTABLES.format('I', NODE_TOBIND_EXTERNAL_IPS, protocol,
                                    public_ip,
                                    publicPort,
                                    pod_ip,
                                    containerPort))
        else:
            print '==DELETED PORTS==', publicPort, containerPort, protocol
            ssh.exec_command(
                IPTABLES.format('D', NODE_TOBIND_EXTERNAL_IPS, protocol,
                                public_ip,
                                publicPort,
                                pod_ip,
                                containerPort))
    ssh.close()
    return False


def remove_lock(*args):
    try:
        os.remove(LOCK_FILE_NAME)
    except OSError:
        pass
    sys.exit(0)


def set_lock():
    with open(LOCK_FILE_NAME, 'wt') as f:
        f.write(str(os.getpid()))
    signal.signal(signal.SIGINT, remove_lock)
    signal.signal(signal.SIGTERM, remove_lock)


def listen_kub_events():
    if not os.path.exists(LOCK_FILE_NAME):
        set_lock()
    else:
        with open(LOCK_FILE_NAME, 'rt') as f:
            if not psutil.pid_exists(int(f.read())):
                set_lock()
            else:
                return
    # Dirty hack for gevent first switch
    r = None
    with gevent.Timeout(1, False):
        r = requests.get(KUBE_MASTER_URL + '/watch/pods', stream=True)
    if r is None:
        print 'WATCH TIMEOUT'
    while True:
        try:
            print '==START WATCH EVENTS== pid:', os.getpid()
            r = requests.get(KUBE_MASTER_URL + '/watch/pods', stream=True)
            if r.status_code != 200:
                gevent.sleep(0.2)
                print "CAN'T CONNECT TO KUBERNETES APISERVER WATCH. RECONNECT"
            while not r.raw.closed:
                content_length = r.raw.readline().strip()
                # print "LENGTH:", content_length
                if content_length not in ('0', ''):
                    content = r.raw.read(int(content_length, 16)).strip()
                    # TODO filter events func here
                    # Filter if pod ports already mapped etc.
                    # if 'podIP' in content:
                    #     print '==EVENT WITH PODIP=='
                    # else:
                    #     print '==EVENT=='
                    process_event(content)
                    if r.raw.readline() != '\r\n':
                        print 'Wrong end block in listen_kub_events. Reconnect.'
                        r.raw.close()
                else:
                    print 'CONNECTION CLOSED:', r.raw.closed
                    # if not r.raw.closed:
                    #     print 'Content_length {0}'.format(content_length)
            gevent.sleep(0.1)
            print 'CLOSED. RECONNECT(Listen pods events)'
        except KeyboardInterrupt:
            break
        except Exception as e:
            print e.__repr__(), '...restarting listen events...'
            gevent.sleep(0.2)
# // OLD algo for fallback =====================================================
























# TODO remove when migrate to v1beta3
SERVICES_V3_URL = get_api_url('services').replace('v1beta2', 'v1beta3/namespaces/default') + '/'


def filter_event(data):
    metadata = data['object']['metadata']
    if metadata['name'] in ('kubernetes', 'kubernetes-ro'):
        return None
    try:
        if metadata['labels']['kubernetes.io/cluster-service'] == 'true':
            return None
    except KeyError:
        pass

    return data


def process_endpoints_event(data):
    if data is None:
        return
    if SERVICES_VERBOSE_LOG >= 2:
        print 'ENDPOINT EVENT', data
    service_name = data['object']['metadata']['name']
    r = requests.get(SERVICES_V3_URL + service_name)
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
                res = modify_node_ips(state['assigned-to'], 'del',
                                      state['assigned-pod-ip'],
                                      state['assigned-public-ip'],
                                      service['spec']['ports'])
                if res is True:
                    del state['assigned-to']
                    del state['assigned-pod-ip']
                    service['metadata']['annotations']['public-ip-state'] = json.dumps(state)
                    r = requests.put(SERVICES_V3_URL + service_name, json.dumps(service))
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
        # TODO change to v3
        kub_pod = requests.get('http://127.0.0.1:8080/api/v1beta2/pods/' + podname).json()
        ports = service['spec']['ports']
        # TODO what to do here when pod yet not assigned to node at this moment?
        # skip only this event or reconnect(like now)?
        current_host = kub_pod['currentState']['host']
        pod_ip = pods[0]['addresses'][0]['IP']
        if not assigned_to:
            res = modify_node_ips(current_host, 'add', pod_ip, public_ip, ports)
            if res is True:
                state['assigned-to'] = current_host
                state['assigned-pod-ip'] = pod_ip
                service['metadata']['annotations']['public-ip-state'] = json.dumps(state)
                r = requests.put(SERVICES_V3_URL + service_name, json.dumps(service))
        else:
            if current_host != assigned_to:     # migrate pod
                if SERVICES_VERBOSE_LOG >= 2:
                    print 'MIGRATE POD'
                res = modify_node_ips(assigned_to, 'del',
                                      state['assigned-pod-ip'],
                                      public_ip, ports)
                if res is True:
                    res2 = modify_node_ips(current_host, 'add', pod_ip,
                                           public_ip, ports)
                    if res2 is True:
                        state['assigned-to'] = current_host
                        state['assigned-pod-ip'] = pod_ip
                        service['metadata']['annotations']['public-ip-state'] = json.dumps(state)
                        r = requests.put(SERVICES_V3_URL + service_name, service)
    else:   # more? replica case
        pass


def listen_endpoints():
    if not os.path.exists(LOCK_FILE_NAME):
        set_lock()
    else:
        with open(LOCK_FILE_NAME, 'rt') as f:
            if not psutil.pid_exists(int(f.read())):
                set_lock()
            else:
                return
    # Dirty hack for gevent first switch with uwsgi
    r = None
    with gevent.Timeout(1, False):
        r = requests.get(KUBE_MASTER_URL.replace('v1beta2', 'v1beta3') + '/watch/endpoints', stream=True)
    if r is None:
        if SERVICES_VERBOSE_LOG >= 2:
            print '=WATCH TIMEOUT='
    while True:
        try:
            if SERVICES_VERBOSE_LOG >= 1:
                print '==START WATCH ENDPOINTS== pid:', os.getpid()
            r = requests.get(KUBE_MASTER_URL.replace('v1beta2', 'v1beta3') + '/watch/endpoints', stream=True)
            if r.status_code != 200:
                gevent.sleep(0.1)
                print "CAN'T CONNECT TO KUBERNETES APISERVER WATCH. RECONNECT"
            while not r.raw.closed:
                content_length = r.raw.readline().strip()
                # print "LENGTH:", content_length
                if content_length not in ('0', ''):
                    content = r.raw.read(int(content_length, 16)).strip()
                    data = json.loads(content)
                    data = filter_event(data)
                    process_endpoints_event(data)
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