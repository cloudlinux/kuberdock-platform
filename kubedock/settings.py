import os
from datetime import timedelta

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

DEBUG = True
TEST = False
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
TRIAL_KUBES = 10

# redis configs
REDIS_HOST = 'localhost'
REDIS_PORT = '6379'

CELERY_BROKER_URL = 'redis://localhost:6379',
CELERY_RESULT_BACKEND = 'redis://localhost:6379'

KUBE_API_VERSION = 'v1'
KUBE_MASTER_URL = 'http://localhost:8080/api/'

# If None, defaults will be used
SSH_KEY_FILENAME = '/var/lib/nginx/.ssh/id_rsa'

SERVICES_VERBOSE_LOG = 1
PODS_VERBOSE_LOG = 1

INFLUXDB_HOST = '127.0.0.1'
INFLUXDB_PORT = 8086
INFLUXDB_TABLE = 'stats'
INFLUXDB_USER = 'root'
INFLUXDB_PASSWORD = 'root'
INFLUXDB_DATABASE = 'cadvisor'

# Port to access elasticsearch via rest api
ELASTICSEARCH_REST_PORT = 9200

PD_SEPARATOR = '__SEP__'
PORTS_TO_RESTRICT = [ELASTICSEARCH_REST_PORT]
NODE_LOCAL_STORAGE_PREFIX = '/var/lib/kuberdock/storage'
CELERYBEAT_SCHEDULE = {
    'pull-hourly-stats': {
        'task': 'kubedock.tasks.pull_hourly_stats',
        'schedule': timedelta(minutes=5)
    },
    'fix-pods-timeline': {
        'task': 'kubedock.tasks.fix_pods_timeline',
        'schedule': timedelta(minutes=5)
    }
}

ONLINE_LAST_MINUTES = 5

NODE_INSTALL_LOG_FILE = '/var/log/kuberdock/node-install-log-{0}.log'
UPDATE_LOG_FILE = '/var/log/kuberdock/update.log'
MAINTENANCE_LOCK_FILE = '/var/lib/kuberdock/maintenance.lock'
UPDATES_RELOAD_LOCK_FILE = '/var/lib/kuberdock/updates-reload.lock'
UPDATES_PATH = '/var/opt/kuberdock/kubedock/updates/scripts'
KUBERDOCK_SERVICE = 'emperor.uwsgi'

MASTER_IP = ''
MASTER_TOBIND_FLANNEL = 'enp0s5'
NODE_TOBIND_EXTERNAL_IPS = 'enp0s5'
NODE_TOBIND_FLANNEL = 'enp0s5'
NODE_INSTALL_TIMEOUT_SEC = 30*60    # 30 min


# Import hoster settings in update case

import ConfigParser
cp = ConfigParser.ConfigParser()
if cp.read('/etc/sysconfig/kuberdock/kuberdock.conf'):
    if cp.has_section('main'):
        if cp.has_option('main', 'DB_USER'):
            DB_USER = cp.get('main', 'DB_USER')
        if cp.has_option('main', 'DB_PASSWORD'):
            DB_PASSWORD = cp.get('main', 'DB_PASSWORD')
        if cp.has_option('main', 'DB_NAME'):
            DB_NAME = cp.get('main', 'DB_NAME')
        if cp.has_option('main', 'MASTER_IP'):
            MASTER_IP = cp.get('main', 'MASTER_IP')
        if cp.has_option('main', 'MASTER_TOBIND_FLANNEL'):
            MASTER_TOBIND_FLANNEL = cp.get('main', 'MASTER_TOBIND_FLANNEL')
        if cp.has_option('main', 'NODE_TOBIND_EXTERNAL_IPS'):
            NODE_TOBIND_EXTERNAL_IPS = cp.get('main', 'NODE_TOBIND_EXTERNAL_IPS')
        if cp.has_option('main', 'NODE_TOBIND_FLANNEL'):
            NODE_TOBIND_FLANNEL = cp.get('main', 'NODE_TOBIND_FLANNEL')

#import ConfigParser
#config = ConfigParser.RawConfigParser(
#    defaults=dict([(k, v) for k, v in globals().items() if k[0].isupper()])
#)
#try:
#    config.read('/etc/sysconfig/kuberdock/kuberdock.conf')
#    if not config.has_section('main'):
#        config.add_section('main')
#    DB_USER = config.get('main', 'DB_USER')
#    DB_PASSWORD = config.get('main', 'DB_PASSWORD')
#    DB_NAME = config.get('main', 'DB_NAME')
#    MASTER_IP = config.get('main', 'MASTER_IP')
#    MASTER_TOBIND_FLANNEL = config.get('main', 'MASTER_TOBIND_FLANNEL')
#    NODE_TOBIND_EXTERNAL_IPS = config.get('main', 'NODE_TOBIND_EXTERNAL_IPS')
#    NODE_TOBIND_FLANNEL = config.get('main', 'NODE_TOBIND_FLANNEL')
#except ConfigParser.Error as e:
#    print 'ConfigParser Error: ', e


# Import local settings
try:
    from local_settings import *
except ImportError:
    pass

# Only after local settings
DB_CONNECT_STRING = "{0}:{1}@127.0.0.1/{2}".format(DB_USER, DB_PASSWORD, DB_NAME)
SQLALCHEMY_DATABASE_URI = '{0}://{1}'.format(DB_ENGINE, DB_CONNECT_STRING)

AWS = False
try:
    from amazon_settings import *
except ImportError:
    pass

CEPH=False
try:
    from ceph_settings import *
except ImportError:
    pass
