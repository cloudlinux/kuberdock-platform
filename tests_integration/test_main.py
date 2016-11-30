import logging
import time
from urllib2 import HTTPError

from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.utils import (
    assert_eq, gen_rnd_ceph_pv_name, assert_raises)

LOG = logging.getLogger(__name__)


@pipeline('main')
@pipeline('main_aws')
def test_cadvisor_errors(cluster):
    # type: (KDIntegrationTestAPI) -> None
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
@pipeline('main_aws')
def test_a_pv_created_together_with_pod(cluster):
    # type: (KDIntegrationTestAPI) -> None
    # We have issue related to using non-unique disk names within
    # same CEPH pool (AC-3831). That is why name is randomized.
    pv_name = gen_rnd_ceph_pv_name()

    mount_path = '/usr/share/nginx/html'

    # It is possible to create an nginx pod together with new PV
    pv = cluster.pvs.add("dummy", pv_name, mount_path)
    pod = cluster.pods.create("nginx", "test_nginx_pod_1", pvs=[pv],
                              start=True, wait_for_status='running',
                              wait_ports=True, ports_to_open=(80, ))
    assert_eq(pv.exists(), True)

    c_id = pod.get_container_id(container_image='nginx')
    pod.docker_exec(c_id,
                    'echo -n TEST > {path}/test.txt'.format(path=mount_path))
    ret = pod.do_GET(path='/test.txt')
    assert_eq('TEST', ret)
    pod.delete()

    # It is possible to create an nginx pod using existing PV
    pod = cluster.pods.create("nginx", "test_nginx_pod_2", pvs=[pv],
                              start=True, wait_for_status='running',
                              wait_ports=True, ports_to_open=(80, ))
    ret = pod.do_GET(path='/test.txt')
    assert_eq('TEST', ret)
    pod.delete()

    # It's possible to remove PV created together with pod
    pv.delete()
    assert_eq(pv.exists(), False)

    # Create another PV with the same name
    pv = cluster.pvs.add('dummy', pv_name, mount_path)
    pod = cluster.pods.create(
        'nginx', 'test_nginx_pod_3', pvs=[pv], start=True,
        wait_for_status='running', wait_ports=True, ports_to_open=(80, ))
    assert_eq(pv.exists(), True)

    # '/test.txt' is not on newly created PV, we expect HTTP Error 404
    with assert_raises(HTTPError, 'HTTP Error 404: Not Found'):
        pod.do_GET(path='/test.txt')

    pod.delete()
    pv.delete()
    assert_eq(pv.exists(), False)


@pipeline('main')
@pipeline('main_upgraded')
@pipeline('ceph')
@pipeline('ceph_upgraded')
@pipeline('main_aws')
def test_a_pv_created_separately(cluster):
    # type: (KDIntegrationTestAPI) -> None
    pv_name = gen_rnd_ceph_pv_name()
    pv_size = 2
    mount_path = '/nginxpv'

    # It is possible to create a separate PV
    pv = cluster.pvs.add("new", pv_name, mount_path, pv_size)
    assert pv.exists()
    assert_eq(pv.size, pv_size)

    # It's possible to use separately created PV for nginx pod
    cluster.pods.create("nginx", "test_nginx_pod_3", pvs=[pv],
                        wait_for_status='running')

    # TODO: place correct exception and regexp to args of assertRaisesRegexp
    # TODO: and uncomment the next block. Currently blocked by AC-3689
    '''
    # It's not possible to create pod using assigned PV
    with cluster.assertRaisesRegexp(some_exception, some_regexp):
        pod = cluster.pods.create("nginx", "test_nginx_pod_4",
                                      start=True, wait_ports=False,
                                      wait_for_status='running',
                                      healthcheck=False, pv_size=pv.size,
                                      pv_name=pv.name,
                                      pv_mount_path='/nginxpv')
    '''


@pipeline('main')
@pipeline('main_upgraded')
@pipeline("main_aws")
def test_can_create_pod_without_volumes_and_ports(cluster):
    # type: (KDIntegrationTestAPI) -> None
    # Contents of Docker file utilized to create image:
    # FROM busybox
    # CMD ["/bin/sh", "-c", "while true; do sleep 1; done"]
    cluster.pods.create("apopova/busybox", "test_busybox_pod_1",
                        wait_for_status='running', healthcheck=True)


@pipeline('main')
@pipeline('main_upgraded')
@pipeline("main_aws")
def test_nginx_with_healthcheck(cluster):
    # type: (KDIntegrationTestAPI) -> None
    cluster.pods.create("nginx", "test_nginx_pod_1", ports_to_open=(80, ),
                        start=True, wait_ports=True, healthcheck=True,
                        wait_for_status='running')


@pipeline('main')
@pipeline('main_upgraded')
@pipeline("main_aws")
def test_recreate_pod_with_real_ip(cluster):
    # type: (KDIntegrationTestAPI) -> None
    pod = cluster.pods.create("nginx", "test_nginx_pod_4",
                              ports_to_open=(80, ), wait_ports=True,
                              start=True, wait_for_status='running')
    pod.healthcheck()
    pod.delete()
    pod = cluster.pods.create("nginx", "test_nginx_pod_4",
                              ports_to_open=(80, ), wait_ports=True,
                              start=True, wait_for_status='running')
    pod.healthcheck()
    pod.delete()


@pipeline('main')
@pipeline('main_upgraded')
@pipeline("main_aws")
def test_nginx_kublet_resize(cluster):
    # type: (KDIntegrationTestAPI) -> None
    pod = cluster.pods.create("nginx", "test_nginx_pod_1",
                              ports_to_open=(80, ),
                              start=True, wait_ports=True, healthcheck=True,
                              wait_for_status='running')
    pod.change_kubes(kubes=2, container_image='nginx')
    time.sleep(20)
    pod.wait_for_ports()
    pod.healthcheck()

@pipeline("main")
@pipeline("main_aws")
def test_start_pod_and_reboot_node(cluster):
    node = cluster.nodes.get_node("node1")
    pod = cluster.pods.create("nginx", "nginx_pod", ports_to_open=[80],
                              wait_ports=True, healthcheck=True)

    node.reboot()
    pod.wait_for_status("running")
    pod.healthcheck()
