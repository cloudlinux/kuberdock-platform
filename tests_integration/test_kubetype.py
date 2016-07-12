from tests_integration.lib.integration_test_utils import assert_eq
from tests_integration.lib.pipelines import pipeline


@pipeline('kubetype')
def test_pod_lands_on_correct_node_given_a_kubetype(cluster):
    # Should land on kd_node1 (see pipeline definition)
    pod1 = cluster.create_pod("nginx", "test_nginx_pod_1",
                              kube_type='Standard')
    # Should land on kd_node2 (see pipeline definition)
    pod2 = cluster.create_pod("nginx", "test_nginx_pod_2", kube_type='Tiny')

    pod1.wait_for_status('running')
    pod2.wait_for_status('running')

    pod_hosts = {n['name']: n['host'] for n in cluster.get_all_pods()}
    cluster.assert_pods_number(2)
    assert_eq(pod_hosts['test_nginx_pod_1'], 'node1')
    assert_eq(pod_hosts['test_nginx_pod_2'], 'node2')
