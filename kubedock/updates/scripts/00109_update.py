import json
from datetime import timedelta

from kubedock.updates import helpers
from kubedock.core import ConnectionPool, db
from kubedock.system_settings.fixtures import add_system_settings
from kubedock.system_settings.models import SystemSettings


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Update system settings scheme...')
    helpers.upgrade_db()

    redis = ConnectionPool.get_connection()
    old_settings = SystemSettings.get_all()

    # backup for downgrade
    if not redis.get('old_system_settings'):
        redis.set('old_system_settings', json.dumps(old_settings),
                  ex=int(timedelta(days=7).total_seconds()))

    SystemSettings.query.delete()
    add_system_settings()
    for param in old_settings:
        SystemSettings.set_by_name(param.get('name'), param.get('value'), commit=False)
    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrade system_settings scheme...')

    redis = ConnectionPool.get_connection()
    old_settings = redis.get('old_system_settings')
    if old_settings:
        # restore old settings
        SystemSettings.query.delete()
        for param in json.loads(old_settings):
            db.session.add(
                SystemSettings(name=param.get('name'),
                               label=param.get('label'),
                               description=param.get('description'),
                               placeholder=param.get('placeholder'),
                               options=json.dumps(param.get('options')),
                               value=param.get('value')))
        db.session.commit()
