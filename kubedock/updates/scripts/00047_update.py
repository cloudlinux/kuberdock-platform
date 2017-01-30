
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

from sqlalchemy.sql import text

from kubedock.core import db
from kubedock.updates import helpers
from kubedock import tasks
from kubedock.settings import NODE_CEPH_AWARE_KUBERDOCK_LABEL


def update_node_ceph_flags():
    hosts_query = text("SELECT hostname from nodes")
    hosts = [item[0] for item in db.session.execute(hosts_query).fetchall()]
    hosts_with_ceph = []
    for host in hosts:
        if not tasks.is_ceph_installed_on_node(host):
            continue
        hosts_with_ceph.append(host)
    if not hosts_with_ceph:
        return
    flags_query =\
        "INSERT INTO node_flags (node_id, created, deleted, flag_name, flag_value) "\
        "SELECT id, NOW() at time zone 'utc', NULL, 'ceph_installed', 'true' FROM nodes "\
        "WHERE hostname IN ({})".format(
            ', '.join("'" + host + "'" for host in hosts_with_ceph)
        )
    db.session.execute(text(flags_query))
    db.session.commit()
    for host in hosts_with_ceph:
        tasks.add_k8s_node_labels(
            host, {NODE_CEPH_AWARE_KUBERDOCK_LABEL: "True"})


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading db...')
    helpers.upgrade_db(revision='3505518f6f4f')

    update_node_ceph_flags()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading db...')
    helpers.downgrade_db(revision='79a6e3998d6')
