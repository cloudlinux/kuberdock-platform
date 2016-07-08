from tests_integration.lib.integration_test_utils import \
    NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG, assert_raises, assert_eq
from tests_integration.lib.pipelines import pipeline


# TODO: to API add method, which creates IP pools via kdclt instead of
# manage.py then use this method to manage IP pools inside this class
@pipeline('main')
def test_cadvisor_errors(cluster):
    """Check cadvisor error/warning appears in uwsgi (AC-3499)"""

    cluster.kdctl('license show')

    # TODO: Remove once AC-3618 implemented
    cmd = "[ $(journalctl --since '15 min ago' -m -t uwsgi | " \
          "grep -v 'ssl_stapling' | " \
          "egrep 'warn|err' -c) -eq 0 ]"
    cluster.ssh_exec('master', cmd)


@pipeline('main')
def test_a_pv_created_together_with_pod(cluster):
    pv_name = "disk107"
    mount_path = '/nginxpv'

    # It is possible to create an nginx pod together with new PV
    pv = cluster.create_pv("dummy", pv_name, mount_path)
    pod = cluster.create_pod("nginx", "test_nginx_pod_1", pvs=[pv],
                             start=True, wait_ports=True,
                             wait_for_status='running',
                             healthcheck=True)
    assert pv.exists()
    pod.delete()

    # It is possible to create an nginx pod using existing PV
    pod = cluster.create_pod("nginx", "test_nginx_pod_2", pvs=[pv],
                             start=True, wait_ports=True,
                             wait_for_status='running',
                             healthcheck=True)
    pod.delete()

    # It's possible to remove PV created together with pod
    pv.delete()
    assert not pv.exists()


@pipeline('main')
def test_a_pv_created_separately(cluster):
    pv_name = "disk207"
    pv_size = 2
    mount_path = '/nginxpv'

    # It is possible to create a separate PV
    pv = cluster.create_pv("new", pv_name, mount_path, pv_size)
    assert pv.exists()
    assert_eq(pv.size, pv_size)

    # It's possible to use separately created PV for nginx pod
    cluster.create_pod("nginx", "test_nginx_pod_3", pvs=[pv], wait_ports=False,
                       wait_for_status='running',
                       healthcheck=False)

    # TODO: place correct exception and regexp to args of assertRaisesRegexp
    # TODO: and uncomment the next block. Currently blocked by AC-3689
    '''
    # It's not possible to create pod using assigned PV
    with cluster.assertRaisesRegexp(some_exception, some_regexp):
        pod = cluster.create_pod("nginx", "test_nginx_pod_4",
                                      start=True, wait_ports=False,
                                      wait_for_status='running',
                                      healthcheck=False, pv_size=pv.size,
                                      pv_name=pv.name,
                                      pv_mount_path='/nginxpv')
    '''


@pipeline('main')
def test_can_create_pod_without_volumes_and_ports(cluster):
    # Contents of Docker file utilized to create image:
    # FROM busybox
    # CMD ["/bin/sh", "-c", "while true; do sleep 1; done"]
    cluster.create_pod("apopova/busybox", "test_busybox_pod_1",
                       start=True, open_all_ports=False,
                       healthcheck=False, wait_ports=False,
                       wait_for_status='running')


@pipeline('networking')
def test_nginx(cluster):
    # It is possible to create an nginx pod with public IP
    pod = cluster.create_pod("nginx", "test_nginx_pod_1",
                             start=True, wait_ports=True,
                             wait_for_status='running',
                             healthcheck=True)
    pod.delete()

    # It's not possible to create a POD with public IP with no IP pools
    cluster.delete_all_ip_pools()
    with assert_raises(NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG):
        cluster.create_pod("nginx", "test_nginx_pod_2", start=True)

    assert_eq(cluster.get_all_pods(), [])

    # Test if it's possible to create a pod without a public IP
    cluster.create_pod("nginx", "test_nginx_pod_3",
                       start=True, open_all_ports=False,
                       healthcheck=False, wait_ports=False,
                       wait_for_status='running')