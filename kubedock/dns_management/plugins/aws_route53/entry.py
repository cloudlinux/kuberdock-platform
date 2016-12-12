from boto.route53.connection import Route53Connection
from flask import current_app


def _make_qualified(domain):
    if domain.startswith('*.'):
        domain = r'\052' + domain[1:]
    if not domain.endswith('.'):
        domain += '.'
    return domain


def delete_type_A_record(domain, **kwargs):
    """
    Delete A record for domain

    :param domain: domain to delete
    :param dict kwargs: additional params such as id and secret for access to
        AWS ROUTE 53
    :return: None
    """
    domain = _make_qualified(domain)

    main_domain = domain.split('.', 1)[-1]

    conn = Route53Connection(kwargs['id'], kwargs['secret'])

    zone = conn.get_zone(main_domain)
    if zone is None:
        return

    record = zone.get_a(domain)
    if record is None:
        return

    zone.delete_a(domain, all=False)


def delete_type_CNAME_record(domain, **kwargs):
    """
    Delete CNAME record for domain

    :param domain: domain to delete
    :param dict kwargs: additional params such as id and secret for access to
        AWS ROUTE 53
    :return: None
    """
    domain = _make_qualified(domain)

    main_domain = domain.split('.', 1)[-1]

    conn = Route53Connection(kwargs['id'], kwargs['secret'])

    zone = conn.get_zone(main_domain)
    if zone is None:
        return

    record = zone.get_cname(domain)
    if record is None:
        return

    zone.delete_cname(domain, all=False)


def create_or_update_type_A_record(domain, new_ips, **kwargs):
    """
    Create or update A record for domain

    :param str domain: domain to add
    :param list new_ips: IP addresses of load balancer
    :param dict kwargs: additional params such as id and secret for access to
        AWS ROUTE 53
    :return:
    """
    domain = _make_qualified(domain)

    main_domain = domain.split('.', 1)[-1]

    conn = Route53Connection(kwargs['id'], kwargs['secret'])

    zone = conn.get_zone(main_domain)
    if zone is None:
        raise ValueError('Zone for domain {} not found. '
                         'Need to configure the zone'.format(domain))

    record = zone.get_a(domain)
    if record is None:
        zone.add_a(domain, new_ips)
        current_app.logger.debug(
            'Create new record in zone "{zone}" with '
            '"{domain}" and ip "{ips}"'.format(
                zone=zone.name, domain=domain, ips=new_ips
            )
        )
    else:
        if set(new_ips) != set(record.resource_records):
            zone.update_a(domain, new_ips)
            current_app.logger.debug(
                'Replace record in zone "{zone}" with '
                'domain "{domain}" and ip "{ips}"'.format(
                    zone=zone.name, domain=domain, ips=new_ips
                )
            )
        else:
            current_app.logger.debug(
                'Domain "{domain}" with '
                'ip "{ips}" in zone "{zone}" '
                'already exists'.format(
                    zone=zone.name, domain=domain, ips=new_ips
                )
            )


def check_if_zone_exists(domain, **kwargs):
    # For Route53 domain should end with dot
    domain = _make_qualified(domain)

    conn = Route53Connection(kwargs['id'], kwargs['secret'])
    zone = conn.get_zone(domain)
    return bool(zone)


def create_or_update_type_CNAME_record(domain, target, **kwargs):
    """
    Create or update CNAME record for domain

    :param str domain: domain to add
    :param list target: CNAME target to point the domain to
    :param dict kwargs: additional params such as id and secret for access to
        AWS ROUTE 53
    :return:
    """
    domain = _make_qualified(domain)

    main_domain = domain.split('.', 1)[-1]

    conn = Route53Connection(kwargs['id'], kwargs['secret'])

    zone = conn.get_zone(main_domain)
    if zone is None:
        raise ValueError('Zone for domain {} not found. '
                         'Need to configure the zone'.format(domain))

    record = zone.get_cname(domain)
    if record is None:
        zone.add_cname(domain, target)
        current_app.logger.debug(
            'Create new record CNAME in zone "{zone}" with '
            '"{domain}" and target "{target}"'.format(
                zone=zone.name, domain=domain, target=target,
            )
        )
        return

    if target == record.resource_records:
        current_app.logger.debug(
            'CNAME record for "{domain}" with '
            'to "{target}" in zone "{zone}" '
            'already exists'.format(
                zone=zone.name, target=target, domain=domain
            )
        )
        return

    zone.update_cname(domain, target)
    current_app.logger.debug(
        'Updated CNAME record in zone "{zone}" with '
        'domain "{domain}" and target "{target}"'.format(
            zone=zone.name, domain=domain, target=target,
        )
    )
