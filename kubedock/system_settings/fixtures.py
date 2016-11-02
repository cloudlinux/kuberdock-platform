from ..utils import randstr
from .models import SystemSettings, db
from . import keys


def add_system_settings():
    db.session.add_all([
        SystemSettings(
            name=keys.BILLING_TYPE, label='Select your billing system',
            value='No billing',
            setting_group='billing'),
        SystemSettings(
            name=keys.BILLING_URL, label='Link to billing',
            placeholder='http://domain.name',
            description=('Used to access billing API and to create link to '
                         'predefined application request processing script'),
            setting_group='billing'),
        SystemSettings(
            name=keys.BILLING_USERNAME, label='Billing admin username',
            placeholder='admin',
            setting_group='billing'),
        SystemSettings(
            name=keys.BILLING_PASSWORD, label='Billing admin password',
            placeholder='password',
            setting_group='billing'),
        SystemSettings(
            name=keys.SINGLE_SIGN_ON_SECRET_KEY,
            label='Secret key for Single sign-on',
            placeholder='Enter a secret key', value=randstr(16),
            description=('Used for Single sign-on. Must be shared between '
                         'Kuberdock and billing system or other 3rd party '
                         'application.'),
            setting_group='general'),
        SystemSettings(
            name=keys.EXTERNAL_SYSTEMS_AUTH_EMAIL,
            label='Email for external services',
            placeholder='Enter an email address',
            description=('Cluster-wide email that is required for cluster '
                         'authentication in external services.'),
            setting_group='general'),
        SystemSettings(
            name=keys.PERSISTENT_DISK_MAX_SIZE, value='10',
            label='Persistent disk maximum size',
            description='Maximum capacity of a user container persistent '
                        'disk in GB',
            placeholder='Enter value to limit PD size',
            setting_group='general'),
        SystemSettings(
            name=keys.MAX_KUBES_PER_CONTAINER, value='64',
            label='Maximum number of kubes per container',
            description="Changing this value won't affect existing containers",
            placeholder='Enter value to limit number of kubes per container',
            setting_group='general'),
        SystemSettings(
            name=keys.CPU_MULTIPLIER, value='8',
            label='CPU multiplier',
            description='Cluster CPU multiplier',
            placeholder='Enter value for CPU multiplier',
            setting_group='general'),
        SystemSettings(
            name=keys.MEMORY_MULTIPLIER, value='4',
            label='Memory multiplier',
            description='Cluster Memory multiplier',
            placeholder='Enter value for Memory multiplier',
            setting_group='general'),
        SystemSettings(
            name=keys.MAX_KUBES_TRIAL_USER, value='5',
            label='Kubes limit for Trial user',
            placeholder='Enter Kubes limit for Trial user',
            setting_group='general'
        ),
        SystemSettings(
            name=keys.DNS_MANAGEMENT_SYSTEM,
            label='Select your DNS management system',
            value='No provider',
            setting_group='domain'),
        SystemSettings(
            name=keys.DNS_MANAGEMENT_CPANEL_HOST,
            label='cPanel URL for DNS management',
            description='cPanel URL that used for DNS management',
            placeholder='Enter URL for cPanel which serve your DNS records',
            setting_group='domain'),
        SystemSettings(
            name=keys.DNS_MANAGEMENT_CPANEL_USER,
            label='cPanel user name for DNS management',
            description='cPanel user that used for DNS management auth',
            placeholder='Enter user for cPanel which serve your DNS records',
            setting_group='domain'),
        SystemSettings(
            name=keys.DNS_MANAGEMENT_CPANEL_TOKEN,
            label='cPanel user token for DNS management',
            description='cPanel token that used for DNS management auth',
            placeholder='Enter token for cPanel which serve your DNS records',
            setting_group='domain'),
        SystemSettings(
            name=keys.DNS_MANAGEMENT_ROUTE53_ID,
            label='AWS Access Key ID',
            description='AWS Access Key ID for Route 53 DNS management',
            placeholder='Enter AWS Access Key ID',
            setting_group='domain'
        ),
        SystemSettings(
            name=keys.DNS_MANAGEMENT_ROUTE53_SECRET,
            label='AWS Secret Access Key',
            description='AWS Secret Access Key for Route 53 DNS management',
            placeholder='Enter AWS Secret Access Key',
            setting_group='domain'
        ),
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
