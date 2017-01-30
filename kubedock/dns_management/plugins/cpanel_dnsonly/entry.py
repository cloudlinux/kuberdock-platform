
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

from flask import current_app

from .dnsonly_client import API
from ... import exceptions


def delete_type_A_record(domain, **kwargs):
    """
    Delete A record to domain

    :param domain: domain which will have been deleted
    :param dict kwargs: additional params such as email and
        token for access to Cloudflare API
    :return: None
    """

    main_domain = extract_main_domain(domain)
    api = API(**kwargs)

    try:
        zone = api.get_zone(main_domain)
    except exceptions.ZoneDoesNotExist:
        raise ValueError("Zone for domain {} not found. "
                         "Need to configure the zone".format(domain))

    for dns_record in zone.records():
        # dns record without end point
        if dns_record.type == 'A' and domain == dns_record.name[:-1]:
            dns_record.delete()


def delete_type_CNAME_record(domain, **kwargs):
    """
    Delete CNAME record to domain

    :param domain: domain which will have been deleted
    :param dict kwargs: additional params such as email and
        token and certtoken for access to Cloudflare API
    :return: None
    """
    main_domain = extract_main_domain(domain)
    api = API(**kwargs)

    zone = api.get_zone(main_domain)
    for record in zone.records():
        # dns record without end point
        if record.type == 'CNAME' and domain == record.name[:-1]:
            record.delete()


def create_or_update_type_A_record(domain, new_ips, **kwargs):
    """
    Create or update A record for IP addresses of load
    balancer

    :param str domain: New subdomain name in existing zone
    :param list new_ips: IP addresses of load balancer
    :param dict kwargs: additional params such as token for access WHM API
    :return:
    """
    main_domain = extract_main_domain(domain)
    api = API(**kwargs)

    try:
        zone = api.get_zone(main_domain)
    except exceptions.ZoneDoesNotExist:
        raise ValueError("Zone for domain {} not found. "
                         "Need to configure the zone".format(domain))

    for dns_record in zone.records():
        # dns record without end point
        if dns_record.type == 'A' and domain == dns_record.name[:-1]:
            if dns_record.address not in new_ips:
                # dnsonly can assign only one ip address
                # here you can use roundrobin for many ip addresses
                new_ip = new_ips[0]

                dns_record.address = new_ip
                dns_record.edit()

                current_app.logger.debug(
                    'Replace record in zone "{zone}" with '
                    'domain "{domain}" '
                    'and ip "{ips}"'.format(
                        zone=zone.name, domain=domain, ips=new_ip
                    ))

            else:
                current_app.logger.debug(
                    'Domain "{domain}" with '
                    'ip "{ips}" in zone "{zone}" '
                    'already exists'.format(
                        zone=zone.name, domain=domain, ips=new_ips
                    ))

            return

    # dnsonly can assign only one ip address
    # here you can use roundrobin for many ip addresses
    new_ip = new_ips[0]

    zone.add_a_record(domain, new_ip)
    current_app.logger.debug(
        'Create new record in zone "{zone}" with '
        '"{domain}" '
        'and ip "{ips}"'.format(
            zone=zone.name, domain=domain, ips=new_ips
        ))


def create_or_update_type_CNAME_record(domain, target, **kwargs):
    """
    Create or update CNAME record for IP addresses of load
    balancer

    :param str domain: New subdomain name in existing zone
    :param list new_ips: IP addresses of load balancer
    :param dict kwargs: additional params such as token for access WHM API
    :return:
    """
    main_domain = extract_main_domain(domain)
    api = API(**kwargs)

    try:
        target_zone = api.get_zone(main_domain)
    except exceptions.ZoneDoesNotExist:
        raise ValueError("Zone for domain {} not found. "
                         "Need to configure the zone".format(domain))

    for dns_record in target_zone.records():
        if dns_record.type == 'CNAME' and domain == dns_record.name[:-1]:
            if dns_record.cname == target:
                current_app.logger.debug(
                    'CNAME record {} for domain "{}" '
                    'in the "{}" zone already exists'.format(
                        target, domain, target_zone.name))
                return

            dns_record.cname = target
            dns_record.edit()

            current_app.logger.debug(
                'Replaced CNAME record in zone "{zone}" with '
                'domain "{domain}" and target "{target}"'.format(
                    zone=target_zone.name, domain=domain, target=target))

            return

    # If a matching record was not found - create a new one
    target_zone.add_cname_record(domain, target)
    current_app.logger.debug(
        'Created a new CNAME record in zone "{zone}" with '
        '"{domain}" and target "{target}"'.format(
            zone=target_zone.name, domain=domain, target=target
        ))


def check_if_zone_exists(domain, **kwargs):
    api = API(**kwargs)
    try:
        api.get_zone(domain)
        return True
    except exceptions.ZoneDoesNotExist:
        return False


def extract_main_domain(domain):
    if domain.endswith('.'):
        domain = domain[:-1]

    _, _, main_domain = domain.partition('.')

    return main_domain
