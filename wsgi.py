import gevent
import gevent.monkey
gevent.monkey.patch_all()
from psycogreen.gevent import patch_psycopg; patch_psycopg()

import logging
from werkzeug.wsgi import DispatcherMiddleware
from werkzeug.serving import run_with_reloader
from werkzeug.debug import DebuggedApplication
from gevent.wsgi import WSGIServer


# Utility function for development =============================================
# http://projects.unbit.it/uwsgi/wiki/TipsAndTricks
import sys, code, inspect, os


class RestoredStandardInputContext(object):
    def __enter__(self):
        self.backup_stdin = os.dup(sys.stdin.fileno())
        os.dup2(sys.stdout.fileno(), sys.stdin.fileno())

    def __exit__(self, error_type, error, traceback):
        os.dup2(self.backup_stdin, sys.stdin.fileno())


def interact(locals=None, plain=False):
    with RestoredStandardInputContext():
        code.interact(local=locals or inspect.currentframe().f_back.f_locals)

try:
    __builtins__.__dict__['INTERACT'] = interact
    __builtins__['INTERACT'] = interact
except (TypeError, AttributeError):
    pass
# ==============================================================================


from kubedock import frontend, api, listeners
from kubedock.settings import PRE_START_HOOK_ENABLED, SENTRY_ENABLE
from kubedock.core import ExclusiveLock

front_app = frontend.create_app()
back_app = api.create_app()
application = DispatcherMiddleware(
    front_app,
    {'/api': back_app}
)
if SENTRY_ENABLE:
    import socket
    from kubedock.settings import MASTER_IP
    from kubedock.settings import SENTRY_DSN, SENTRY_PROCESSORS
    from kubedock.settings import SENTRY_EXCLUDE_PATHS
    from raven.contrib.flask import Sentry
    from kubedock.utils import get_version
    from kubedock.kapi.licensing import get_license_info
    authkey = get_license_info().get('auth_key', 'no installation id')
    hostname = "{}({})".format(socket.gethostname(), MASTER_IP)
    back_app.config['SENTRY_RELEASE'] = get_version('kuberdock')
    back_app.config['SENTRY_NAME'] = hostname
    back_app.config['SENTRY_TAGS'] = {'installation_id': authkey}
    back_app.config['SENTRY_PROCESSORS'] = SENTRY_PROCESSORS
    back_app.config['SENTRY_EXCLUDE_PATHS'] = SENTRY_EXCLUDE_PATHS
    sentry = Sentry(back_app, logging=True, level=logging.ERROR, dsn=SENTRY_DSN)
# Remove all locks remained after previous server run.
try:
    with back_app.app_context():
        ExclusiveLock.clean_locks()
except:
    pass

try:
    import uwsgi
except ImportError:
    pass
else:
    if uwsgi.worker_id() == 1:
        d = gevent.spawn(listeners.listen_pods, back_app)
        gevent.spawn(listeners.listen_services, back_app)
        f = gevent.spawn(listeners.listen_nodes, back_app)
        e = gevent.spawn(listeners.listen_events, back_app)
        if PRE_START_HOOK_ENABLED:
            j = gevent.spawn(api.pre_start_hook, back_app)
        k = gevent.spawn(api.populate_registered_hosts, back_app)
        #  l = gevent.spawn(listeners.listen_extended_statuses, back_app)
        s = gevent.spawn(listeners.listen_pod_states, back_app)

if __name__ == "__main__":

    import os
    if os.environ.get('WERKZEUG_RUN_MAIN'):
        d = gevent.spawn(listeners.listen_pods, back_app)
        gevent.spawn(listeners.listen_services, back_app)
        f = gevent.spawn(listeners.listen_nodes, back_app)
        e = gevent.spawn(listeners.listen_events, back_app)
        if PRE_START_HOOK_ENABLED:
            j = gevent.spawn(api.pre_start_hook, back_app)
        k = gevent.spawn(api.populate_registered_hosts, back_app)
        #  l = gevent.spawn(listeners.listen_extended_statuses, back_app)
        s = gevent.spawn(listeners.listen_pod_states, back_app)

    @run_with_reloader
    def run_server():
        http_server = WSGIServer(('', 5000), DebuggedApplication(application))
        http_server.serve_forever()
