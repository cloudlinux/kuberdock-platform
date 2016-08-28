from kubedock.core import db
from kubedock.system_settings import keys
from kubedock.system_settings.models import SystemSettings


NAMES = (
    keys.DNS_MANAGEMENT_ROUTE53_ID,
    keys.DNS_MANAGEMENT_ROUTE53_SECRET,
)


def upgrade(upd, with_testing, *args, **kwargs):
    for setting_name in NAMES:
        SystemSettings.query.filter_by(name=setting_name).delete()
    db.session.add_all([
        SystemSettings(
            name=keys.DNS_MANAGEMENT_ROUTE53_ID,
            label='AWS Access Key ID',
            description='AWS Access Key ID for Route 53 DNS management',
            placeholder='Enter AWS Access Key ID'
        ),
        SystemSettings(
            name=keys.DNS_MANAGEMENT_ROUTE53_SECRET,
            label='AWS Secret Access Key',
            description='AWS Secret Access Key for Route 53 DNS management',
            placeholder='Enter AWS Secret Access Key'
        ),
    ])
    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, *args, **kwargs):
    pass


def downgrade_node(upd, with_testing, exception, *args, **kwargs):
    pass
