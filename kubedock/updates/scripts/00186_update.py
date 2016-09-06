from kubedock.core import db
from kubedock.system_settings import keys
from kubedock.system_settings.models import SystemSettings


NAMES = (
    keys.DNS_MANAGEMENT_CLOUDFLARE_EMAIL,
    keys.DNS_MANAGEMENT_CLOUDFLARE_TOKEN,
    keys.DNS_MANAGEMENT_CLOUDFLARE_CERTTOKEN,
)


def upgrade(upd, with_testing, *args, **kwargs):
    for setting_name in NAMES:
        SystemSettings.query.filter_by(name=setting_name).delete()
    db.session.add_all([
        SystemSettings(
            name=keys.DNS_MANAGEMENT_CLOUDFLARE_EMAIL,
            label='CloudFlare Email',
            description='Email for CloudFlare DNS management',
            placeholder='Enter CloudFlare Email',
            setting_group='domain'
        ),
        SystemSettings(
            name=keys.DNS_MANAGEMENT_CLOUDFLARE_TOKEN,
            label='CloudFlare Global API Key',
            description='Global API Key for CloudFlare DNS management',
            placeholder='Enter CloudFlare Global API Key',
            setting_group='domain'
        ),
        SystemSettings(
            name=keys.DNS_MANAGEMENT_CLOUDFLARE_CERTTOKEN,
            label='CloudFlare Origin CA Key',
            description='Origin CA Key for CloudFlare DNS management',
            placeholder='Enter CloudFlare Origin CA Key',
            setting_group='domain'
        ),
    ])
    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, *args, **kwargs):
    pass


def downgrade_node(upd, with_testing, exception, *args, **kwargs):
    pass
