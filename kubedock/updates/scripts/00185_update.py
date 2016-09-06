from kubedock.core import db
from kubedock.system_settings import keys
from kubedock.system_settings.models import SystemSettings


def upgrade(upd, with_testing, *args, **kwargs):
    SystemSettings.query.filter_by(name=keys.MAX_KUBES_TRIAL_USER).delete()
    db.session.add_all([
        SystemSettings(
            name=keys.MAX_KUBES_TRIAL_USER, value='5',
            label='Kubes limit for Trial user',
            placeholder='Enter Kubes limit for Trial user',
            setting_group='general'
        ),
    ])
    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, *args, **kwargs):
    pass


def downgrade_node(upd, with_testing, exception, *args, **kwargs):
    pass
