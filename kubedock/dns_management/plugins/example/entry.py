"""Minimal example for DNS management plugin.
"""

from flask import current_app


def delete_type_A_record(domain, **kwargs):
    """
    Delete A record to domain

    :param domain: domain which will have been deleted
    :param dict kwargs: additional params such as address, token for access to
        external DNS management API
    :return: None

    Note: this is an example, does nothing, useful for testing
    """
    current_app.logger.debug(
        u'Called "delete_type_A_record" domain: {}, params: {}'.format(
            domain, kwargs))


def create_or_update_type_A_record(domain, new_ips, **kwargs):
    """
    Create or update A record for IP addresses of load
    balancer

    :param str domain: New subdomain name in existing zone
    :param list new_ips: IP addresses of load balancer (Ingress controller)
    :param dict kwargs: additional params such as address, token for access to
        external DNS management API
    :return: None

    Note: this is an example, does nothing, useful for testing
    """
    current_app.logger.debug(
        u'Called "create_or_update_type_A_record" domain: {}, ips: {}, '
        u'params: {}'.format(domain, new_ips, kwargs))
