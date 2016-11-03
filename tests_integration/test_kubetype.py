from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.utils import assert_eq, kube_type_to_int
from tests_integration.lib.pipelines import pipeline


@pipeline('kubetype')
def test_pod_lands_on_correct_node_given_a_kubetype(cluster):
    # type: (KDIntegrationTestAPI) -> None
    # Ensure nodes have expected kube types
    for node, kube_type in [('node1', 'Standard'), ('node2', 'Tiny')]:
        info = cluster.nodes.get_node_info(node)
        assert_eq(info['kube_id'], kube_type_to_int(kube_type))

    # Should land on kd_node1 (see pipeline definition)
    pod1 = cluster.pods.create(
        "nginx", "test_nginx_pod_1", kube_type='Standard')
    # Should land on kd_node2 (see pipeline definition)
    pod2 = cluster.pods.create(
        "nginx", "test_nginx_pod_2", kube_type='Tiny')

    pod1.wait_for_status('running')
    pod2.wait_for_status('running')

    pod_hosts = {
        n['name']: n['host'] for n in cluster.pods.filter_by_owner()}

    cluster.assert_pods_number(2)
    assert_eq(pod_hosts['test_nginx_pod_1'], 'node1')
    assert_eq(pod_hosts['test_nginx_pod_2'], 'node2')
