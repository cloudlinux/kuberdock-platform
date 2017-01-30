
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

from ..allowed_ports.models import AllowedPort
from ..core import db
from ..exceptions import AllowedPortsException
from ..kapi.network_policies import (
    get_node_allowed_ports_policy,
    get_node_allowed_ports_rule,
)
from ..settings import ETCD_ALLOWED_PORT_KEY_PATH, ETCD_HOST, ETCD_PORT


ETCD_ERROR_MESSAGE = "Can't update allowed port policy in etcd"


def _get_allowed_ports_rules():
    allowed_ports = {}
    for port in AllowedPort.query:
        allowed_ports.setdefault(port.protocol, []).append(port.port)

    allowed_ports_rules = []
    for proto, ports in allowed_ports.items():
        rule = get_node_allowed_ports_rule(ports, proto)
        allowed_ports_rules.append(rule)

    return allowed_ports_rules


def get_ports():
    return [allowed_port.dict() for allowed_port in AllowedPort.query]


def _set_allowed_ports_etcd():
    allowed_ports_rules = _get_allowed_ports_rules()

    allowed_ports_policy = json.dumps(
        get_node_allowed_ports_policy(allowed_ports_rules)
    )

    client = etcd.Client(host=ETCD_HOST, port=ETCD_PORT)
    try:
        result = client.read(ETCD_ALLOWED_PORT_KEY_PATH)
        result.value = allowed_ports_policy
        client.update(result)
    except etcd.EtcdKeyNotFound:
        client.write(ETCD_ALLOWED_PORT_KEY_PATH, allowed_ports_policy)
    except etcd.EtcdException:
        raise AllowedPortsException.OpenPortError(
            details={'message': ETCD_ERROR_MESSAGE}
        )


def set_port(port, protocol):
    _protocol = protocol.lower()
    if AllowedPort.query.filter_by(port=port, protocol=_protocol).first():
        raise AllowedPortsException.OpenPortError(
            details={'message': 'Port already opened'}
        )

    allowed_port = AllowedPort(port=port, protocol=_protocol)

    db.session.add(allowed_port)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise AllowedPortsException.OpenPortError(
            details={'message': 'Error adding Allowed Port to database'}
        )

    _set_allowed_ports_etcd()


def del_port(port, protocol):
    _protocol = protocol.lower()
    allowed_port = AllowedPort.query.filter_by(port=port,
                                               protocol=_protocol).first()
    if allowed_port is None:
        raise AllowedPortsException.ClosePortError(
            details={'message': "Port doesn't opened"}
        )

    db.session.delete(allowed_port)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise AllowedPortsException.ClosePortError(
            details={'message': 'Error deleting Allowed Port from database'}
        )

    allowed_ports_rules = _get_allowed_ports_rules()

    client = etcd.Client(host=ETCD_HOST, port=ETCD_PORT)

    if allowed_ports_rules:
        allowed_ports_policy = get_node_allowed_ports_policy(
            allowed_ports_rules)
        try:
            result = client.read(ETCD_ALLOWED_PORT_KEY_PATH)
            result.value = json.dumps(allowed_ports_policy)
            client.update(result)
        except etcd.EtcdException:
            raise AllowedPortsException.ClosePortError(
                details={'message': ETCD_ERROR_MESSAGE}
            )
    else:
        try:
            client.delete(ETCD_ALLOWED_PORT_KEY_PATH)
        except etcd.EtcdKeyNotFound:
            pass
        except etcd.EtcdException:
            raise AllowedPortsException.ClosePortError(
                details={
                    'message': "Can't remove allowed ports policy from etcd"
                }
            )
