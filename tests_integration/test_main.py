from tests_integration.lib.integration_test_utils import \
    NO_FREE_IPS_ERR_MSG, assert_raises, assert_eq, get_rnd_string
from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.pipelines import pipeline


@pipeline('main')
def test_cadvisor_errors(cluster):
    """Check cadvisor error/warning appears in uwsgi (AC-3499)"""

    cluster.kdctl('pricing license show')

    # TODO: Remove once AC-3618 implemented
    cmd = "journalctl --since '15 min ago' -m -t uwsgi | " \
          "grep -v 'ssl_stapling' | egrep 'warn|err' | tail -n 100"
    _, out, err = cluster.ssh_exec('master', cmd)
    assert_eq((out + err).strip(), '')


@pipeline('main')
@pipeline('main_upgraded')
@pipeline('ceph')
@pipeline('ceph_upgraded')
def test_a_pv_created_together_with_pod(cluster):
    # We have issue related to using non-unique disk names within
    # same CEPH pool (AC-3831). That is why name is randomized.
    pv_name = _gen_rnd_ceph_pv_name()

    mount_path = '/nginxpv'

    # It is possible to create an nginx pod together with new PV
    pv = cluster.create_pv("dummy", pv_name, mount_path)
    pod = cluster.create_pod("nginx", "test_nginx_pod_1", pvs=[pv],
                             start=True, wait_for_status='running')
    assert pv.exists()
    pod.delete()

    # It is possible to create an nginx pod using existing PV
    pod = cluster.create_pod("nginx", "test_nginx_pod_2", pvs=[pv],
                             start=True, wait_for_status='running')
    pod.delete()

    # It's possible to remove PV created together with pod
    pv.delete()
    assert not pv.exists()


@pipeline('main')
@pipeline('main_upgraded')
@pipeline('ceph')
@pipeline('ceph_upgraded')
def test_a_pv_created_separately(cluster):
    pv_name = _gen_rnd_ceph_pv_name()
    pv_size = 2
    mount_path = '/nginxpv'

    # It is possible to create a separate PV
    pv = cluster.create_pv("new", pv_name, mount_path, pv_size)
    assert pv.exists()
    assert_eq(pv.size, pv_size)

    # It's possible to use separately created PV for nginx pod
    cluster.create_pod("nginx", "test_nginx_pod_3", pvs=[pv],
                       wait_for_status='running')

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
@pipeline('main_upgraded')
def test_can_create_pod_without_volumes_and_ports(cluster):
    # Contents of Docker file utilized to create image:
    # FROM busybox
    # CMD ["/bin/sh", "-c", "while true; do sleep 1; done"]
    cluster.create_pod("apopova/busybox", "test_busybox_pod_1",
                       wait_for_status='running', healthcheck=True)


@pipeline('main')
@pipeline('main_upgraded')
def test_nginx_with_healthcheck(cluster):
    cluster.create_pod("nginx", "test_nginx_pod_1", open_all_ports=True,
                       start=True, wait_ports=True, healthcheck=True,
                       wait_for_status='running')


@pipeline('main')
@pipeline('main_upgraded')
def test_recreate_pod_with_real_ip(cluster):
    pod = cluster.create_pod("nginx", "test_nginx_pod_4", open_all_ports=True,
                             start=True, wait_for_status='running')
    pod.healthcheck()
    pod.delete()
    pod = cluster.create_pod("nginx", "test_nginx_pod_4", open_all_ports=True,
                             start=True, wait_for_status='running')
    pod.healthcheck()
    pod.delete()


@pipeline('networking')
@pipeline('networking_upgraded')
def test_pod_ip_resource(cluster):
    # It's not possible to create a POD with public IP with no IP pools
    cluster.delete_all_ip_pools()
    with assert_raises(NonZeroRetCodeException, NO_FREE_IPS_ERR_MSG):
        cluster.create_pod("nginx", "test_nginx_pod_2", open_all_ports=True,
                           start=True)

    assert_eq(cluster.get_all_pods(), [])

    # It's still possible to create a pod without a public IP
    cluster.create_pod("nginx", "test_nginx_pod_3",
                       start=True, open_all_ports=False,
                       wait_for_status='running')


def _gen_rnd_ceph_pv_name():
    return get_rnd_string(prefix="integr_test_disk_")
