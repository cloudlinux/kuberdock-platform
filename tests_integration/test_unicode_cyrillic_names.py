# coding=utf-8

from tests_integration.lib.pipelines import pipeline


@pipeline('main')
def test_redeploy_pod_with_unicode_name(cluster):
    # Prepare workload with various KD entities with unicode names
    pod1 = cluster.create_pod("nginx", u"АБВЫёяурнв", open_all_ports=True,
                              start=True, wait_ports=True,
                              wait_for_status='running', healthcheck=True)

    cluster.create_user(name=u"юзер", password="qwerty",
                        email="sample@email.com",
                        role="User", active="True", package="Standard package")
    cluster.create_user(name=u"ʓλμβ", password="qwerty",
                        email="sample2@email.com",
                        role="User", active="True", package="Standard package")

    cluster.create_pv(kind="dummy", name=u"ПерсистентВольюм",
                      mount_path='/some_mnt_pth', size=1)
    cluster.create_pv(kind="dummy", name=u"ŷßė",
                      mount_path='/some_mnt_pth', size=1)

    # Test redeploy ability
    pod1.redeploy()
