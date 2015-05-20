import os
from datetime import timedelta

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

DEBUG = True
FLASKY_ADMIN = os.environ.get('AC_FLASKY_ADMIN', 'igor.bliss@gmail.com')

DB_ENGINE = 'postgresql+psycopg2' # more: http://docs.sqlalchemy.org/en/latest/dialects/#included-dialects
DB_USER = 'kuberdock'
DB_PASSWORD = 'kuberdock2go'
DB_NAME = 'kuberdock'

# Test whether it solves db bugs:
SQLALCHEMY_POOL_SIZE = 10

SQLALCHEMY_COMMIT_ON_TEARDOWN = True
#SQLALCHEMY_ECHO=True
SECRET_KEY = os.environ.get('SECRET_KEY', '37bliss91')

KUBERDOCK_INTERNAL_USER = 'kuberdock-internal'

# redis configs
REDIS_HOST = 'localhost'
REDIS_PORT = '6379'

CELERY_BROKER_URL = 'redis://localhost:6379',
CELERY_RESULT_BACKEND = 'redis://localhost:6379'

KUBE_API_VERSION = 'v1beta2'
KUBE_MASTER_URL = 'http://localhost:8080/api/{0}'.format(KUBE_API_VERSION)

# If None, defaults will be used
SSH_KEY_FILENAME = None

SERVICES_VERBOSE_LOG = 1

INFLUXDB_HOST = '127.0.0.1'
INFLUXDB_PORT = 8086
INFLUXDB_TABLE = 'stats'
INFLUXDB_USER = 'root'
INFLUXDB_PASSWORD = 'root'
INFLUXDB_DATABASE = 'cadvisor'

PD_SEPARATOR = '__SEP__'

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

NODE_INSTALL_LOG_FILE = '/var/log/kuberdock/node-install-log-{0}.log'

MASTER_IP = ''
MASTER_TOBIND_FLANNEL = 'enp0s5'
NODE_TOBIND_EXTERNAL_IPS = 'enp0s5'
NODE_TOBIND_FLANNEL = 'enp0s5'


# Import hoster settings in update case
import ConfigParser
config = ConfigParser.RawConfigParser(
    defaults=dict([(k, v) for k, v in globals().items() if k[0].isupper()])
)
try:
    config.read('/etc/sysconfig/kuberdock/kuberdock.conf')
    if not config.has_section('main'):
        config.add_section('main')
    DB_USER = config.get('main', 'DB_USER')
    DB_PASSWORD = config.get('main', 'DB_PASSWORD')
    DB_NAME = config.get('main', 'DB_NAME')
    MASTER_IP = config.get('main', 'MASTER_IP')
    MASTER_TOBIND_FLANNEL = config.get('main', 'MASTER_TOBIND_FLANNEL')
    NODE_TOBIND_EXTERNAL_IPS = config.get('main', 'NODE_TOBIND_EXTERNAL_IPS')
    NODE_TOBIND_FLANNEL = config.get('main', 'NODE_TOBIND_FLANNEL')
except ConfigParser.Error as e:
    print 'ConfigParser Error: ', e


# Import local settings
try:
    from local_settings import *
except ImportError:
    pass

# Only after local settings
DB_CONNECT_STRING = "{0}:{1}@127.0.0.1/{2}".format(DB_USER, DB_PASSWORD, DB_NAME)
SQLALCHEMY_DATABASE_URI = '{0}://{1}'.format(DB_ENGINE, DB_CONNECT_STRING)