
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

from kubedock.kapi.helpers import KubeQuery, get_pod_config, replace_pod_config
from kubedock.kapi.podcollection import PodCollection


def upgrade(upd, with_testing, *args, **kwargs):
    pod_collection = PodCollection()
    for pod_dict in pod_collection.get(as_json=False):
        pod = pod_collection._get_by_id(pod_dict['id'])
        db_config = get_pod_config(pod.id)
        cluster_ip = db_config.pop('clusterIP', None)
        if cluster_ip is None:
            service_name = db_config.get('service')
            if service_name is None:
                continue
            namespace = db_config.get('namespace') or pod.id
            service = KubeQuery().get(['services', service_name], ns=namespace)
            cluster_ip = service.get('spec', {}).get('clusterIP')
            if cluster_ip is not None:
                db_config['podIP'] = cluster_ip
        replace_pod_config(pod, db_config)


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('No downgrade provided')
