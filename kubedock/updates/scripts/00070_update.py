
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

from fabric.api import local, put, run

from kubedock.users.models import User
from kubedock.pods.models import Pod
from kubedock.settings import KUBERDOCK_INTERNAL_USER
from kubedock.kapi.nodes import get_dns_pod_config
from kubedock.validation import check_internal_pod_data
from kubedock.kapi.podcollection import PodCollection


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Update dns pod...')

    local('etcd-ca --depot-path /root/.etcd-ca new-cert --ip "10.254.0.10" --passphrase "" etcd-dns')
    local('etcd-ca --depot-path /root/.etcd-ca sign --passphrase "" etcd-dns')
    local('etcd-ca --depot-path /root/.etcd-ca export etcd-dns --insecure --passphrase "" | tar -xf -')
    local('mv etcd-dns.crt /etc/pki/etcd/etcd-dns.crt')
    local('mv etcd-dns.key.insecure /etc/pki/etcd/etcd-dns.key')

    user = User.filter_by(username=KUBERDOCK_INTERNAL_USER).one()

    dns_pod = Pod.filter_by(name='kuberdock-dns', owner=user).first()

    if dns_pod:
        PodCollection(user).delete(dns_pod.id, force=True)

    dns_config = get_dns_pod_config()
    check_internal_pod_data(dns_config, user)
    dns_pod = PodCollection(user).add(dns_config, skip_check=True)
    PodCollection(user).update(dns_pod['id'], {'command': 'start'})


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade available')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Copy etcd-dns cert/key to node {0}'.format(env.host_string))
    put('/etc/pki/etcd/etcd-dns.crt', '/etc/pki/etcd/etcd-dns.crt')
    put('/etc/pki/etcd/etcd-dns.key', '/etc/pki/etcd/etcd-dns.key')

    upd.print_log('Rebooting node...')
    run('(sleep 2; reboot) &', pty=False)


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('No downgrade provided')
