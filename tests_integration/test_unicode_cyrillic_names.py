# coding=utf-8

from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.utils import POD_STATUSES


@pipeline('main')
def test_redeploy_pod_with_unicode_name(cluster):
    # type: (KDIntegrationTestAPI) -> None
    # Prepare workload with various KD entities with unicode names
    pod1 = cluster.pods.create(
        "nginx", u"АБВЫёяурнв", open_all_ports=True, wait_ports=True,
        start=True, wait_for_status=POD_STATUSES.running, healthcheck=True)

    # TODO: We can't user non-ascii usernames :( Uncomment when we can
    # cluster.users.create(name=u"юзер", password="qwerty",
    #                      email="sample@email.com",
    #                      role="User", active="True",
    #                      package="Standard package")
    # cluster.users.create(name=u"ʓλμβ", password="qwerty",
    #                      email="sample2@email.com",
    #                      role="User", active="True",
    #                      package="Standard package")

    # TODO: We can't also create non-ascii persistent volumes. Uncomment
    # when we can
    # cluster.pvs.add(kind="new", name=u"ПерсистентВольюм",
    #                mount_path='/some_mnt_pth', size=1)
    # cluster.pvs.add(kind="new", name=u"ŷßė", mount_path='/some_mnt_pth',
    #                size=1)

    # Test redeploy ability
    pod1.redeploy(wipeOut=True)
