import shutil
from os import path

from kubedock.updates.helpers import stop_service, start_service

old = '/index.txt'
new = '/var/lib/kuberdock/k8s2etcd_resourceVersion'
service_name = 'kuberdock-k8s2etcd'


def upgrade(upd, with_testing, *args, **kwargs):
    # Move index file of k8s2etcd service from / to /var/lib/kuberdock
    try:
        stop_service(service_name)
        if path.isfile(old) and not path.isfile(new):
            shutil.move(old, new)
    finally:
        start_service(service_name)


def downgrade(*args, **kwars):
    try:
        stop_service(service_name)
        if path.isfile(new) and not path.isfile(old):
            shutil.move(new, old)
    finally:
        start_service(service_name)
