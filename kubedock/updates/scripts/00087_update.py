"""Introduce PD namespaces"""
import ConfigParser

from kubedock.pods.models import PersistentDisk, db
from kubedock.kapi import pstorage 
from kubedock.settings import (
    MASTER_IP, KUBERDOCK_SETTINGS_FILE, CEPH, PD_NS_SEPARATOR)


OLD_DEFAULT_CEPH_POOL = 'rbd'


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrade namespaces for PD...')
    config = ConfigParser.RawConfigParser()
    config.read(KUBERDOCK_SETTINGS_FILE)
    ns = MASTER_IP
    if not config.has_option('main', 'PD_NAMESPACE'):
        if CEPH:
            # Store default CEPH pool as namespace. It already was used
            # by KD cluster, so we will not change it.
            ns = OLD_DEFAULT_CEPH_POOL
        config.set('main', 'PD_NAMESPACE', ns)
        with open(KUBERDOCK_SETTINGS_FILE, 'wb') as fout:
            config.write(fout)

    if CEPH:
        # Set 'rbd' for all existing ceph drives, because it was a default pool
        PersistentDisk.query.filter(
            ~PersistentDisk.drive_name.contains(PD_NS_SEPARATOR)
        ).update(
            {PersistentDisk.drive_name: \
                OLD_DEFAULT_CEPH_POOL + PD_NS_SEPARATOR + \
                PersistentDisk.drive_name
            },
            synchronize_session=False
        )
        db.session.commit()
        pstorage.check_namespace_exists(namespace=ns)


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Downgrade ...')
    if CEPH:
        for pd in PersistentDisk.query:
            parts = PersistentDisk.drive_name.split(PD_NS_SEPARATOR, 1)
            if len(parts) > 1:
                PersistentDisk.drive_name = parts[-1]
        db.session.commit()
