import os
from celery import Celery
from flask import Flask

from .core import db, login_manager, influx_db
#from .utils import register_blueprints

def create_app(package_name, package_path, settings_override=None):
    app = Flask(package_name, instance_relative_config=True)
    app.config.from_object('kubedock.settings')
    app.config.from_pyfile('settings.cfg', silent=True)
    app.config.from_object(settings_override)
    db.init_app(app)
    influx_db.init_app(app)
    login_manager.init_app(app)
    #register_blueprints(app, package_name, package_path)
    return app


def make_celery(app=None):
    if app is None:
        app = create_app('kubedock', os.path.dirname(__file__))
    celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery