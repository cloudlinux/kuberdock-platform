
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
    helpers.install_package('kuberdock', with_testing)
    helpers.upgrade_db(revision='head')


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    # do not output to stdout because of unicode decoding exception
    run('rpm --nodeps -e docker')
    run('rm -rf /var/lib/docker')
    run('yum install kernel kernel-headers kernel-tools kernel-tools-libs docker-1.6.2 docker-selinux-1.6.2 --disablerepo=extras --enablerepo=kube-testing -y')
    run('rm -f /etc/sysconfig/docker-storage.rpmsave')
    run("sed -i '/^DOCKER_STORAGE_OPTIONS=/c\DOCKER_STORAGE_OPTIONS=--storage-driver=overlay' /etc/sysconfig/docker-storage")
    run("reboot")


def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
    pass
