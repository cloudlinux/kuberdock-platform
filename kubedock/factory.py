import datetime
import os

import pytz
from fabric.api import env
from flask import Flask
from flask.json import JSONEncoder

from kubedock.billing.resolver import BillingFactory
from kubedock.core import db, login_manager
from kubedock.settings import SSH_KEY_FILENAME, SENTRY_ENABLE


class APIJSONEncoder(JSONEncoder):
    """Fix datetime conversion in flask.jsonify, 'tojson' jinja filter.
    All internal datetime fields are treated as UTC time. UTC offset will
    be added to all serialized to json datetime objects.
    Output date&time serialized strings will be looked like
    '2015-11-12T06:41:02+00:00'
    """
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            if obj.tzinfo is None:
                obj = obj.replace(tzinfo=pytz.UTC)
            return obj.isoformat()
        if isinstance(obj, datetime.date):
            return obj.isoformat()
        return JSONEncoder.default(self, obj)


def create_app(package_name, package_path, settings_override=None):
    app = Flask(package_name, instance_relative_config=True)
    app.url_map.strict_slashes = False
    app.config.from_object('kubedock.settings')
    app.config.from_pyfile('settings.cfg', silent=True)
    app.config.from_object(settings_override)
    db.init_app(app)
    login_manager.init_app(app)
    BillingFactory().init_app(app)
    app.json_encoder = APIJSONEncoder
    return app


def make_celery(app=None):
    if app is None:
        app = create_app('kubedock', os.path.dirname(__file__))
    if SENTRY_ENABLE:
        import socket
        import celery
        import raven
        from raven.contrib.celery import register_signal
        from raven.contrib.celery import register_logger_signal
        from kubedock.settings import MASTER_IP
        from kubedock.settings import SENTRY_DSN, SENTRY_EXCLUDE_PATHS
        from kubedock.settings import SENTRY_PROCESSORS
        from kubedock.utils import get_version
        from kubedock.kapi.licensing import get_license_info
        authkey = get_license_info().get('auth_key', 'no installation id')
        from celery.utils import log

        class Celery(celery.Celery):

            def on_configure(self):
                hostname = "{}({})".format(socket.gethostname(), MASTER_IP)
                tags = {'installation_id': authkey}
                client = raven.Client(SENTRY_DSN, name=hostname,
                                      release=get_version('kuberdock'),
                                      tags=tags, processors=SENTRY_PROCESSORS,
                                      exclude_paths=SENTRY_EXCLUDE_PATHS)

                # register a custom filter to filter out duplicate logs
                register_logger_signal(client)

                # hook into the Celery error handler
                register_signal(client)
    else:
        from celery import Celery
    celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True
        flask_app = app

        def __call__(self, *args, **kwargs):
            if self.request.called_directly:
                return TaskBase.__call__(self, *args, **kwargs)
            else:
                with app.app_context():
                    env.user = 'root'
                    env.key_filename = SSH_KEY_FILENAME
                    return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery
