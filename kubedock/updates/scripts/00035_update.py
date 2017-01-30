
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

import re
import math

from kubedock.core import db
from kubedock.users.models import User
from kubedock.pods.models import Pod
from kubedock.nodes.models import Node
from kubedock.settings import KUBERDOCK_INTERNAL_USER, MASTER_IP
from kubedock.kapi.nodes import (
    get_kuberdock_logs_config,
    get_dns_pod_config,
    get_kuberdock_logs_pod_name,
    KUBERDOCK_LOGS_MEMORY_LIMIT
)
from kubedock.validation import check_internal_pod_data
from kubedock.billing import Kube, kubes_to_limits
from kubedock.kapi.podcollection import PodCollection


INTERNAL_SERVICE_KUBE_TYPE = -1
int_kube_type_config = {
    'id': INTERNAL_SERVICE_KUBE_TYPE,
    'name': 'Internal service',
    'cpu': .01,
    'cpu_units': 'Cores',
    'memory': 64,
    'memory_units': 'MB',
    'disk_space': 1,
    'disk_space_units': 'GB',
    'included_traffic': 0
}

pod_name_pattern = re.compile(get_kuberdock_logs_pod_name('.+?'))

def get_internal_user():
    return User.query.filter_by(username=KUBERDOCK_INTERNAL_USER).first()

def update_dns_pod(user):
    dns_pod = db.session.query(Pod).filter(
        Pod.name == 'kuberdock-dns',
        Pod.owner_id == user.id
    ).first()
    if dns_pod:
        pods = PodCollection(user)
        pods.delete(dns_pod.id, force=True)

    dns_config = get_dns_pod_config()
    check_internal_pod_data(dns_config, user)
    dns_pod = PodCollection(user).add(dns_config, skip_check=True)
    PodCollection(user).update(dns_pod['id'], {'command': 'start'})


def add_internal_kube_type():
    kube = db.session.query(Kube).filter(
        Kube.id == INTERNAL_SERVICE_KUBE_TYPE
    ).first()
    if kube:
        return
    kube = Kube(**int_kube_type_config)
    db.session.add(kube)
    db.session.commit()


def update_log_pods(user):

    for pod in PodCollection(user).get(as_json=False):
        if pod_name_pattern.match(pod['name']):
            PodCollection(user).delete(pod['id'], force=True)

    logs_kubes = 1
    logcollector_kubes = logs_kubes
    logstorage_kubes = logs_kubes
    node_resources = kubes_to_limits(
        logs_kubes, INTERNAL_SERVICE_KUBE_TYPE)['resources']
    logs_memory_limit = node_resources['limits']['memory']
    if logs_memory_limit < KUBERDOCK_LOGS_MEMORY_LIMIT:
        logs_kubes = int(math.ceil(
            float(KUBERDOCK_LOGS_MEMORY_LIMIT) / logs_memory_limit
        ))

    if logs_kubes > 1:
        # allocate total log cubes to log collector and to log
        # storage/search containers as 1 : 3
        total_kubes = logs_kubes * 2
        logcollector_kubes = int(math.ceil(float(total_kubes) / 4))
        logstorage_kubes = total_kubes - logcollector_kubes

    for node in Node.query:
        hostname = node.hostname
        podname = get_kuberdock_logs_pod_name(hostname)
        logs_config = get_kuberdock_logs_config(
            hostname,
            podname,
            INTERNAL_SERVICE_KUBE_TYPE,
            logcollector_kubes,
            logstorage_kubes,
            MASTER_IP,
            user.token,
        )
        check_internal_pod_data(logs_config, user=user)
        logs_pod = PodCollection(user).add(logs_config)
        PodCollection(user).update(logs_pod['id'], {'command': 'start'})


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Adding internal kube type ...')
    add_internal_kube_type()
    upd.print_log('Update dns pod ...')
    user = get_internal_user()
    update_dns_pod(user)
    upd.print_log('Update logs pods ...')
    update_log_pods(user)
    upd.print_log('Done.')


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade available.')
