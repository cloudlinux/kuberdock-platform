
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

from shutil import copyfile, copystat
from kubedock.updates import helpers

nginx_path = '/etc/nginx/nginx.conf'
kd_path = '/etc/nginx/conf.d/kuberdock-ssl.conf'


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Update nginx config...')

    copyfile(nginx_path, nginx_path + '.disabled')
    copystat(nginx_path, nginx_path + '.disabled')
    copyfile(kd_path, kd_path + '.disabled')
    copystat(kd_path, kd_path + '.disabled')

    copyfile('/var/opt/kuberdock/conf/nginx.conf', nginx_path)
    copyfile('/var/opt/kuberdock/conf/kuberdock-ssl.conf', kd_path)
    helpers.restart_service('nginx')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Rollback nginx config...')
    copyfile(nginx_path + '.disabled', nginx_path)
    copyfile(kd_path + '.disabled', kd_path)
    helpers.restart_service('nginx')
