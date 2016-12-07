import logging
from time import sleep

from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.utils import (
    get_rnd_low_string, assert_raises, log_debug,
    wait_for)
from tests_integration.lib.exceptions import NonZeroRetCodeException

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


@pipeline('main')
@pipeline('ceph')
@pipeline('zfs')
@pipeline('main_upgraded')
@pipeline('ceph_upgraded')
@pipeline('zfs_upgraded')
def test_two_pods_cant_use_same_pv(cluster):
    pv = cluster.pvs.add('dummy', 'nginxpv', '/nginxpv')
    pod1 = cluster.pods.create(
        'nginx', 'test_nginx_pod_1', pvs=[pv], start=True,
        wait_for_status='running')
    pod2 = cluster.pods.create('nginx', 'test_nginx_pod_2', pvs=[pv],
                               start=False)

    log_debug("Try to start 'pod2' that uses the same PV as 'pod1'", LOG)
    pod2.start()

    # FIXME: Need a proper way to determain that some resources where not
    # available when we tried to start the pod
    sleep(120)
    pod2.wait_for_status('stopped')

    pod1.delete()
    pod2.delete()
    pv.delete()


@pipeline('ceph')
@pipeline('ceph_upgraded')
def test_move_pods_and_delete_node_with_ceph_storage(cluster):
    pv_name = get_rnd_low_string(prefix='ceph_pv_')
    pv_mpath = '/nginxpv'
    pv = cluster.pvs.add('dummy', pv_name, pv_mpath)
    # NOTE: we want to make sure that pod lands on 'node1', because 'node4'
    # will be deleted later on.
    with cluster.temporary_stop_host('node4'):
        pod = cluster.pods.create('nginx', 'test_nginx_pod_1', pvs=[pv],
                                  start=False)
        pod.start()
        pod.wait_for_status('running')

    prev_node = pod.node
    with cluster.temporary_stop_host(prev_node):
        wait_for(lambda: pod.node != prev_node)
        pod.wait_for_status('running')

    log_debug("Delete node '{}' which is hosting the pod. Pod should move to "
              "node '{}'".format(pod.node, prev_node))
    hosting_node = cluster.nodes.get_node(node_name=pod.node)
    hosting_node.delete()

    wait_for(lambda: pod.node == prev_node)
    pod.wait_for_status('running')


@pipeline('main')
@pipeline('zfs')
@pipeline('ceph')
@pipeline('main_upgraded')
@pipeline('zfs_upgraded')
@pipeline('ceph_upgraded')
def test_overuse_pv_quota(cluster):
    """
    Scenario as follows:
    1. Create pod with PV(size 1GB) on it
    2. Write 640MB of data on the attached PV. Operation should complete with
        no errors
    3. Try to write another 512MB of data on the same PV. This should fail,
        due to insufficent disk space
    """
    log_debug('===== Overuse Disk quota =====', LOG)
    pv_name = get_rnd_low_string(prefix='integr_test_disk_')
    mount_path = '/nginxpv'
    pv = cluster.pvs.add('dummy', pv_name, mount_path)
    pod = cluster.pods.create('nginx', 'test_nginx_pod_1', pvs=[pv],
                              start=True, wait_for_status='running')

    containers = pod.containers
    container_id = containers[0]['containerID']
    # write 640MB to PV
    cmd1 = 'dd if=/dev/zero of={}/tempfile1 bs=64M ' \
           'count=10'.format(mount_path)
    pod.docker_exec(container_id, cmd1)

    # should fail, due to insufficent disk space
    with assert_raises(NonZeroRetCodeException):
        cmd2 = 'dd if=/dev/zero of={}/tempfile2 bs=64M count=8'.format(
            mount_path)
        pod.docker_exec(container_id, cmd2)

    pod.delete()
    pv.delete()


@pipeline('delete_node')
def test_delete_node_with_pv(cluster):
    """
    Scenario as follows:
    1. Create 2 pods(pod1, pod2) with PVs(pv1, pv2).
    2. Try to delete node. This should fail.
    3. Delete pod2 and pv2.
    4. Try to delete node. This should fail again.
    5. Delete pod1.
    6. Try to delete node. This shuild fail again.
    7. Delete pv1.
    8. Delete node. Node should be deleted.
    """
    log_debug('===== Delete Node with PV =====', LOG)

    pv_name1 = get_rnd_low_string(prefix='integr_test_disk_')
    mount_path1 = '/nginxpv1'
    pv_name2 = get_rnd_low_string(prefix='integr_test_disk_')
    mount_path2 = '/nginxpv2'

    pv1 = cluster.pvs.add('new', pv_name1, mount_path1)
    pv2 = cluster.pvs.add('new', pv_name2, mount_path2)

    pod1 = cluster.pods.create(
        'nginx', 'test_nginx_pod_1', pvs=[pv1], start=False)
    pod2 = cluster.pods.create(
        'nginx', 'test_nginx_pod_2', pvs=[pv1, pv2], start=True,
        wait_for_status='running')

    hosting_node = cluster.nodes.get_node(pod1.node)

    pod2.stop()
    pod2.wait_for_status('stopped')

    # Try to delete node with pv1 and pv2 on it. Should fail.
    with assert_raises(
        NonZeroRetCodeException,
        "Node 'node1' can't be deleted. Reason: users Persistent volumes "
        "located on the node.*"):
        hosting_node.delete()

    pod2.delete()
    pv2.delete()
    # Try to delete node with pv1 on it. Should fail.
    with assert_raises(
        NonZeroRetCodeException,
        "Node 'node1' can't be deleted. Reason: users Persistent volumes "
        "located on the node.*"):
        hosting_node.delete()

    pod1.delete()
    # pod1 is deleted, but pv1 is still linked to the node.
    # deletion will fail.
    with assert_raises(
        NonZeroRetCodeException,
        "Node 'node1' can't be deleted. Reason: users Persistent volumes "
        "located on the node.*"):
        hosting_node.delete()

    pv1.delete()
    # no pvs left on node, so it can be deleted with no problem.
    hosting_node.delete()
