
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

from kubedock.kapi.nodes import handle_nodes, process_rule
from kubedock.nodes.models import Node
from kubedock.settings import MASTER_IP, PORTS_TO_RESTRICT


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Allow master to access ElasticSearch on nodes')
    nodes = [n for n, in Node.query.values(Node.ip)]
    for port in PORTS_TO_RESTRICT:
        handle_nodes(process_rule, nodes=nodes, action='insert', port=port,
                     target='ACCEPT', source=MASTER_IP, append_reject=False)


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Revert "Allow master to access ElasticSearch on nodes"')
    nodes = [n for n, in Node.query.values(Node.ip)]
    for port in PORTS_TO_RESTRICT:
        handle_nodes(process_rule, nodes=nodes, action='delete', port=port,
                     target='ACCEPT', source=MASTER_IP, append_reject=False)
