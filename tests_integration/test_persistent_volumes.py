import logging
import os
from time import sleep

from tests_integration.lib.pipelines import pipeline
from tests_integration.lib import utils
from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.pod import Port

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


ZFS_POOL = 'kdstorage00'
ZFS_POOL_MOUNTPOINT = '/var/lib/kuberdock/storage'
GREP_EXIT_CODES = (1, )
CEPH_DISK_QUOTA_EXCEEDED_MSG = 'No space left on device'
ZFS_DISK_QUOTA_EXCEEDED_MSG = 'Disk quota exceeded'
LVM_DISK_QUOTA_EXCEEDED_MSG = 'No space left on device'

DISK_QUOTA_EXCEEDED_MSGS = '({}|{}|{})'.format(
    CEPH_DISK_QUOTA_EXCEEDED_MSG, ZFS_DISK_QUOTA_EXCEEDED_MSG,
    LVM_DISK_QUOTA_EXCEEDED_MSG)


@pipeline('main')
@pipeline('main_upgraded')
@pipeline('zfs')
@pipeline('zfs_upgraded')
@pipeline('ceph')
@pipeline('ceph_upgraded')
@pipeline('zfs_aws')
@pipeline('zfs_aws_upgraded')
def test_two_pods_cant_use_same_pv(cluster):
    pv = cluster.pvs.add('dummy', 'nginxpv', '/nginxpv')
    pod1 = cluster.pods.create(
        'nginx', 'test_nginx_pod_1', pvs=[pv], start=True,
        wait_for_status='running')
    pod2 = cluster.pods.create('nginx', 'test_nginx_pod_2', pvs=[pv],
                               start=False)

    utils.log_debug("Try to start 'pod2' that uses the same PV as 'pod1'", LOG)
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
    pv_name = utils.get_rnd_low_string(prefix='ceph_pv_')
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
        utils.wait_for(lambda: pod.node != prev_node)
        pod.wait_for_status('running')

    utils.log_debug(
        "Delete node '{}' which is hosting the pod. Pod should move to "
        "node '{}'".format(pod.node, prev_node))
    hosting_node = cluster.nodes.get_node(node_name=pod.node)
    hosting_node.delete()

    utils.wait_for(lambda: pod.node == prev_node)
    pod.wait_for_status('running')


@pipeline('main')
@pipeline('main_upgraded')
@pipeline('zfs')
@pipeline('zfs_upgraded')
@pipeline('ceph')
@pipeline('ceph_upgraded')
@pipeline('zfs_aws')
@pipeline('zfs_aws_upgraded')
def test_overuse_pv_quota(cluster):
    """
    Scenario as follows:
    1. Create pod with PV(size 1GB) on it
    2. Write 640MB of data on the attached PV. Operation should complete with
        no errors
    3. Try to write another 512MB of data on the same PV. This should fail,
        due to insufficent disk space
    """
    utils.log_debug('===== Overuse Disk quota =====', LOG)
    pv_name = utils.get_rnd_low_string(prefix='integr_test_disk_')
    mount_path = '/nginxpv'
    pv = cluster.pvs.add('dummy', pv_name, mount_path)
    pod = cluster.pods.create('nginx', 'test_nginx_pod_1', pvs=[pv],
                              start=True, wait_for_status='running')

    container_id = pod.get_container_id(container_image='nginx')
    # write 640MB to PV
    cmd1 = 'dd if=/dev/zero of={}/tempfile1 bs=64M ' \
           'count=10'.format(mount_path)
    utils.log_debug('Before wipe out: write 640MBs to disk', LOG)
    pod.docker_exec(container_id, cmd1)

    # should fail, due to insufficent disk space
    with utils.assert_raises(NonZeroRetCodeException,
                             DISK_QUOTA_EXCEEDED_MSGS):
        utils.log_debug('Before wipe out: write 512MBs to disk', LOG)
        cmd2 = 'dd if=/dev/zero of={}/tempfile2 bs=64M count=8'.format(
            mount_path)
        pod.docker_exec(container_id, cmd2)

    utils.log_debug('Restart pod with wipe out', LOG)
    pod.redeploy(wipeOut=True)
    utils.wait_for(
        lambda: container_id != pod.get_container_id(container_image='nginx'))
    pod.wait_for_status('running')
    container_id = pod.get_container_id(container_image='nginx')

    utils.log_debug('After wipe out: write 640MBs to disk', LOG)
    pod.docker_exec(container_id, cmd1)

    with utils.assert_raises(NonZeroRetCodeException,
                             DISK_QUOTA_EXCEEDED_MSGS):
        utils.log_debug('After wipe out: write 512MBs to disk', LOG)
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
    utils.log_debug('===== Delete Node with PV =====', LOG)

    pv_name1 = utils.get_rnd_low_string(prefix='integr_test_disk_')
    mount_path1 = '/nginxpv1'
    pv_name2 = utils.get_rnd_low_string(prefix='integr_test_disk_')
    mount_path2 = '/nginxpv2'

    pv1 = cluster.pvs.add('new', pv_name1, mount_path1)
    pv2 = cluster.pvs.add('new', pv_name2, mount_path2)

    pod1 = cluster.pods.create(
        'nginx', 'test_nginx_pod_1', pvs=[pv1], start=False)
    pod2 = cluster.pods.create(
        'nginx', 'test_nginx_pod_2', pvs=[pv1, pv2], start=True,
        wait_for_status='running')

    hosting_node = cluster.nodes.get_node(pod2.node)

    pod2.stop()
    pod2.wait_for_status('stopped')

    # Try to delete node with pv1 and pv2 on it. Should fail.
    with utils.assert_raises(
        NonZeroRetCodeException,
        "Node 'node1' can't be deleted. Reason: users Persistent volumes "
        "located on the node.*"):
        hosting_node.delete()

    pod2.delete()
    pv2.delete()
    # Try to delete node with pv1 on it. Should fail.
    with utils.assert_raises(
        NonZeroRetCodeException,
        "Node 'node1' can't be deleted. Reason: users Persistent volumes "
        "located on the node.*"):
        hosting_node.delete()

    pod1.delete()
    # pod1 is deleted, but pv1 is still linked to the node.
    # deletion will fail.
    with utils.assert_raises(
        NonZeroRetCodeException,
        "Node 'node1' can't be deleted. Reason: users Persistent volumes "
        "located on the node.*"):
        hosting_node.delete()

    pv1.delete()
    # no pvs left on node, so it can be deleted with no problem.
    hosting_node.delete()


@pipeline('zfs')
@pipeline('zfs_upgraded')
def test_add_new_block_device(cluster):
    """
    Add a new block device into ZFS pool (Non-AWS)
    """
    for node in cluster.node_names:
        utils.log_debug("Add new block device to node '{}'".format(node), LOG)
        # NOTE: Generate a new file each time, so that if test is run on a
        # cluster multiple times nothing is broken, otherwise if we attach two
        # volumes with the same name, ZFS pool will be broken.
        # FIXME: Tried to detach the volume after the test is complete, but
        # couldn't figure out how to do it properly.
        of_path = utils.get_rnd_low_string(prefix='/tmp/dev', length=5)

        write_file_cmd = 'dd if=/dev/zero of="{}" bs=64M count=10'.format(
            of_path)
        cluster.ssh_exec(node, write_file_cmd)

        add_bl_device_cmd = (
            'node-storage add-volume --hostname {} ''--devices {}'.format(
                node, of_path))
        cluster.manage(add_bl_device_cmd)

        utils.log_debug("Make sure a new block device is added", LOG)
        _, out, _ = cluster.ssh_exec(node, 'zpool status', sudo=True)
        utils.assert_in(of_path, out)


@pipeline('zfs')
@pipeline('zfs_upgraded')
@pipeline('zfs_aws')
@pipeline('zfs_aws_upgraded')
def test_zfs_volumes_mount_properly(cluster):
    """
    Automate TestRail case: Deploy with ZFS parameter

    https://cloudlinux.testrail.net/index.php?/cases/view/81
    """
    image = 'nginx'
    pv_name = utils.get_rnd_low_string(prefix='zfs_pv_')
    pv_mpath = '/usr/share/nginx/html'
    pv = cluster.pvs.add('dummy', pv_name, pv_mpath)
    pod = cluster.pods.create(
        image, 'nginx_zfs_volume_mounts', pvs=[pv],
        ports=[Port(80, public=True)], start=True, wait_for_status='running',
        wait_ports=True)

    pod_owner = cluster.users.get(name=pod.owner)
    pv_mountpoint = os.path.join(ZFS_POOL_MOUNTPOINT, str(pod_owner.get('id')),
                                 pv_name)
    check_volume_mounts(cluster, pod, log_msg_prefix='BEFORE NODE REBOOT: ')

    utils.log_debug("Write a file 'test.txt' to PV and get it via HTTP", LOG)
    c_id = pod.get_container_id(container_image=image)
    pod.docker_exec(c_id, 'echo -n TEST > {}/test.txt'.format(pv_mpath))
    ret = pod.do_GET(path='/test.txt')
    utils.assert_eq('TEST', ret)

    # Reboot Node
    cluster.nodes.get_node(pod.node).reboot()

    utils.wait_for(lambda: c_id != pod.get_container_id(container_image=image))
    pod.wait_for_ports()

    check_volume_mounts(cluster, pod, log_msg_prefix='AFTER NODE REBOOT: ')

    utils.log_debug(
        "Make sure that we can get 'test.txt' via HTTP after node reboot",
        LOG)
    ret = pod.do_GET(path='/test.txt')
    utils.assert_eq('TEST', ret)

    c_id = pod.get_container_id(container_image=image)

    utils.log_debug('Restart Pod and check that volumes are mounted correctly')
    pod.redeploy()

    utils.wait_for(lambda: c_id != pod.get_container_id(container_image=image))
    pod.wait_for_status('running')

    check_volume_mounts(cluster, pod, log_msg_prefix='AFTER POD RESTART: ')

    node = pod.node
    pod.delete()
    pv.delete()

    utils.log_debug(
        "Make sure that '{}' is not mounted after PV deletion".format(pv_name),
        LOG)
    with utils.assert_raises(NonZeroRetCodeException,
                             expected_ret_codes=GREP_EXIT_CODES):
        utils.retry(
            assert_volume_mounts, cluster=cluster, mountpoint=pv_mountpoint,
            node=node, assertion=utils.assert_not_in, tries=3, interval=60)

    utils.log_debug(
        "Make sure that '{}' is not in mountpoints".format(pv_name), LOG)
    pool_path = os.path.join(ZFS_POOL, str(pod_owner.get('id')), pv_name)

    with utils.assert_raises(NonZeroRetCodeException,
                             'dataset does not exist'):
        utils.retry(
            assert_zfs_mount_points, cluster=cluster, pool_path=pool_path,
            volume_mp=pv_mountpoint, node=node, assertion=utils.assert_not_in,
            tries=3, interval=60)


def check_volume_mounts(cluster, pod, log_msg_prefix=''):
    utils.log_debug(
        "{}Run 'sudo zpool list' and make sure that '{}' is there".format(
            log_msg_prefix, ZFS_POOL), LOG)
    _, out, _ = cluster.ssh_exec(pod.node, 'zpool list', sudo=True)
    utils.assert_in(ZFS_POOL, out)

    for pv in pod.pvs:
        pod_owner = cluster.users.get(name=pod.owner)
        pv_mountpoint = os.path.join(
            ZFS_POOL_MOUNTPOINT, str(pod_owner.get('id')), pv.name)
        pool_path = os.path.join(
            ZFS_POOL, str(pod_owner.get('id')), pv.name)
        utils.log_debug("{}Run 'zfs list' and check that '{}' is there".format(
            log_msg_prefix, pv.name), LOG)

        _, out, _ = cluster.ssh_exec(pod.node, 'zfs list', sudo=True)
        utils.assert_in(pv.name, out)

        # This may look redundant, but it's here only to be consistent with
        # test inside TestRail
        utils.log_debug(
            "{}Make sure that '{}' is mounted".format(
                log_msg_prefix, pv.name), LOG)
        assert_volume_mounts(cluster, pv_mountpoint, pod.node, utils.assert_in)

        utils.log_debug(
            "{}Make sure that '{}' has a correct mountpoint".format(
                log_msg_prefix, pv.name), LOG)

        assert_zfs_mount_points(
            cluster, pool_path, pv_mountpoint, node=pod.node,
            assertion=utils.assert_in)


def assert_volume_mounts(
        cluster, mountpoint, node='node1', assertion=utils.assert_in):
    _, out, _ = cluster.ssh_exec(
        node, 'mount | grep {}'.format(mountpoint), sudo=True)
    assertion(mountpoint, out)


def assert_zfs_mount_points(
        cluster, pool_path, volume_mp, node='node1',
        assertion=utils.assert_in):
    _, out, _ = cluster.ssh_exec(
        node, 'zfs get mountpoint {}'.format(pool_path), sudo=True)
    assertion(volume_mp, out)
