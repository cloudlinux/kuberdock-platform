import os
from datetime import timedelta

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

DEBUG = True
FLASKY_ADMIN = os.environ.get('AC_FLASKY_ADMIN', 'igor.bliss@gmail.com')

DB_USER = 'kuberdock'
DB_PASSWORD = 'kuberdock2go'
DB_NAME = 'kuberdock'

SQLALCHEMY_COMMIT_ON_TEARDOWN = True

SECRET_KEY = os.environ.get('SECRET_KEY', '37bliss91')

if DEBUG:
    # root password to connect to nodes
    NODE_SSH_AUTH = ''
else:
    # ssh key filename to connect to nodes (in production)
    NODE_SSH_AUTH = ''

CELERY_BROKER_URL = 'redis://localhost:6379',
CELERY_RESULT_BACKEND = 'redis://localhost:6379'

MASTER_IP = ''

KUBE_API_VERSION = 'v1beta2'
KUBE_MASTER_URL = 'http://localhost:8080/api/{0}'.format(KUBE_API_VERSION)

INFLUXDB_HOST = '127.0.0.1'
INFLUXDB_PORT = 8086
INFLUXDB_TABLE = 'stats'
INFLUXDB_USER = 'root'
INFLUXDB_PASSWORD = 'root'
INFLUXDB_DATABASE = 'cadvisor'

CELERYBEAT_SCHEDULE = {
    'event-stream': {
        'task': 'kubedock.tasks.check_events',
        'schedule': timedelta(seconds=5),
    },
    'pull-hourly-stats': {
        'task': 'kubedock.tasks.pull_hourly_stats',
        'schedule': timedelta(minutes=5)
    }
}

ONLINE_LAST_MINUTES = 5

# TODO We need to allow change it during cluster setup
NODE_INET_IFACE = 'enp0s5'

LOCK_FILE_NAME = '/var/tmp/kuberdock.watch.pid'

# Import local settings
try:
    from local_settings import *
except ImportError:
    pass

# Only after local settings
DB_CONNECT_STRING = "{0}:{1}@127.0.0.1/{2}".format(DB_USER, DB_PASSWORD, DB_NAME)
SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://' + DB_CONNECT_STRING