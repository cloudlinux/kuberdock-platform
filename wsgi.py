import gevent
import gevent.monkey
gevent.monkey.patch_all()

import os
import signal
import psutil

from werkzeug.wsgi import DispatcherMiddleware
from werkzeug.serving import run_with_reloader
from werkzeug.debug import DebuggedApplication
from gevent.wsgi import WSGIServer

from kubedock import frontend, api
from kubedock.settings import LOCK_FILE_NAME

# This renders install scripts with latest settings at every start
import make_scripts

application = DispatcherMiddleware(
    frontend.create_app(),
    {'/api': api.create_app()}
)


def remove_lock(*args):
    try:
        os.remove(LOCK_FILE_NAME)
    except OSError:
        pass


def lock_and_listen():
    with open(LOCK_FILE_NAME, 'wt') as f:
        f.write(str(os.getpid()))
    gevent.spawn(api.listen_kub_events)
    signal.signal(signal.SIGINT, remove_lock)
    signal.signal(signal.SIGTERM, remove_lock)

if not os.path.exists(LOCK_FILE_NAME):
    lock_and_listen()
else:
    with open(LOCK_FILE_NAME, 'rt') as f:
        if not psutil.pid_exists(int(f.read())):
            lock_and_listen()

if __name__ == "__main__":

    @run_with_reloader
    def run_server():
        http_server = WSGIServer(('', 5000), DebuggedApplication(application))
        http_server.serve_forever()