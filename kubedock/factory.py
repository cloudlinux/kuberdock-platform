import os
import datetime

import pytz
from flask import Flask
from flask.json import JSONEncoder
from fabric.api import env

from .core import db, login_manager, influx_db
from kubedock.settings import SSH_KEY_FILENAME, SENTRY_ENABLE
from kubedock.billing.resolver import BillingFactory


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
    app.config.from_object('kubedock.settings')
    app.config.from_pyfile('settings.cfg', silent=True)
    app.config.from_object(settings_override)
    db.init_app(app)
    influx_db.init_app(app)
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
        from kubedock.settings import SENTRY_DSN, MASTER_IP
        from kubedock.utils import get_version

        class Celery(celery.Celery):

            def on_configure(self):
                hostname = "{}({})".format(socket.gethostname(), MASTER_IP)
                client = raven.Client(SENTRY_DSN, name=hostname,
                                      release=get_version('kuberdock'))

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
            with app.app_context():
                env.user = 'root'
                env.key_filename = SSH_KEY_FILENAME
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery
