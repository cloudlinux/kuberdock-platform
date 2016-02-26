import os
from datetime import timedelta

from celery.schedules import crontab

DEFAULT_TIMEZONE = 'UTC'

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

DEBUG = True
# With the following option turned on (by default) and in case of debug mode
# we will get a couple of 'idle in transaction' states
# in postgres if there will be unhandled exceptions in request processing.
# From docs:
# In debug mode Flask will not tear down a request on an exception immediately.
# Instead if will keep it alive so that the interactive debugger can still
# access it. This behavior can be controlled by the
# PRESERVE_CONTEXT_ON_EXCEPTION configuration variable.
PRESERVE_CONTEXT_ON_EXCEPTION = False
TEST = False
PRE_START_HOOK_ENABLED = False

DB_ENGINE = 'postgresql+psycopg2' # more: http://docs.sqlalchemy.org/en/latest/dialects/#included-dialects
DB_USER = 'kuberdock'
DB_PASSWORD = 'kuberdock2go'
DB_NAME = 'kuberdock'

# Test whether it solves db bugs:
SQLALCHEMY_POOL_SIZE = 20
SQLALCHEMY_POOL_RECYCLE = 3600
SQLALCHEMY_MAX_OVERFLOW = 20

MAX_KUBES_PER_CONTAINER = 10

SQLALCHEMY_COMMIT_ON_TEARDOWN = True
#SQLALCHEMY_ECHO=True
SECRET_KEY = os.environ.get('SECRET_KEY', '0987654321')

KUBERDOCK_INTERNAL_USER = 'kuberdock-internal'
TRIAL_KUBES = 10

EXTERNAL_UTILS_LANG = 'en_US.UTF-8'

# redis configs
REDIS_HOST = 'localhost'
REDIS_PORT = '6379'

CELERY_BROKER_URL = 'redis://localhost:6379',
CELERY_RESULT_BACKEND = 'redis://localhost:6379'

# Also used in yaml api version check
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

# separator for persisnet drive name - username after separator (LEGACY)
PD_SEPARATOR_USERNAME = '__SEP__'
# separator for persisnet drive name - user id after separator
PD_SEPARATOR_USERID = '__SEPID__'
#: Persistent drive namespace. Used to distinct drives for different kuberdock
# clusters on one storage backend. In case of CEPH it is equal to CEPH pool
# name for this cluster.
PD_NAMESPACE = ''
PD_NS_SEPARATOR = '/'
ERROR_TOKEN = 'ERROR:'
NODE_LOCAL_STORAGE_PREFIX = '/var/lib/kuberdock/storage'
DEFAULT_REGISTRY = 'https://registry-1.docker.io'
DEFAULT_IMAGES_URL = 'https://registry.hub.docker.com'
DOCKER_IMG_CACHE_TIMEOUT = timedelta(hours=4)

SSE_KEEPALIVE_INTERVAL = 15
SSE_POLL_INTERVAL = 0.5

ID_PATH = '/var/lib/kuberdock/installation-id'
STAT_URL = 'https://cln.cloudlinux.com/api/kd/validate.json'

CELERYBEAT_SCHEDULE = {
    'pull-hourly-stats': {
        'task': 'kubedock.tasks.pull_hourly_stats',
        'schedule': timedelta(minutes=5)
    },
    'fix-pods-timeline': {
        'task': 'kubedock.tasks.fix_pods_timeline',
        'schedule': timedelta(minutes=5)
    },
    # twice per day clean up persistent drives (for deleted users and drives
    # marked as deleted)
    'clean-deleted-persistent-drives': {
        'task': 'kubedock.tasks.clean_deleted_drives',
        'schedule': crontab(hour='*')
    },
    'send-stat': {
        'task': 'kubedock.tasks.send_stat',
        'schedule': timedelta(hours=24)
    },
    'unmap-temp-mapped-drives': {
        'task': 'kubedock.kapi.pstorage.unmap_temporary_mapped_ceph_drives_task',
        'schedule': crontab(minute='*')
    }
}

ONLINE_LAST_MINUTES = 5

NODE_INSTALL_LOG_FILE = '/var/log/kuberdock/node-install-log-{0}.log'
UPDATE_LOG_FILE = '/var/log/kuberdock/update.log'
MAINTENANCE_LOCK_FILE = '/var/lib/kuberdock/maintenance.lock'
UPDATES_RELOAD_LOCK_FILE = '/var/lib/kuberdock/updates-reload.lock'
UPDATES_PATH = '/var/opt/kuberdock/kubedock/updates/scripts'
KUBERDOCK_SERVICE = 'emperor.uwsgi'
KUBERDOCK_SETTINGS_FILE = '/etc/sysconfig/kuberdock/kuberdock.conf'

MASTER_IP = ''
MASTER_TOBIND_FLANNEL = 'enp0s5'
NODE_TOBIND_EXTERNAL_IPS = 'enp0s5'
NODE_TOBIND_FLANNEL = 'enp0s5'
NODE_INSTALL_TIMEOUT_SEC = 30*60    # 30 min
PD_NAMESPACE = ''

NODE_CEPH_AWARE_KUBERDOCK_LABEL = 'kuberdock-ceph-enabled'

ETCD_REGISTERED_HOSTS = 'http://127.0.0.1:4001/v2/keys/kuberdock/network/plugin/registered_hosts'

# Import hoster settings in update case

import ConfigParser
cp = ConfigParser.ConfigParser()
if cp.read(KUBERDOCK_SETTINGS_FILE):
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
        if cp.has_option('main', 'PD_NAMESPACE'):
            PD_NAMESPACE = cp.get('main', 'PD_NAMESPACE')


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
    from .amazon_settings import *
except ImportError:
    pass

CEPH = False
CEPH_POOL_NAME = 'rbd'
try:
    from .ceph_settings import *
    if CEPH and PD_NAMESPACE:
        CEPH_POOL_NAME = PD_NAMESPACE
except ImportError:
    pass
