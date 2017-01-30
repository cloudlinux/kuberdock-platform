
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
from fabric.api import run


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Test_master_upgrade 1', helpers.local('uname -a'))
    helpers.upgradedb()


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Test_master_downgrade 1')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Upgrade node test')
    print run('uname -a')


def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
    upd.print_log('In downgrade node')
