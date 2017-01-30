
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


from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.utils import NO_FREE_IPS_ERR_MSG, assert_raises, \
    assert_eq, POD_STATUSES, log_debug
from tests_integration.lib.pipelines import pipeline


@pipeline('networking')
@pipeline('networking_upgraded')
@pipeline('networking_aws')
def test_pod_ip_resource(cluster):
    # type: (KDIntegrationTestAPI) -> None
    # It's not possible to create a POD with public IP with no IP pools
    cluster.ip_pools.clear()
    with assert_raises(NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG):
        cluster.pods.create("nginx", "test_nginx_pod_2",
                            open_all_ports=True,
                            start=True)

    assert_eq(cluster.pods.filter_by_owner(), [])

    # It's still possible to create a pod without a public IP
    cluster.pods.create("nginx", "test_nginx_pod_3",
                        start=True, open_all_ports=False,
                        wait_for_status=POD_STATUSES.running)


@pipeline('networking')
@pipeline('networking_aws')
@pipeline('networking_upgraded')
def test_create_delete_ippool(cluster):
    nginx1 = cluster.pods.create("nginx", "test_nginx_pod_1",
                                 open_all_ports=True, start=True,
                                 healthcheck=True, wait_ports=True,
                                 wait_for_status=POD_STATUSES.running)
    nginx2 = cluster.pods.create("nginx", "test_nginx_pod_2",
                                 open_all_ports=True, start=True,
                                 healthcheck=True, wait_ports=True,
                                 wait_for_status=POD_STATUSES.running)

    with assert_raises(NonZeroRetCodeException,
                       text='.*You cannot delete this network.*',
                       expected_ret_codes=(1,)):
        cluster.ip_pools.clear()

    nginx1.healthcheck()
    nginx2.healthcheck()
    nginx1.delete()
    nginx2.delete()
    cluster.ip_pools.clear()
    cluster.ip_pools.add('192.168.0.0/24',
                         excludes='192.168.0.0-192.168.0.214,'
                                  '192.168.0.218-192.168.0.255')
    pool = cluster.ip_pools.get('192.168.0.0/24')
    log_debug(pool)
    assert_eq(len(pool['free_hosts']), 3)
