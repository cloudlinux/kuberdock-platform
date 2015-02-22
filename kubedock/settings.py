import os
from datetime import timedelta

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

DEBUG = True
FLASKY_ADMIN = os.environ.get('AC_FLASKY_ADMIN', 'igor.bliss@gmail.com')
SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://' + os.environ.get('AC_POSTGRES', 'kubedock:Iwb4gDo@127.0.0.1/kubedock')
SQLALCHEMY_COMMIT_ON_TEARDOWN = True

SECRET_KEY = os.environ.get('SECRET_KEY', '37bliss91')

if DEBUG:
    NODE_SSH_AUTH = 'admin'
else:
    NODE_SSH_AUTH = 'id_rsa'

CELERY_BROKER_URL = 'redis://localhost:6379',
CELERY_RESULT_BACKEND = 'redis://localhost:6379'

KUBE_API_VERSION = 'v1beta1'
KUBE_MASTER_URL = 'http://localhost:8080/api/{0}'.format(KUBE_API_VERSION)

INFLUXDB_HOST = '127.0.0.1'
INFLUXDB_PORT = 8086
INFLUXDB_TABLE = 'stats'
INFLUXDB_USER = 'dbadmin'
INFLUXDB_PASSWORD = 'Iwb4gDo'
INFLUXDB_DATABASE = 'cadvisor'

CELERYBEAT_SCHEDULE = {
    'event-stream': {
        'task': 'kubedock.tasks.check_events',
        'schedule': timedelta(seconds=5),
    },
    'pull-hourly-stats': {
        'task': 'kubedock.tasks.pull_hourly_stats',
        'schedule': timedelta(minutes=5)
    },
    'get-nodes-logs': {
        'task': 'kubedock.tasks.get_nodes_logs',
        'schedule': timedelta(seconds=1)
    }
}

ONLINE_LAST_MINUTES = 5
