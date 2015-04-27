import gevent
import gevent.monkey
gevent.monkey.patch_all()
from psycogreen.gevent import patch_psycopg; patch_psycopg()

from werkzeug.wsgi import DispatcherMiddleware
from werkzeug.serving import run_with_reloader
from werkzeug.debug import DebuggedApplication
from gevent.wsgi import WSGIServer
import threading
import os

from kubedock import frontend, api

# This renders install scripts with latest settings at every start
import make_scripts

application = DispatcherMiddleware(
    frontend.create_app(),
    {'/api': api.create_app()}
)
# gevent.spawn(api.listen_endpoints)

if __name__ == "__main__":

    if os.environ.get('WERKZEUG_RUN_MAIN'):
        t = threading.Thread(target=api.listen_endpoints)
        t.daemon = True
        t.start()

    @run_with_reloader
    def run_server():
        http_server = WSGIServer(('', 5000), DebuggedApplication(application))
        http_server.serve_forever()
else:
    t = threading.Thread(target=api.listen_endpoints)
    t.daemon = True
    t.start()