from flask import current_app

import CloudFlare


def delete_type_A_record(domain, **kwargs):
    """
    Delete A record to domain

    :param domain: domain which will have been deleted
    :param dict kwargs: additional params such as email and
        token for access to Cloudflare API
    :return: None
    """
    sub_domain, _, main_domain = domain.partition('.')
    cf = CloudFlare.CloudFlare(**kwargs)

    try:
        zone = cf.zones.get(params={'name': main_domain})[0]
    except IndexError:
        return

    for dns_record in cf.zones.dns_records.get(zone['id'], params={
        'type': 'A',
        'name': domain
    }):
        cf.zones.dns_records.delete(
            zone['id'],
            dns_record['id']
        )


def create_or_update_type_A_record(domain, new_ips, **kwargs):
    """
    Create or update A record for IP addresses of load
    balancer

    :param str domain: New subdomain name in existing zone
    :param list new_ips: IP addresses of load balancer
    :param dict kwargs: additional params such as email and token
        for access to Cloudflare API
    :return: None
    """
    sub_domain, _, main_domain = domain.partition('.')
    cf = CloudFlare.CloudFlare(**kwargs)

    try:
        zone = cf.zones.get(params={'name': main_domain})[0]
    except IndexError:
        raise ValueError("Zone for domain {} not found. "
                         "Need to configure the zone".format(domain))

    for dns_record in cf.zones.dns_records.get(zone['id'], params={
        'type': 'A',
        'name': domain
    }):
        if dns_record['content'] not in new_ips:
            # cloudflare can assign only one ip address
            # here you can use roundrobin for many ip addresses
            new_ip = new_ips[0]
            data = {
                'content': new_ip,
                # Requires other fields
                # https://github.com/danni/python-cloudflare/blob
                # /python3ify/examples
                # /example-create-zone-and-populate.py#L59

                'type': dns_record['type'],
                'name': dns_record['name']
            }
            cf.zones.dns_records.put(
                zone['id'],
                dns_record['id'],
                data=data)
            current_app.logger.debug(
                'Replace record in zone "{zone}" with '
                'domain "{domain}" '
                'and ip "{ips}"'.format(
                    zone=zone['name'], domain=domain, ips=new_ip
                ))
        else:
            current_app.logger.debug(
                'Domain "{domain}" with '
                'ip "{ips}" in zone "{zone}" '
                'already exists'.format(
                    zone=zone['name'], domain=domain, ips=new_ips
                ))

        break  # exit for loop after dns zone was processed
    else:
        # this branch executes if for loop is not terminated by break
        # e.g. there is no dns zone that we expect for

        # cloudflare can assign only one ip address
        # here you can use roundrobin for many ip addresses
        new_ip = new_ips[0]
        data = {
            'content': new_ip,
            'type': 'A',
            'name': domain
        }
        cf.zones.dns_records.post(zone['id'], data=data)
        current_app.logger.debug(
            'Create new record in zone "{zone}" with '
            '"{domain}" '
            'and ip "{ips}"'.format(
                zone=zone['name'], domain=domain, ips=new_ips
            ))
