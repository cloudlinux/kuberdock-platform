import datetime
#from ..utils import JSONEncoder
from .. import factory
from .. import sessions
from ..rbac import get_user_role
from ..settings import NODE_INET_IFACE, KUBE_MASTER_URL
from ..core import ssh_connect

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
    app.session_interface = sessions.ManagedSessionInterface(
        sessions.DataBaseSessionManager(app.config['SECRET_KEY']),
        skip_paths, datetime.timedelta(days=1))
    
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


class APIError(Exception):
    def __init__(self, message, status_code=400):
        if isinstance(message, (list, tuple, dict)):
            message = str(message)
        self.message = message
        self.status_code = status_code


def on_app_error(e):
    return jsonify({'status': e.message}), e.status_code


def on_permission_denied(e):
    message = e.kwargs['message'] or 'Denied to {0}'.format(get_user_role())
    return on_app_error(APIError('Error. {0}'.format(message), status_code=403))


def on_404(e):
    return on_app_error(APIError('Not found', status_code=404))


def process_event(kub_event):
    # TODO handle pods migrations
    try:
        kub_event = json.loads(kub_event.strip())
    except ValueError:
        print 'Wrong event data in process_event: "{0}"'.format(kub_event)
        return True
    public_ip = kub_event['object']['labels'].get('kuberdock-public-ip')
    if (not public_ip) or (kub_event['type'] == "ADDED"):
        return False
    pod_ip = kub_event['object']['currentState'].get('podIP')
    if not pod_ip:
        return True
    conts = kub_event['object']['desiredState']['manifest']['containers']

    ARPING = 'arping -I {0} -A {1} -c 10 -w 1'
    IP_ADDR = 'ip addr {0} {1}/32 dev {2}'
    IPTABLES = 'iptables -t nat -{0} PREROUTING ' \
               '-i {1} ' \
               '-p tcp -d {2} ' \
               '--dport {3} -j DNAT ' \
               '--to-destination {4}:{3}'
    if kub_event['type'] == "MODIFIED":
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
    ssh.exec_command(IP_ADDR.format(cmd, public_ip, NODE_INET_IFACE))
    if cmd == 'add':
        ssh.exec_command(ARPING.format(NODE_INET_IFACE, public_ip))
    for container in conts:
        for port_spec in container['ports']:
            if cmd == 'add':
                i, o, e = ssh.exec_command(
                    IPTABLES.format('C', NODE_INET_IFACE, public_ip,
                                    port_spec['containerPort'],
                                    pod_ip))
                exit_status = o.channel.recv_exit_status()
                if exit_status != 0:
                    ssh.exec_command(
                        IPTABLES.format('I', NODE_INET_IFACE, public_ip,
                                        port_spec['containerPort'],
                                        pod_ip))
            else:
                ssh.exec_command(
                    IPTABLES.format('D', NODE_INET_IFACE, public_ip,
                                    port_spec['containerPort'],
                                    pod_ip))
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
    while True:
        try:
            r = requests.get(KUBE_MASTER_URL + '/watch/pods', stream=True)
            # TODO if listen endpoinds must skip 3 events
            # (1 last +  2 * kubernetes endpoints)
            # maybe more if we have more services
            while not r.raw.closed:
                content_length = r.raw.readline()
                if content_length not in ('0', ''):
                    # TODO due to watch bug:
                    needs_reconnect = process_event(r.raw.readline())
                    if needs_reconnect:
                        r.raw.close()
                        gevent.sleep(0.2)
                        break
                    r.raw.readline()
            # print 'RECONNECT(Listen pods events)'
        except KeyboardInterrupt:
            break
        except Exception as e:
            print e.__repr__(), '...restarting listen events...'
            gevent.sleep(0.2)