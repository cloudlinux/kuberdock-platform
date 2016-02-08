import gevent
import gevent.monkey
gevent.monkey.patch_all()
from psycogreen.gevent import patch_psycopg; patch_psycopg()

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
from kubedock.settings import PRE_START_HOOK_ENABLED
from kubedock.core import ExclusiveLock

front_app = frontend.create_app()
back_app = api.create_app()
application = DispatcherMiddleware(
    front_app,
    {'/api': back_app}
)

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
        f = gevent.spawn(listeners.listen_nodes, back_app)
        e = gevent.spawn(listeners.listen_events, back_app)
        if PRE_START_HOOK_ENABLED:
            j = gevent.spawn(api.pre_start_hook, back_app)
        k = gevent.spawn(api.populate_registered_hosts, back_app)
        l = gevent.spawn(listeners.listen_extended_statuses, back_app)
        s = gevent.spawn(listeners.listen_pod_states, back_app)

if __name__ == "__main__":

    import os
    if os.environ.get('WERKZEUG_RUN_MAIN'):
        f = gevent.spawn(listeners.listen_nodes, back_app)
        e = gevent.spawn(listeners.listen_events, back_app)
        if PRE_START_HOOK_ENABLED:
            j = gevent.spawn(api.pre_start_hook, back_app)
        k = gevent.spawn(api.populate_registered_hosts, back_app)
        l = gevent.spawn(listeners.listen_extended_statuses, back_app)
        s = gevent.spawn(listeners.listen_pod_states, back_app)

    @run_with_reloader
    def run_server():
        http_server = WSGIServer(('', 5000), DebuggedApplication(application))
        http_server.serve_forever()
