from datetime import timedelta
from urlparse import urlparse

from kubedock.updates import helpers
from kubedock.core import ConnectionPool
from kubedock.system_settings.fixtures import add_system_settings
from kubedock.system_settings.models import db, SystemSettings


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Update system settings scheme...')
    helpers.upgrade_db(revision='46bba639e6fb')

    redis = ConnectionPool.get_connection()

    billing_apps_link = SystemSettings.get_by_name('billing_apps_link')
    persitent_disk_max_size = SystemSettings.get_by_name('persitent_disk_max_size')

    # backup for downgrade
    if not redis.get('old_billing_apps_link'):
        redis.set('old_billing_apps_link', billing_apps_link or '',
                  ex=int(timedelta(days=7).total_seconds()))
    if not redis.get('old_persitent_disk_max_size'):
        redis.set('old_persitent_disk_max_size', persitent_disk_max_size,
                  ex=int(timedelta(days=7).total_seconds()))

    billing_url = (urlparse(billing_apps_link)._replace(path='', query='',
                                                        params='').geturl()
                   if billing_apps_link else None)
    SystemSettings.query.delete()
    add_system_settings()
    SystemSettings.set_by_name(
        'persitent_disk_max_size', persitent_disk_max_size, commit=False)
    SystemSettings.set_by_name('billing_url', billing_url, commit=False)
    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrade system_settings scheme...')

    redis = ConnectionPool.get_connection()
    SystemSettings.query.delete()
    db.session.add_all([
        SystemSettings(name='billing_apps_link',
                       label='Link to billing system script',
                       description='Link to predefined application request processing script',
                       placeholder='http://whmcs.com/script.php',
                       value=redis.get('old_billing_apps_link')),
        SystemSettings(name='persitent_disk_max_size',
                       value=redis.get('old_persitent_disk_max_size'),
                       label='Persistent disk maximum size',
                       description='maximum capacity of a user container persistent disk in GB',
                       placeholder='Enter value to limit PD size')
    ])
    db.session.commit()

    helpers.downgrade_db(revision='27ac98113841')
