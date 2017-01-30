
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

from fabric.api import run
from kubedock.settings import MASTER_IP, KUBERDOCK_SETTINGS_FILE


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    if not MASTER_IP:
        raise Exception('There is no MASTER_IP specified in {0}.'
                        'Check that file has not been renamed by package '
                        'manager to .rpmsave or similar'
                        .format(KUBERDOCK_SETTINGS_FILE))
    upd.print_log('Change ntp.conf to sync only with master...')
    upd.print_log(run('sed -i "/^server /d" /etc/ntp.conf'))
    upd.print_log(
        run('echo "server {0} iburst" >> /etc/ntp.conf'.format(MASTER_IP))
    )
    upd.print_log(run('systemctl restart ntpd'))


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('No downgrade provided for this update. You may rerun '
                  'this upgrade script as many times as need or edit '
                  '/etc/ntp.conf manually.')
