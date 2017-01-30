
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import logging
import os
import re
from time import sleep

from tests_integration.lib import utils
from tests_integration.lib.cluster_utils import add_pa_from_url
from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.pipelines import pipeline
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
        wait_for_status=utils.POD_STATUSES.running)
    pod2 = cluster.pods.create('nginx', 'test_nginx_pod_2', pvs=[pv],
                               start=False)

    utils.log_debug("Try to start 'pod2' that uses the same PV as 'pod1'", LOG)
    pod2.start()

    # FIXME: Need a proper way to determain that some resources where not
    # available when we tried to start the pod
    sleep(120)
    pod2.wait_for_status(utils.POD_STATUSES.stopped)

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
        cluster.nodes.get_node('node4').wait_for_status(
            utils.NODE_STATUSES.troubles)
        pod = cluster.pods.create('nginx', 'test_nginx_pod_1', pvs=[pv],
                                  start=False)
        pod.start()
        pod.wait_for_status(utils.POD_STATUSES.running)

    prev_node = pod.node
    with cluster.temporary_stop_host(prev_node):
        cluster.nodes.get_node(prev_node).wait_for_status(
            utils.NODE_STATUSES.troubles)
        utils.wait_for(lambda: pod.node != prev_node)
        pod.wait_for_status(utils.POD_STATUSES.running)

    utils.log_debug(
        "Delete node '{}' which is hosting the pod. Pod should move to "
        "node '{}'".format(pod.node, prev_node))
    hosting_node = cluster.nodes.get_node(node_name=pod.node)
    hosting_node.delete()

    utils.wait_for(lambda: pod.node == prev_node)
    pod.wait_for_status(utils.POD_STATUSES.running)


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
    pod = cluster.pods.create(
        'nginx', 'test_nginx_pod_1', pvs=[pv], start=True,
        wait_for_status=utils.POD_STATUSES.running)

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
    pod.wait_for_status(utils.POD_STATUSES.running)
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
        wait_for_status=utils.POD_STATUSES.running)

    hosting_node = cluster.nodes.get_node(pod2.node)

    pod2.stop()
    pod2.wait_for_status(utils.POD_STATUSES.stopped)

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
        ports=[Port(80, public=True)], start=True, wait_ports=True,
        wait_for_status=utils.POD_STATUSES.running)

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
    pod.wait_for_status(utils.POD_STATUSES.running)

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


@pipeline('main')
@pipeline('main_upgraded')
@pipeline('zfs')
@pipeline('zfs_upgraded')
@pipeline('zfs_aws')
def test_resize_pv_of_custom_docker_hub_pod(cluster):
    NGINX_IMAGE = 'nginx'
    pv_name = utils.get_rnd_string(prefix='custom_pod_resizable_pv_')
    pv_mpath = '/nginxpv'
    pv = cluster.pvs.add('dummy', pv_name, pv_mpath, size=1)
    pod = cluster.pods.create(
        NGINX_IMAGE, 'test_pod_for_resizable_pvs', pvs=[pv], start=True,
        wait_for_status='running')

    pv_id = pv.info()['id']

    _test_resize_pv(cluster, pod, NGINX_IMAGE, pv_mpath, pv_id)


@pipeline('main')
@pipeline('main_upgraded')
@pipeline('zfs')
@pipeline('zfs_upgraded')
@pipeline('zfs_aws')
def test_resize_pv_of_pa(cluster):
    WP_IMAGE = 'kuberdock/wordpress:4.6.1-1'  # FIXME: Update me, when wordpress image changes.  # noqa
    wp_pa = cluster.pods.create_pa(
        'wordpress.yaml', wait_for_status='running', wait_ports=True,
        plan_id=1)

    # Retrieve PV mount path
    pa_spec = wp_pa.get_spec()
    container_spec = next(c for c in pa_spec['containers']
                          if c['image'] == WP_IMAGE)
    vol_mounts = container_spec['volumeMounts']
    pv_inner_name = vol_mounts[0]['name']
    pv_mpath = vol_mounts[0]['mountPath']

    pv_name = next(v['persistentDisk']['pdName'] for v in pa_spec['volumes']
                   if v['name'] == pv_inner_name)

    _, out, _ = cluster.kcli2('pstorage get --name {}'.format(pv_name),
                              out_as_dict=True)
    pv_id = out['data']['id']

    _test_resize_pv(cluster, wp_pa, WP_IMAGE, pv_mpath, pv_id,
                    initial_disk_usage=28)


@pipeline('main')
@pipeline('main_upgraded')
@pipeline('zfs')
@pipeline('zfs_upgraded')
@pipeline('zfs_aws')
@pipeline('ceph')
@pipeline('ceph_upgraded')
def test_wipe_out_persistent_data(cluster):
    """
    1. Create Redis pod
    2. Add records to Redis
    3. Make sure that records are preserved after restarting pod without wiping
    4. Restart the pod with wipe out
    5. MAke sure that record has been removed from Redis
    """
    key = "test_key"
    value = "test_value"

    utils.log_debug("Creating and preparing Redis pod", LOG)
    pa_url = "https://raw.githubusercontent.com/cloudlinux/" \
             "kuberdock_predefined_apps/master/redis.yaml"
    name = add_pa_from_url(cluster, pa_url)
    redis_pod = cluster.pods.create_pa(name,
                                 wait_for_status="running",
                                 healthcheck=True)

    utils.log_debug("Updating the pod by inserting custom key-value pair", LOG)
    redis_pod.redis_set(key, value)
    utils.log_debug("Check that pod has been updated", LOG)
    utils.assert_eq(redis_pod.redis_get(key), value)

    utils.log_debug("Restarting the pod without wiping out", LOG)
    redis_pod.redeploy(wipeOut=False, wait_for_running=True)
    utils.log_debug("Check that pod still contains user data", LOG)
    utils.assert_eq(redis_pod.redis_get(key), value)

    utils.log_debug("Redeploying and wiping out the pod", LOG)
    redis_pod.redeploy(wipeOut=True, wait_for_running=True)
    redis_pod.healthcheck()
    utils.log_debug("Check that pod has been defaulted", LOG)
    utils.assert_eq(redis_pod.redis_get(key), None)


def _test_resize_pv(cluster, pod, container_image, mountpath, pv_id,
                    initial_disk_usage=0):
    """
    Perform writes and resizes on pod Persistent volume
    :param cluster:
    :param pod: KDPod
    :param container_image: If pod has several containers, then we need to
        know which container to use in this test
    :param pv_name: Persistent volume name as it appears in UI
    :param mountpath: Path to FS mount point
    :param pv_id: Persistent volume id inside KD db
    :param initial_disk_usage: Some containers have default data written to
        mounted PVs, so we need to know approximate size in MBs, so that
        we can calculate the disk usage properly
    """
    # Sizes are in GBs
    INITIAL_PV_SIZE = 1
    INCREASED_PV_SIZE = 3
    DECREASED_PV_SIZE1 = 2
    DECREASED_PV_SIZE2 = 1

    total_write_amount = initial_disk_usage  # in MBs

    file1_name = utils.get_rnd_string(prefix='file_')
    file2_name = utils.get_rnd_string(prefix='file_')
    file3_name = utils.get_rnd_string(prefix='file_')

    utils.log_debug('Check that back-end supports PV resize', LOG)

    _, out, _ = cluster.manage('persistent-volume is-resizable')
    utils.assert_eq('True', out)

    # The default size of PV is 1GB
    c_id = pod.get_container_id(container_image=container_image)

    # Check PV used space
    _assert_disk_usage(pod, c_id, mountpath, total_write_amount,
                       INITIAL_PV_SIZE * 1024)

    # Write to PV here until it's full
    # 512MB
    _write_dummy_file_to_pv(pod, container_image, mountpath, file1_name, bs=64,
                            count=8)
    total_write_amount += 512
    _assert_disk_usage(pod, c_id, mountpath, total_write_amount,
                       INITIAL_PV_SIZE * 1024)

    with utils.assert_raises(NonZeroRetCodeException,
                             DISK_QUOTA_EXCEEDED_MSGS):
        # Try writing 640MB into ~500MB available disk space
        # Only (512 - initial_disk_usage)MB will be written
        _write_dummy_file_to_pv(pod, container_image, mountpath, file2_name,
                                bs=64, count=10)

    # We filled PV in the previous step, now its used size should be equal
    # to PV size
    total_write_amount = INITIAL_PV_SIZE * 1024
    _assert_disk_usage(pod, c_id, mountpath, total_write_amount,
                       INITIAL_PV_SIZE * 1024)

    # Resize PV
    cluster.manage(
        'persistent-volume resize --pv-id {id} --new-size {size}'.format(
            id=pv_id, size=INCREASED_PV_SIZE))

    _assert_disk_usage(pod, c_id, mountpath, total_write_amount,
                       INCREASED_PV_SIZE * 1024)
    # Write again to make sure that size was increased
    # 640MB
    _write_dummy_file_to_pv(pod, container_image, mountpath, file2_name,
                            count=10)
    # One file was overwritten
    total_write_amount += 640 - (512 - initial_disk_usage)

    # 512MB
    _write_dummy_file_to_pv(pod, container_image, mountpath, file3_name,
                            count=8)
    # New file was created
    total_write_amount += 512

    _assert_disk_usage(pod, c_id, mountpath, total_write_amount,
                       INCREASED_PV_SIZE * 1024)
    utils.log_debug(
        'Current PV size: {}GB used space: ~{} new size: {}GB'.format(
            INCREASED_PV_SIZE, '1.6GB', DECREASED_PV_SIZE1), LOG)
    cluster.manage(
        'persistent-volume resize --pv-id {id} --new-size {size}'.format(
            id=pv_id, size=DECREASED_PV_SIZE1))

    # Check PV used space
    _assert_disk_usage(pod, c_id, mountpath, total_write_amount,
                       DECREASED_PV_SIZE1 * 1024)

    # Decrease PV size
    utils.log_debug(
        'Current PV size: {}GB used space: ~{} new size: {}GB'.format(
            DECREASED_PV_SIZE1, '1.6GB', DECREASED_PV_SIZE2), LOG)
    FAILED_TO_RESIZE_MSG = (
        'Failed to resize PV: Volume can not be reduced to {}.00G. Already '
        'used'.format(DECREASED_PV_SIZE2))
    with utils.assert_raises(NonZeroRetCodeException, FAILED_TO_RESIZE_MSG):
        cluster.manage(
            'persistent-volume resize --pv-id {id} --new-size {size}'.format(
                id=pv_id, size=DECREASED_PV_SIZE2))

    _assert_disk_usage(pod, c_id, mountpath, total_write_amount,
                       DECREASED_PV_SIZE1 * 1024)


def _write_dummy_file_to_pv(pod, container_image, mountpath, filename,
                            bs=64, count=8):
    """
    Create a dummy file inside pod's container with image 'container_image' at
    path 'mountpath' and size 'size'MB
    :param pod: KDPod
    :param container_image: Container image of 'pod'
    :param mountpath: PV mountpath where to create a file
    :param size: How many bytes to write
    :param count: Number of records to make
    """
    utils.log_debug('Attempting to write {}MB on PV'.format(bs * count))
    c_id = pod.get_container_id(container_image=container_image)
    cmd = 'dd if=/dev/zero of={mountpath}/{filename} bs={bs}M ' \
          'count={count}'.format(mountpath=mountpath, filename=filename, bs=bs,
                                 count=count)
    pod.docker_exec(c_id, cmd)


def _assert_disk_usage(pod, c_id, pv_path, write_size, disk_size):
    _, out, _ = pod.docker_exec(c_id, 'df {}'.format(pv_path))
    use_percentage = int(1. * write_size / disk_size * 100)
    expected = '({}%|{}%|{}%)'.format(use_percentage - 1, use_percentage,
                                      use_percentage + 1)
    utils.log_debug('Expected sizes: {}'.format(expected), LOG)
    utils.assert_not_eq(re.search(expected, out), None)
