
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


def upgrade(*args, **kwargs):
    pass


def downgrade(*args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Allow registries with self-sighned serts...')
    upd.print_log(run(r'''
        sed -i.old "s|^# \(INSECURE_REGISTRY='--insecure-registry\)'|\1=0.0.0.0/0'|" \
            /etc/sysconfig/docker
    '''))
    upd.print_log(run('systemctl restart docker'))


def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
    upd.print_log('Forbid registries with self-sighned serts...')
    upd.print_log(run(r'''
        sed -i.old "s|^\(INSECURE_REGISTRY='--insecure-registry\)=0.0.0.0/0'|# \1\'|"
            /etc/sysconfig/docker
    '''))
    upd.print_log(run('systemctl restart docker'))
