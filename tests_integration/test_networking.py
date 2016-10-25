
from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.integration_test_utils import \
    NO_FREE_IPS_ERR_MSG, assert_raises, assert_eq
from tests_integration.lib.pipelines import pipeline


@pipeline('networking')
@pipeline('networking_upgraded')
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
                        wait_for_status='running')


@pipeline('networking')
@pipeline('networking_upgraded')
def test_create_delete_ippool(cluster):
    nginx1 = cluster.pods.create("nginx", "test_nginx_pod_1",
                                 open_all_ports=True, start=True,
                                 healthcheck=True, wait_ports=True,
                                 wait_for_status='running')

    with assert_raises(NonZeroRetCodeException,
                       text='.*You cannot delete this network.*',
                       expected_ret_codes=(1,)):
        cluster.ip_pools.clear()

    nginx1.healthcheck()
    nginx1.delete()
    cluster.ip_pools.clear()
