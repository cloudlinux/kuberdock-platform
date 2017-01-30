
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

import json

import etcd

from ..restricted_ports.models import RestrictedPort
from ..core import db
from ..exceptions import RestrictedPortsException
from ..kapi.network_policies import (
    get_pod_restricted_ports_policy,
    get_pod_restricted_ports_rule,
)
from ..settings import ETCD_RESTRICTED_PORT_KEY_PATH, ETCD_HOST, ETCD_PORT


ETCD_ERROR_MESSAGE = "Can't update restricted port policy in etcd"


def _get_restricted_ports_rules():
    restricted_ports = {}
    for port in RestrictedPort.query:
        restricted_ports.setdefault(port.protocol, []).append(port.port)

    restricted_ports_rules = []
    for proto, ports in restricted_ports.items():
        rule = get_pod_restricted_ports_rule(ports, proto)
        restricted_ports_rules.append(rule)

    return restricted_ports_rules


def get_ports():
    return [restricted_port.dict() for restricted_port in RestrictedPort.query]


def _set_restricted_ports_etcd():
    restricted_ports_rules = _get_restricted_ports_rules()

    restricted_ports_policy = json.dumps(
        get_pod_restricted_ports_policy(restricted_ports_rules)
    )

    client = etcd.Client(host=ETCD_HOST, port=ETCD_PORT)
    try:
        result = client.read(ETCD_RESTRICTED_PORT_KEY_PATH)
        result.value = restricted_ports_policy
        client.update(result)
    except etcd.EtcdKeyNotFound:
        client.write(ETCD_RESTRICTED_PORT_KEY_PATH, restricted_ports_policy)
    except etcd.EtcdException:
        raise RestrictedPortsException.ClosePortError(
            details={'message': ETCD_ERROR_MESSAGE}
        )


def set_port(port, protocol):
    _protocol = protocol.lower()
    if RestrictedPort.query.filter_by(port=port, protocol=_protocol).first():
        raise RestrictedPortsException.ClosePortError(
            details={'message': 'Port already closed'}
        )

    restricted_port = RestrictedPort(port=port, protocol=_protocol)

    db.session.add(restricted_port)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise RestrictedPortsException.ClosePortError(
            details={'message': 'Error adding Restricted Port to database'}
        )

    _set_restricted_ports_etcd()


def del_port(port, protocol):
    _protocol = protocol.lower()
    restricted_port = RestrictedPort.query.filter_by(port=port,
                                                  protocol=_protocol).first()
    if restricted_port is None:
        raise RestrictedPortsException.OpenPortError(
            details={'message': "Port doesn't closed"}
        )

    db.session.delete(restricted_port)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise RestrictedPortsException.OpenPortError(
            details={'message': 'Error deleting Restricted Port from database'}
        )

    restricted_ports_rules = _get_restricted_ports_rules()

    client = etcd.Client(host=ETCD_HOST, port=ETCD_PORT)

    if restricted_ports_rules:
        restricted_ports_policy = get_pod_restricted_ports_policy(
            restricted_ports_rules)
        try:
            result = client.read(ETCD_RESTRICTED_PORT_KEY_PATH)
            result.value = json.dumps(restricted_ports_policy)
            client.update(result)
        except etcd.EtcdException:
            raise RestrictedPortsException.OpenPortError(
                details={'message': ETCD_ERROR_MESSAGE}
            )
    else:
        try:
            client.delete(ETCD_RESTRICTED_PORT_KEY_PATH)
        except etcd.EtcdKeyNotFound:
            pass
        except etcd.EtcdException:
            raise RestrictedPortsException.OpenPortError(
                details={
                    'message': "Can't remove restricted ports policy from etcd"
                }
            )
