
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

from kubedock.kapi.nodes import (
    get_kuberdock_logs_config,
    get_kuberdock_logs_pod_name,
)
from kubedock.kapi.podcollection import PodCollection
from kubedock.settings import KUBERDOCK_INTERNAL_USER, MASTER_IP
from kubedock.users.models import User
from kubedock.validation import check_internal_pod_data


CONF = '/etc/rsyslog.d/kuberdock.conf'
PARAM = '$LocalHostName'


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Add node hostname to rsyslog configuration...')

    run("sed -i '/^{0}/d; i{0} {1}' {2}".format(PARAM, env.host_string, CONF))
    run('systemctl restart rsyslog')

    upd.print_log('Update logging pod...')
    ki = User.filter_by(username=KUBERDOCK_INTERNAL_USER).first()
    pod_name = get_kuberdock_logs_pod_name(env.host_string)

    for pod in PodCollection(ki).get(as_json=False):
        if pod['name'] == pod_name:
            break
    else:
        return

    PodCollection(ki).delete(pod['id'], force=True)
    logs_config = get_kuberdock_logs_config(
        env.host_string,
        pod_name,
        pod['kube_type'],
        pod['containers'][0]['kubes'],
        pod['containers'][1]['kubes'],
        MASTER_IP,
        ki.get_token(),
    )
    check_internal_pod_data(logs_config, user=ki)
    logs_pod = PodCollection(ki).add(logs_config, skip_check=True)

    run('rm -fr /var/lib/elasticsearch/kuberdock/nodes/*/indices/syslog-*')

    PodCollection(ki).update(logs_pod['id'], {'command': 'start'})


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')
