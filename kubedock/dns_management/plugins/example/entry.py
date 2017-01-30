
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
