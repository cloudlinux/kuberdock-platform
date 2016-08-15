"""System settings names"""

BILLING_TYPE = 'billing_type'
BILLING_URL = 'billing_url'
BILLING_USERNAME = 'billing_username'
BILLING_PASSWORD = 'billing_password'
SINGLE_SIGN_ON_SECRET_KEY = 'sso_secret_key'
EXTERNAL_SYSTEMS_AUTH_EMAIL = 'email'
PERSISTENT_DISK_MAX_SIZE = 'persitent_disk_max_size'
MAX_KUBES_PER_CONTAINER = 'max_kubes_per_container'
CPU_MULTIPLIER = 'cpu_multiplier'
MEMORY_MULTIPLIER = 'memory_multiplier'

# DNS Management settings
KEY_PREFIX_DNS_MANAGEMENT = 'dns_management'
DNS_MANAGEMENT_SYSTEM = KEY_PREFIX_DNS_MANAGEMENT + '_system'
#    CPanel settings for dns management
#    Prefix for keys of Cpanel dns management settings
KEY_PREFIX_DNS_CPANEL = 'dns_management_cpanel_dnsonly'
DNS_MANAGEMENT_CPANEL_HOST = KEY_PREFIX_DNS_CPANEL + '_host'
DNS_MANAGEMENT_CPANEL_USER = KEY_PREFIX_DNS_CPANEL + '_user'
DNS_MANAGEMENT_CPANEL_TOKEN = KEY_PREFIX_DNS_CPANEL + '_token',
