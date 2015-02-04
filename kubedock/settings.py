import os
from datetime import timedelta

DEBUG = True
FLASKY_ADMIN = os.environ.get('AC_FLASKY_ADMIN', 'igor.bliss@gmail.com')
SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://' + os.environ.get('AC_POSTGRES', 'kubedock:Iwb4gDo@127.0.0.1/kubedock')
SQLALCHEMY_COMMIT_ON_TEARDOWN = True

SECRET_KEY = os.environ.get('SECRET_KEY', '37bliss91')

if DEBUG:
    MINION_SSH_AUTH = 'admin'
else:
    MINION_SSH_AUTH = 'id_rsa'

CELERY_BROKER_URL = 'redis://localhost:6379',
CELERY_RESULT_BACKEND = 'redis://localhost:6379'

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
    'get-minions-logs': {
        'task': 'kubedock.tasks.get_minions_logs',
        'schedule': timedelta(seconds=1)
    }
}

ONLINE_LAST_MINUTES = 5
