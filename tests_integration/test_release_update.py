# coding=utf-8

from tests_integration.lib.pipelines import pipeline


@pipeline('release_update')
def test_release_update(cluster):
    """Check pods became runnig after upgrage

    Steps:
        1. Create cluster
        2. Create nginx pod
        3. Create nginx pod with cyrilic name
        4. Create nginx pod with chinese name
        5. Upgrade cluster
        6. Waiting pod became running
        7. Check health of all pods
    """
    # Step 1, 2, 3, 4
    pod1 = cluster.create_pod("nginx", u"test_nginx_pod_1",
                              open_all_ports=True,
                              start=True, wait_ports=True, healthcheck=True,
                              wait_for_status='running')
    pod2 = cluster.create_pod("nginx", u"тест_нжинкс_под_2",
                              open_all_ports=True, start=True, wait_ports=True,
                              healthcheck=True, wait_for_status='running')
    pod3 = cluster.create_pod("nginx", u"測試nginx的莢1", open_all_ports=True,
                              start=True, wait_ports=True, healthcheck=True,
                              wait_for_status='running')
    # Step 5
    cluster.upgrade('/tmp/prebuilt_rpms/kuberdock.rpm',
                    use_testing=True, skip_healthcheck=True)
    # Step 6
    pod1.wait_for_status('running')
    pod2.wait_for_status('running')
    pod3.wait_for_status('running')
    # Step 7
    pod1.healthcheck()
    pod2.healthcheck()
    pod3.healthcheck()

