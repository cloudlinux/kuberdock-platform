# coding=utf-8

from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.integration_test_api import KDIntegrationTestAPI


@pipeline('release_update')
def test_release_update(cluster):
    # type: (KDIntegrationTestAPI) -> None
    """Check pods became running after upgrade

    Steps:
        1. Create cluster
        2. Create nginx pod
        3. Create nginx pod with cyrillic name
        4. Create nginx pod with chinese name
        5. Upgrade cluster
        6. Waiting pod became running
        7. Check health of all pods
    """
    # Step 1, 2, 3, 4
    pod1 = cluster.pods.create("nginx", u"test_nginx_pod_1",
                               open_all_ports=False,
                               start=True, wait_ports=True,
                               healthcheck=True,
                               wait_for_status='running')
    pod2 = cluster.pods.create("nginx", u"тест_нжинкс_под_2",
                               open_all_ports=False, start=True,
                               wait_ports=True,
                               healthcheck=True, wait_for_status='running')
    pod3 = cluster.pods.create("nginx", u"測試nginx的莢1",
                               open_all_ports=False,
                               start=True, wait_ports=True,
                               healthcheck=True,
                               wait_for_status='running')
    # Step 5
    cluster.upgrade('/tmp/prebuilt_rpms/kuberdock.rpm',
                    use_testing=True, skip_healthcheck=True)
    # Step 6
    pod1.wait_for_status('running')
    pod2.wait_for_status('running')
    pod3.wait_for_status('running')
    # Step 7
    # TODO: Turned off till release 1.4, because 1.3 can only exclude IPs from
    # one /24 network
    # pod1.healthcheck()
    # pod2.healthcheck()
    # pod3.healthcheck()
