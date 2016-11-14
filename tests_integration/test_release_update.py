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

    pod1 = cluster.pods.create("nginx", u"test_nginx_pod_1",
                               open_all_ports=True, start=True)
    pod2 = cluster.pods.create("nginx", u"тест_нжинкс_под_2",
                               open_all_ports=True, start=True)
    pod3 = cluster.pods.create("nginx", u"測試nginx的莢1",
                               open_all_ports=True, start=True)
    def healthcheck_all():
        for p in (pod1, pod2, pod3):
            p.wait_for_status("running")
            p.wait_for_ports()
            p.healthcheck()
    healthcheck_all()

    cluster.upgrade('/tmp/prebuilt_rpms/kuberdock.rpm',
                    use_testing=True, skip_healthcheck=True)
    cluster.upgrade_rhosts('/tmp/git-kcli-deploy.sh', use_testing=True)

    healthcheck_all()
