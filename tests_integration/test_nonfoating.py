from tests_integration.lib.integration_test_utils import \
    NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG, assert_raises, assert_eq, \
    pod_factory
from tests_integration.lib.pipeline_utils import pipeline

create_new_pods = pod_factory(
    'nginx', start=True, wait_ports=False, healthcheck=False)


@pipeline('nonfloating')
def test_cannot_create_pod_with_public_ip_with_no_pools(cluster):
    with assert_raises(NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG):
        create_new_pods(cluster, num=1)

    assert_eq(cluster.get_all_pods(), [])


@pipeline('nonfloating')
def test_can_create_pod_without_public_ip_with_no_ip_pools(cluster):
    create_new_pods(cluster, num=1, open_all_ports=False,
                    wait_for_status='running')


@pipeline('nonfloating')
def test_can_not_add_pod_if_no_free_ips_available(cluster):
    expected_pod_count = 3
    # 2 IP addresses in a network
    cluster.add_ip_pool('192.168.0.0/30', 'node1')
    # 1 IP address in a network
    cluster.add_ip_pool('192.168.1.0/32', 'node2')

    pods = create_new_pods(cluster,
                           expected_pod_count, wait_for_status='running')

    with assert_raises(NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG):
        create_new_pods(cluster, num=1)

    # Make sure there are still expected_pod_count of pods
    assert_eq(len(cluster.get_all_pods()), expected_pod_count)

    # Remove a pod to free an IP an try to add a new one - should succeed
    pods[0].delete()
    create_new_pods(cluster, num=1, wait_for_status='running')

    # It's not possible to create a pod once again
    with assert_raises(NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG):
        create_new_pods(cluster, num=1)

    # But it's possible to create a pod without a public IP
    create_new_pods(cluster, open_all_ports=False, wait_for_status='running')

    # Make sure there are +1 pods
    pod_count = len(cluster.get_all_pods())
    assert_eq(pod_count, expected_pod_count + 1)


@pipeline('nonfloating')
def test_pods_are_not_created_on_node_without_free_ips(cluster):
    # 2 IP addresses in a network
    cluster.add_ip_pool('192.168.0.0/30', 'node1')

    create_new_pods(cluster, num=2, wait_for_status='running')

    node_names = (n['host'] for n in cluster.get_all_pods())
    assert (all(n == 'node1' for n in node_names))
