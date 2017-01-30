
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

from kubedock.users.models import User, db
from kubedock.kapi.pod import Pod
from kubedock.billing import repr_limits
from uuid import uuid4
import json


def attach_to_rc(db_pod, db_pod_config):
    item = Pod()._get(['pods', db_pod_config['sid']],
                      ns=db_pod_config.get('namespace'))
    if item['kind'] == 'Status' and item['reason'] == 'NotFound':
        return  # pod is stopped
    pod = Pod.populate(item)
    if pod.status not in ('running', 'succeeded', 'failed'):
        return

    # merge pod from db and pod from kubernetes in one object
    pod.kube_type = db_pod_config.get('kube_type')
    if db_pod_config.get('public_ip'):
        pod.public_ip = db_pod_config['public_ip']
    pod.secrets = db_pod_config.get('secrets', [])
    a = pod.containers
    b = db_pod_config.get('containers')
    pod.containers = pod.merge_lists(a, b, 'name')
    pod.owner = db_pod.owner.username
    for container in pod.containers:
        container.pop('resources', None)
        container['limits'] = repr_limits(container['kubes'],
                                          db_pod_config['kube_type'])

    # create RC
    pod.replicationController = db_pod_config['replicationController'] = True
    pod.replicas = db_pod_config['replicas'] = 1
    pod.sid = db_pod_config['sid'] = str(uuid4())

    rv = pod._post(['replicationcontrollers'], json.dumps(pod.prepare()),
                   rest=True, ns=pod.namespace)
    if rv['kind'] == 'Status':  # k8s will return Status in case of an error
        raise Exception  # couldn't save RC, no need to revert anything

    db_pod.config = json.dumps(db_pod_config)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        # revert changes in kubernetes
        rv = pod._del(['replicationcontrollers', pod.sid], ns=pod.namespace)
        raise


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add Replication Controller to each pod.')
    for user in User.query.all():
        for db_pod in user.pods:
            db_pod_config = json.loads(db_pod.config)
            if db_pod.status == 'deleted' or db_pod_config.get('replicationController'):
                continue
            attach_to_rc(db_pod, db_pod_config)


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')
    # It is totally ok if some of pods will stay with RC.
    # By trying to remove RC we can only make things worse.
