# coding=utf-8

from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.utils import POD_STATUSES


@pipeline('release_update')
@pipeline('release_update_aws')
def test_release_update(cluster):
    # type: (KDIntegrationTestAPI) -> None
    """Check pods are OK after upgrade and new ones can be created."""

    pod1 = cluster.pods.create("nginx", u"test_nginx_pod_1",
                               open_all_ports=True, start=True)
    pod2 = cluster.pods.create("nginx", u"тест_нжинкс_под_2",
                               open_all_ports=True, start=True)
    pod3 = cluster.pods.create("nginx", u"測試nginx的莢1",
                               open_all_ports=True, start=True)
    pod4 = cluster.pods.create_pa("dokuwiki.yaml")

    def healthcheck_all():
        for p in (pod1, pod2, pod3, pod4):
            p.wait_for_status(POD_STATUSES.running)
            p.wait_for_ports()
            p.healthcheck()
    healthcheck_all()

    cluster.upgrade('/tmp/prebuilt_rpms/kuberdock.rpm',
                    use_testing=True, skip_healthcheck=True)
    cluster.upgrade_rhosts('/tmp/git-kcli-deploy.sh', use_testing=True)

    # Make sure pods survive after upgrade
    healthcheck_all()
    # Make sure new pods can be created
    cluster.pods.create("nginx", u"test_nginx_pod_after_upgrade",
                        open_all_ports=True, start=True, wait_ports=True,
                        healthcheck=True)
    cluster.pods.create_pa("dokuwiki.yaml", wait_ports=True, healthcheck=True)


@pipeline('release_update_no_nodes')
def test_release_update_no_nodes(cluster):
    # type: (KDIntegrationTestAPI) -> None
    cluster.upgrade('/tmp/prebuilt_rpms/kuberdock.rpm',
                    use_testing=True, skip_healthcheck=True)
