import gevent
import gevent.monkey
gevent.monkey.patch_all()
from psycogreen.gevent import patch_psycopg; patch_psycopg()

from werkzeug.wsgi import DispatcherMiddleware
from werkzeug.serving import run_with_reloader
from werkzeug.debug import DebuggedApplication
from gevent.wsgi import WSGIServer

from kubedock import frontend, api

front_app = frontend.create_app()
back_app = api.create_app()
application = DispatcherMiddleware(
    front_app,
    {'/api': back_app}
)

try:
    import uwsgi
except ImportError:
    pass
else:
    if uwsgi.worker_id() == 1:
        g = gevent.spawn(api.listen_endpoints, back_app)

if __name__ == "__main__":

    import os
    if os.environ.get('WERKZEUG_RUN_MAIN'):
        g = gevent.spawn(api.listen_endpoints, back_app)

    @run_with_reloader
    def run_server():
        http_server = WSGIServer(('', 5000), DebuggedApplication(application))
        http_server.serve_forever()