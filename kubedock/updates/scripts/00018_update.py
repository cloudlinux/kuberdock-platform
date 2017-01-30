
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

from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    helpers.install_package('kubernetes-master-1.0.3', with_testing)
    helpers.restart_master_kubernetes()

def downgrade(upd, with_testing,  exception, *args, **kwargs):
    helpers.local('yum downgrade kubernetes-master --enablerepo=kube')
    helpers.restart_master_kubernetes()

def upgrade_node(upd, with_testing, env, *args, **kwargs):
    helpers.remote_install('kubernetes-node-1.0.3', with_testing)
    helpers.restart_node_kubernetes()

def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
   helpers.remote_install('kubernetes-node', action='downgrade', testing=with_testing)
   helpers.restart_node_kubernetes()
