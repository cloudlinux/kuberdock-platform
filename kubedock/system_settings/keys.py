
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

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
MAX_KUBES_TRIAL_USER = 'max_kubes_trial_user'

# DNS Management settings
KEY_PREFIX_DNS_MANAGEMENT = 'dns_management'
DNS_MANAGEMENT_SYSTEM = KEY_PREFIX_DNS_MANAGEMENT + '_system'
#    CPanel settings for dns management
#    Prefix for keys of Cpanel dns management settings
KEY_PREFIX_DNS_CPANEL = 'dns_management_cpanel_dnsonly'
DNS_MANAGEMENT_CPANEL_HOST = KEY_PREFIX_DNS_CPANEL + '_host'
DNS_MANAGEMENT_CPANEL_USER = KEY_PREFIX_DNS_CPANEL + '_user'
DNS_MANAGEMENT_CPANEL_TOKEN = KEY_PREFIX_DNS_CPANEL + '_token',

#    Route53 setting for dns management
#    Prefix for keys of Route53 dns management settings
KEY_PREFIX_DNS_ROUTE53 = 'dns_management_aws_route53'
DNS_MANAGEMENT_ROUTE53_ID = KEY_PREFIX_DNS_ROUTE53 + '_id'
DNS_MANAGEMENT_ROUTE53_SECRET = KEY_PREFIX_DNS_ROUTE53 + '_secret'

#    CloudFlare setting for dns management
#    Prefix for keys of CloudFlare dns management settings
KEY_PREFIX_DNS_CLOUDFLARE = 'dns_management_cloudflare'
DNS_MANAGEMENT_CLOUDFLARE_EMAIL = KEY_PREFIX_DNS_CLOUDFLARE + '_email'
DNS_MANAGEMENT_CLOUDFLARE_TOKEN = KEY_PREFIX_DNS_CLOUDFLARE + '_token'
