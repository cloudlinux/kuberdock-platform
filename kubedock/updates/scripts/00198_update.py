from kubedock.system_settings import keys
from kubedock.system_settings.models import SystemSettings
from kubedock.users.models import User, db


def setting_by_name(name):
    return SystemSettings.query \
        .filter_by(name=name).first()


def upgrade(upd, with_testing, *args, **kwargs):
    cpanel_host = setting_by_name(keys.DNS_MANAGEMENT_CPANEL_HOST)
    dns_management = setting_by_name(keys.DNS_MANAGEMENT_SYSTEM)
    if not cpanel_host.value and dns_management.value == 'cpanel_dnsonly':
        dns_management.value = 'No billing'
    dns_management.label = 'Select your DNS management system'
    cpanel_host.label = 'cPanel URL for DNS management'
    cpanel_host.placeholder = 'Enter URL for cPanel which serve your DNS ' \
                              'records'

    setting_by_name(keys.DNS_MANAGEMENT_CPANEL_USER) \
        .placeholder = 'Enter user for cPanel which serve your ' \
                       'DNS records'

    setting_by_name(keys.DNS_MANAGEMENT_CPANEL_TOKEN) \
        .placeholder = 'Enter token for cPanel which serve your ' \
                       'DNS records'

    setting_by_name(keys.BILLING_USERNAME).label = 'Billing admin username'
    setting_by_name(keys.BILLING_PASSWORD).label = 'Billing admin password'

    db.session.commit()

def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass