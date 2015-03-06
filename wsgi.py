import gevent
import gevent.monkey
gevent.monkey.patch_all()

from werkzeug.wsgi import DispatcherMiddleware
from werkzeug.serving import run_with_reloader
from werkzeug.debug import DebuggedApplication
from gevent.wsgi import WSGIServer

from kubedock import frontend, api
from kubedock.core import listen_kub_events

# This renders install scripts with latest settings at every start
import make_scripts

application = DispatcherMiddleware(
    frontend.create_app(),
    {'/api': api.create_app()}
)
gevent.spawn(listen_kub_events)

if __name__ == "__main__":

    @run_with_reloader
    def run_server():
        http_server = WSGIServer(('', 5000), DebuggedApplication(application))
        http_server.serve_forever()