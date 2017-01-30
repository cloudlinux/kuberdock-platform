
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
    upd.print_log('Reloading flannel...')
    helpers.local('systemctl daemon-reload')
    helpers.local('systemctl restart flanneld')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Reloading flannel...')
    helpers.local('systemctl daemon-reload')
    helpers.local('systemctl restart flanneld')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log(helpers.remote_install('kernel-devel', with_testing))
    upd.print_log('Updating flannel...')
    upd.print_log(helpers.remote_install('flannel-0.5.3', with_testing))
    upd.print_log(run('systemctl daemon-reload'))
    upd.print_log(run('systemctl restart flanneld'))


def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
    upd.print_log(helpers.remote_install('kernel-devel', with_testing,
                                         action='remove'))
    upd.print_log('Downgrade flannel...')
    upd.print_log(helpers.remote_install('flannel-0.5.1', with_testing,
                                         action='downgrade'))
    upd.print_log(run('systemctl daemon-reload'))
    upd.print_log(run('systemctl restart flanneld'))
