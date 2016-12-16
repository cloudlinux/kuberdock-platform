import logging

from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib import utils
from tests_integration.lib.pipelines import pipeline

create_new_pods = utils.pod_factory('nginx', start=True)


LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


@pipeline('fixed_ip_pools')
def test_cannot_create_pod_with_public_ip_with_no_pools(cluster):
    with utils.assert_raises(NonZeroRetCodeException,
                             utils.NO_FREE_IPS_ERR_MSG):
        create_new_pods(cluster, num=1, open_all_ports=True)

    utils.assert_eq(cluster.pods.filter_by_owner(), [])


@pipeline('fixed_ip_pools')
def test_can_create_pod_without_public_ip_with_no_ip_pools(cluster):
    create_new_pods(cluster, num=1, open_all_ports=False,
                    wait_for_status=utils.POD_STATUSES.running)


@pipeline('fixed_ip_pools')
def test_cannot_add_pod_if_no_free_ips_available(cluster):
    expected_pod_count = 3
    # 2 IP addresses in a network
    cluster.ip_pools.add('192.168.0.0/31', 'node1')
    # 1 IP address in a network
    cluster.ip_pools.add('192.168.1.0/32', 'node2')

    pods = create_new_pods(cluster, expected_pod_count,
                           open_all_ports=True,
                           wait_for_status=utils.POD_STATUSES.running)

    with utils.assert_raises(NonZeroRetCodeException,
                             utils.NO_FREE_IPS_ERR_MSG):
        create_new_pods(cluster, num=1, open_all_ports=True)

    # Make sure there are still expected_pod_count of pods
    utils.assert_eq(len(cluster.pods.filter_by_owner()), expected_pod_count)

    # Remove a pod to free an IP an try to add a new one - should succeed
    pods[0].delete()
    create_new_pods(cluster, num=1, open_all_ports=True,
                    wait_for_status=utils.POD_STATUSES.running)

    # It's not possible to create a pod once again
    with utils.assert_raises(NonZeroRetCodeException,
                             utils.NO_FREE_IPS_ERR_MSG):
        create_new_pods(cluster, num=1, open_all_ports=True)

    # But it's possible to create a pod without a public IP
    create_new_pods(cluster, open_all_ports=False,
                    wait_for_status=utils.POD_STATUSES.running)

    # Make sure there are +1 pods
    pod_count = len(cluster.pods.filter_by_owner())
    utils.assert_eq(pod_count, expected_pod_count + 1)


@pipeline('fixed_ip_pools')
def test_pods_are_not_created_on_node_without_free_ips(cluster):
    # 2 IP addresses in a network
    cluster.ip_pools.add('192.168.0.0/30', 'node1')

    create_new_pods(cluster, num=2, open_all_ports=True,
                    wait_for_status=utils.POD_STATUSES.running)

    node_names = (n['host'] for n in cluster.pods.filter_by_owner())
    assert (all(n == 'node1' for n in node_names)),\
        "Not all pods created in node1. Created at nodes '{}'".format(node_names)


@pipeline('fixed_ip_pools')
@utils.hooks(teardown=lambda c: c.nodes.wait_all())
def test_pods_with_public_ip_stop_on_node_failure(cluster):
    cluster.ip_pools.add('192.168.0.0/30', 'node1')
    pod_with_pub_ip = cluster.pods.create(
        'nginx', 'fixed_ip_pools_pod_with_ip', start=True, open_all_ports=True,
        wait_for_status=utils.POD_STATUSES.running)

    utils.log_debug(
        "Check that pod with public port on 'fixed_ip_pools' cluster stops "
        "when hosting node fails", LOG)
    hostname = pod_with_pub_ip.node
    with cluster.temporary_stop_host(hostname):
        cluster.nodes.get_node(hostname).wait_for_status(
            utils.NODE_STATUSES.troubles)
        pod_with_pub_ip.wait_for_status(utils.POD_STATUSES.stopped)


@pipeline('fixed_ip_pools')
@utils.hooks(teardown=lambda c: c.nodes.wait_all())
def test_pods_with_ls_stop_on_node_failure(cluster):
    pv = cluster.pvs.add('dummy', 'nginxpv', '/nginxpv')
    pod_with_pv = cluster.pods.create(
        'nginx', 'fixed_ip_pools_pod_with_pv', pvs=[pv], start=True,
        wait_for_status=utils.POD_STATUSES.running)

    utils.log_debug(
        "Check that pod with LS on 'fixed_ip_pools' cluster stops when "
        "hosting node fails", LOG)
    hostname = pod_with_pv.node
    with cluster.temporary_stop_host(hostname):
        cluster.nodes.get_node(hostname).wait_for_status(
            utils.NODE_STATUSES.troubles)
        pod_with_pv.wait_for_status(utils.POD_STATUSES.stopped)


@pipeline('ceph_fixed_ip_pools')
@utils.hooks(teardown=lambda c: c.nodes.wait_all())
def test_pod_with_ceph_pv_migrates_on_node_failure(cluster):
    pv1 = cluster.pvs.add('dummy', 'nginxpv1', '/nginxpv1')
    pod_with_pv_only = cluster.pods.create(
        'nginx', 'test_ceph_fixed_ip_pod_with_pv_only', start=True, pvs=[pv1],
        wait_for_status=utils.POD_STATUSES.running)
    hostname = pod_with_pv_only.node
    utils.log_debug(
        "Check that pod with CEPH PV and without FIXED IP migrates when "
        "hosting node fails", LOG)
    with cluster.temporary_stop_host(hostname):
        cluster.nodes.get_node(hostname).wait_for_status(
            utils.NODE_STATUSES.troubles)
        utils.wait_for(lambda: pod_with_pv_only.node != hostname)
        pod_with_pv_only.wait_for_status(utils.POD_STATUSES.running)


@pipeline('ceph_fixed_ip_pools')
@utils.hooks(teardown=lambda c: c.nodes.wait_all())
def test_pod_without_pv_and_public_ip_migrates_on_node_failure(cluster):
    pod_without_pv_and_ip = cluster.pods.create(
        'nginx', 'test_ceph_fixed_ip_pod_no_pv_and_ip', start=True,
        wait_for_status=utils.POD_STATUSES.running)

    utils.log_debug(
        "Check that pod without CEPH PV and FIXED IP migrates when hosting "
        "node fails", LOG)
    hostname = pod_without_pv_and_ip.node
    with cluster.temporary_stop_host(hostname):
        cluster.nodes.get_node(hostname).wait_for_status('troubles')
        utils.wait_for(lambda: pod_without_pv_and_ip.node != hostname)
        pod_without_pv_and_ip.wait_for_status(utils.POD_STATUSES.running)


@pipeline('ceph_fixed_ip_pools')
@utils.hooks(teardown=lambda c: c.nodes.wait_all())
def test_pod_with_public_ip_stops_on_node_failure(cluster):
    cluster.ip_pools.add('192.168.0.0/30', 'node1')
    pod_with_ip_only = cluster.pods.create(
        'nginx', 'test_ceph_fixed_ip_pod_with_ip_only', open_all_ports=True,
        start=True, wait_for_status=utils.POD_STATUSES.running)

    hostname = pod_with_ip_only.node
    utils.log_debug(
        "Check that pod without CEPH PV, but with FIXED IP stops when hosting"
        " node fails", LOG)
    with cluster.temporary_stop_host(hostname):
        cluster.nodes.get_node(hostname).wait_for_status(
            utils.NODE_STATUSES.troubles)
        pod_with_ip_only.wait_for_status(utils.POD_STATUSES.stopped)
