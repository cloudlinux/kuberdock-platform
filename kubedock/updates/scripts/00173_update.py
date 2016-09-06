from kubedock.core import db
from kubedock.system_settings.models import SystemSettings

NAMES = (
    'email',
)


def upgrade(upd, with_testing):
    for setting_name in NAMES:
        SystemSettings.query.filter_by(name=setting_name).delete()
    db.session.add_all([
        SystemSettings(
            name='email', label='Email for external services',
            setting_group='general',
            placeholder='Enter an email address',
            description=('Cluster-wide email that is required for cluster '
                         'authentication in external services.')),
    ])
    db.session.commit()


def downgrade(upd, with_testing, error):
    for setting_name in NAMES:
        SystemSettings.query.filter_by(name=setting_name).delete()
