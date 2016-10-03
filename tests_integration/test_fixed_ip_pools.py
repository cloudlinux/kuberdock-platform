from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.integration_test_utils import \
    NO_FREE_IPS_ERR_MSG, assert_raises, assert_eq, \
    pod_factory
from tests_integration.lib.pipelines import pipeline

create_new_pods = pod_factory('nginx', start=True)


@pipeline('fixed_ip_pools')
def test_cannot_create_pod_with_public_ip_with_no_pools(cluster):
    with assert_raises(NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG):
        create_new_pods(cluster, num=1, open_all_ports=True)

    assert_eq(cluster.pods.filter_by_owner(), [])


@pipeline('fixed_ip_pools')
def test_can_create_pod_without_public_ip_with_no_ip_pools(cluster):
    create_new_pods(cluster, num=1, open_all_ports=False,
                    wait_for_status='running')


@pipeline('fixed_ip_pools')
def test_cannot_add_pod_if_no_free_ips_available(cluster):
    expected_pod_count = 3
    # 2 IP addresses in a network
    cluster.ip_pools.add('192.168.0.0/31', 'node1')
    # 1 IP address in a network
    cluster.ip_pools.add('192.168.1.0/32', 'node2')

    pods = create_new_pods(cluster, expected_pod_count,
                           open_all_ports=True,
                           wait_for_status='running')

    with assert_raises(NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG):
        create_new_pods(cluster, num=1, open_all_ports=True)

    # Make sure there are still expected_pod_count of pods
    assert_eq(len(cluster.pods.filter_by_owner()), expected_pod_count)

    # Remove a pod to free an IP an try to add a new one - should succeed
    pods[0].delete()
    create_new_pods(cluster, num=1, open_all_ports=True,
                    wait_for_status='running')

    # It's not possible to create a pod once again
    with assert_raises(NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG):
        create_new_pods(cluster, num=1, open_all_ports=True)

    # But it's possible to create a pod without a public IP
    create_new_pods(cluster, open_all_ports=False, wait_for_status='running')

    # Make sure there are +1 pods
    pod_count = len(cluster.pods.filter_by_owner())
    assert_eq(pod_count, expected_pod_count + 1)


# NOTE: Uncomment with new k8s version which includes rename to fixed-ip-pools
# @pipeline('fixed_ip_pools')
def test_pods_are_not_created_on_node_without_free_ips(cluster):
    # 2 IP addresses in a network
    cluster.ip_pools.add('192.168.0.0/30', 'node1')

    create_new_pods(cluster, num=2, open_all_ports=True,
                    wait_for_status='running')

    node_names = (n['host'] for n in cluster.pods.filter_by_owner())
    assert (all(n == 'node1' for n in node_names)),\
        "Not all pods created in node1. Created at nodes '{}'".format(node_names)
