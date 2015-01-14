import os
from datetime import timedelta

DEBUG = True
FLASKY_ADMIN = 'igor.bliss@gmail.com'
SQLALCHEMY_DATABASE_URI='postgresql+psycopg2://kubedock:Iwb4gDo@127.0.0.1/kubedock'
SQLALCHEMY_COMMIT_ON_TEARDOWN = True

SECRET_KEY = os.environ.get('SECRET_KEY') or '37bliss91'

CELERY_BROKER_URL='redis://localhost:6379',
CELERY_RESULT_BACKEND='redis://localhost:6379'

INFLUXDB_HOST = 'localhost'
INFLUXDB_PORT = 8086
INFLUXDB_TABLE='stats'
INFLUXDB_USER='kubedock'
INFLUXDB_PASSWORD='Iwb4gDo'
INFLUXDB_DATABASE='cadvisor'

CELERYBEAT_SCHEDULE = {
    'event-stream': {
        'task': 'kubedock.tasks.check_events',
        'schedule': timedelta(seconds=5),
    },
}