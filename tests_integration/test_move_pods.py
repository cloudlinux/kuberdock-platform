
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

import logging

from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.utils import (
    assert_raises, wait_for, log_debug, hooks, POD_STATUSES, NODE_STATUSES,
    assert_eq)
from tests_integration.lib.pipelines import pipeline


LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


@pipeline('move_pods')
@pipeline('move_pods_aws')
@hooks(teardown=lambda c: c.nodes.wait_all())
def test_pods_with_local_storage_stop(cluster):
    # type: (KDIntegrationTestAPI) -> None
    """
    Tests that the pod with local storage will stop when host, on which local
    storage resides, becomes unavailable.
    """
    pv = cluster.pvs.add('dummy', 'fakepv', '/nginxpv')
    pod = cluster.pods.create(
        'nginx', 'test_nginx_pod', pvs=[pv], start=True)
    pod.wait_for_status(POD_STATUSES.running)
    host = pod.info['host']
    with cluster.temporary_stop_host(host):
        cluster.nodes.get_node(host).wait_for_status(NODE_STATUSES.troubles)
        pod.wait_for_status(POD_STATUSES.stopped)


@pipeline('fixed_ip_pools')
@pipeline('move_pods')
@pipeline('move_pods_aws')
@hooks(teardown=lambda c: c.nodes.wait_all())
def test_pods_move_on_failure(cluster):
    # type: (KDIntegrationTestAPI) -> None
    """
    Tests that the pod without local storage and public IPs will move to
    another host in case of failure.
    """
    pod = cluster.pods.create('nginx', 'test_nginx_pod', start=True)
    pod.wait_for_status(POD_STATUSES.running)
    hostname = pod.info['host']
    log_debug(
        "Check that pod with no PV and public IP (not fixed IP cluster) "
        "migrates to another node when the hosting node fails", LOG)
    with cluster.temporary_stop_host(hostname):
        wait_for(lambda: pod.info['host'] != hostname)
        pod.wait_for_status(POD_STATUSES.running)


@pipeline('move_pods')
@hooks(teardown=lambda c: c.nodes.wait_all())
def test_pods_with_public_ip_move(cluster):
    """
    Test that pod with public IP and no PV moves to another node in case of
    hosting node failure
    """
    pod = cluster.pods.create(
        'nginx', 'test_move_pods_with_pub_ip', open_all_ports=True,
        start=True, wait_for_status=POD_STATUSES.running)

    hostname = pod.node
    log_debug(
        "Check that pod with no PV, but with public IP (not fixed IP cluster) "
        "migrates to another node when the hosting node fails", LOG)
    with cluster.temporary_stop_host(hostname):
        wait_for(lambda: pod.node != hostname)
        pod.wait_for_status(POD_STATUSES.running)


@pipeline('move_pods')
@pipeline('move_pods_aws')
def test_error_start_with_shutdown_local_storage(cluster):
    # type: (KDIntegrationTestAPI) -> None
    """
    Tests that the pod which has persistent volume on the host with status
    'troubles' will produce error on the start and won't start the pod.

    More specifically:
    1. Create the pod with persistent volume 'pv'.
    2. Shut down the pod and the host on which it resides.
    3. Wait till the kubernetes see the host as not working.
    4. Create a new pod with the same persistent volume 'pv'.
    5. Starting the new pod should result in an immediate error.
    """
    pv = cluster.pvs.add('dummy', 'fakepv', '/nginxpv')
    pod = cluster.pods.create('nginx', 'test_nginx_pod', pvs=[pv],
                              start=True, wait_for_status=POD_STATUSES.running)
    host = pod.info['host']
    pod.stop()
    pod.wait_for_status(POD_STATUSES.stopped)
    with cluster.temporary_stop_host(host):
        cluster.nodes.get_node(host).wait_for_status(NODE_STATUSES.troubles)
        new_pod = cluster.pods.create('nginx', 'test_nginx_pod_new',
                                      pvs=[pv],
                                      start=False)
        with assert_raises(
                NonZeroRetCodeException,
                "There are no suitable nodes for the pod. Please try"
                " again later or contact KuberDock administrator"):
            new_pod.start()
        assert_eq(new_pod.status, POD_STATUSES.stopped)


@pipeline('move_pods')
@pipeline('move_pods_aws')
def test_error_with_shutdown_local_storage(cluster):
    # type: (KDIntegrationTestAPI) -> None
    """
    Tests that the pod which has persistent volume on the host, which is about
    to be not working, will become stopped.

    More specifically:
    1. Create persistent volume 'pv' and pod, which uses it.
    2. Shut down pod and host on which it resides.
    3. Don't wait till the kubernetes see the host as not working.
    4. Create a new pod with with persistent volume 'pv'.
    5. Starting a pod should not produce any errors.
    6. Pod's status should become 'stopped'.
    """
    pv = cluster.pvs.add('dummy', 'fakepv', '/nginxpv')
    pod = cluster.pods.create('nginx', 'test_nginx_pod', pvs=[pv],
                              start=True, wait_for_status=POD_STATUSES.running)
    host = pod.info['host']
    pod.stop()
    pod.wait_for_status(POD_STATUSES.stopped)
    with cluster.temporary_stop_host(host):
        new_pod = cluster.pods.create('nginx', 'test_nginx_pod_new',
                                      pvs=[pv],
                                      start=False)
        new_pod.start()
        new_pod.wait_for_status(POD_STATUSES.pending)
        new_pod.wait_for_status(POD_STATUSES.stopped)


@pipeline('move_pods')
@pipeline('move_pods_aws')
def test_pod_not_start_with_pv_on_shut_down_host(cluster):
    # type: (KDIntegrationTestAPI) -> None
    """
    Tests that pod will not be able to start, if it has the persistent volume
    on the node that is in troubles state.
    This is a test for https://cloudlinux.atlassian.net/browse/AC-4087

    Specifically, the behaviour is follows:
    1. Create the pod with persistent volume 'pv'.
    2. Delete pod and persistent volume 'pv'.
    3. Create the pod with persistent volume 'pv', which are exactly the same
       as on the first step.
    4. Shut down the pod and the host on which it resides.
    5. Wait till the kubernetes see the host as not working.
    6. Create a new pod with the same persistent volume 'pv'.
    7. Starting the new pod should result in immediate error.
    """
    pv = cluster.pvs.add('dummy', 'pv', '/nginxpv')
    pod = cluster.pods.create('nginx', 'test_nginx_pod', pvs=[pv],
                              start=True, wait_for_status=POD_STATUSES.running)
    pod.delete()
    pv.delete()
    pv = cluster.pvs.add('dummy', 'pv', '/nginxpv')
    pod = cluster.pods.create('nginx', 'test_nginx_pod', pvs=[pv],
                              start=True, wait_for_status=POD_STATUSES.running)
    host = pod.info['host']
    pod.stop()
    pod.wait_for_status(POD_STATUSES.stopped)
    with cluster.temporary_stop_host(host):
        cluster.nodes.get_node(host).wait_for_status(NODE_STATUSES.troubles)
        new_pod = cluster.pods.create('nginx', 'test_nginx_pod_new',
                                      pvs=[pv],
                                      start=False)
        with assert_raises(
                NonZeroRetCodeException,
                "There are no suitable nodes for the pod. Please try"
                " again later or contact KuberDock administrator"):
            new_pod.start()
        assert_eq(new_pod.status, POD_STATUSES.stopped)
