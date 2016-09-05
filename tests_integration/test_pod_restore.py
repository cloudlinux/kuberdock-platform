import json

from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.integration_test_utils import (
    assert_in, assert_raises, assert_eq, assert_not_eq, hooks, http_share)
from tests_integration.lib.pipelines import pipeline

USER = "test_user"
USER_ID = 3

NGINX_WITHOUT_PV = 'nginx_without_pv'
NGINX_WITH_PV = 'nginx_with_pv'
NGINX_CONTAINER_NAME = "server_with_backup_archive"

BACKUP_FILES = {
    NGINX_WITH_PV: "/nginx_pv.json",
    NGINX_WITHOUT_PV: "/nginx_no_pv.json",
}


def setup_non_pv_test(cluster):
    """:type cluster: KDIntegrationTestAPI"""
    _generate_restore_file_without_pv(cluster)


def setup_pv_test(cluster):
    """:type cluster: KDIntegrationTestAPI"""
    _prepare_server_with_backup_archive(cluster)
    _generate_restore_file_with_pv(cluster)


@pipeline('pod_restore')
@pipeline('pod_restore_upgraded')  # TODO: Drop in 1.4 release
@hooks(setup=setup_non_pv_test)
def test_restore_pod_from_cmd(cluster):
    """Test that pod can be restored from the cmd
    and that pod can't be restored if is't name is already in use.

    :type cluster: KDIntegrationTestAPI
    """
    # Test that pod can be restored from the cmd
    file_name = BACKUP_FILES[NGINX_WITHOUT_PV]
    _, pod_dump, _ = cluster.ssh_exec("master",
                                      "cat {}".format(file_name))
    pod = cluster.pods.restore(USER, pod_dump=pod_dump)
    pod.wait_for_ports()


@pipeline('pod_restore')
@pipeline('pod_restore_upgraded')  # TODO: Drop in 1.4 release
@hooks(setup=setup_non_pv_test)
def test_restore_from_file(cluster):
    """Test that pod without PVs can be restored from json-file.

    :type cluster: KDIntegrationTestAPI
    """
    file_name = BACKUP_FILES[NGINX_WITHOUT_PV]
    pod = cluster.pods.restore(USER, file_path=file_name)
    pod.wait_for_ports()
    cluster.assert_pods_number(1)


@pipeline('pod_restore')
@pipeline('pod_restore_upgraded')  # TODO: Drop in 1.4 release
@hooks(setup=setup_pv_test)
def test_pod_with_pv_restore(cluster):
    """Test that pod with PVs can be restored.

    :type cluster: KDIntegrationTestAPI
    """
    file_name = BACKUP_FILES[NGINX_WITH_PV]
    backup_url = "http://node1/backups"
    path_template = '{owner_id}/{volume_name}.tar.gz'
    # Test that pod with persistent volume can be restored
    pod = cluster.pods.restore(USER, file_path=file_name,
                               pv_backups_location=backup_url,
                               pv_backups_path_template=path_template,
                               wait_for_status="running")
    pod.wait_for_ports()
    assert_in("This page has been restored from tar.gz",
              pod.do_GET(path='/restored_location/'))
    old_id = pod.pod_id

    # Test that pod isn't removed if pod with same name is restored with
    # --force-not-delete flag
    with assert_raises(NonZeroRetCodeException,
                       'Pod with name .* already exists'):
        cluster.pods.restore(USER, file_path=file_name,
                             pv_backups_location=backup_url,
                             pv_backups_path_template=path_template,
                             flags="--force-not-delete")
    # If pod has't been restored, it's id should not be changed
    assert_eq(old_id, pod.pod_id)

    # Test that pod is removed together with disks if pod with same name
    # and same disks names is restored with --force-delete flag
    path_template = '{owner_name}/{volume_name}.zip'
    pod2 = cluster.pods.restore(USER, file_path=file_name,
                                pv_backups_location=backup_url,
                                pv_backups_path_template=path_template,
                                flags="--force-delete",
                                return_as_json=True)
    # If pod was restored than it's id should distinguish from id of pod
    # with same name, that has just been removed
    assert_not_eq(old_id, pod2.pod_id)
    pod2.wait_for_ports()
    assert_in("This page has been restored from zip",
              pod.do_GET(path='/restored_location/'))


def _generate_restore_file_with_pv(cluster):
    """:type cluster: KDIntegrationTestAPI"""

    file_name = BACKUP_FILES[NGINX_WITH_PV]
    if not _exists_on_master(cluster, file_name):
        pod_with_pv, pv = _create_nginx_pod_with_pv(cluster)
        pod_dump = pod_with_pv.get_dump()
        with open('tests_integration/assets/pod_backups{}'
                          .format(file_name), "w") as f:
            json.dump(pod_dump, f)
        _copy_backup_to_master(cluster, file_name)
        pod_with_pv.delete()
        pv.delete()


def _generate_restore_file_without_pv(cluster):
    """:type cluster: KDIntegrationTestAPI"""

    file_name = BACKUP_FILES[NGINX_WITHOUT_PV]
    if not _exists_on_master(cluster, file_name):
        pod_without_pv = _create_nginx_pod_without_pv(cluster)
        pod_dump = pod_without_pv.get_dump()
        with open('tests_integration/assets/pod_backups{}'
                          .format(file_name), "w") as f:
            json.dump(pod_dump, f)
        _copy_backup_to_master(cluster, file_name)
        pod_without_pv.delete()


def _exists_on_master(cluster, file_path):
    """:type cluster: KDIntegrationTestAPI"""
    cmd = "[ -f {} ]".format(file_path)
    try:
        # if file is not accessible by the path, then RetCode will be 1
        _, stdout, _ = cluster.ssh_exec("master", cmd)
        return True
    except NonZeroRetCodeException:
        return False


def _create_nginx_pod_with_pv(cluster):
    """:type cluster: KDIntegrationTestAPI"""
    pv_name = "disk_to_restore"
    mount_path = "/usr/share/nginx/html"
    pod_name = "nginx_with_pv"
    pv = cluster.pvs.add("dummy", pv_name, mount_path)
    pod = cluster.pods.create("nginx", pod_name, pvs=[pv],
                              start=True, wait_for_status='running',
                              open_all_ports=True)
    return pod, pv


def _create_nginx_pod_without_pv(cluster):
    """:type cluster: KDIntegrationTestAPI"""
    pod_name = "nginx_without_pv"
    pod = cluster.pods.create("nginx", pod_name, start=True,
                              wait_for_status='running',
                              open_all_ports=True)
    return pod


def _copy_backup_to_master(cluster, file_name):
    """:type cluster: KDIntegrationTestAPI"""
    ssh = cluster.get_ssh("master")
    sftp = ssh.open_sftp()
    sftp.get_channel().settimeout(10)
    sftp.put('tests_integration/assets/pod_backups{}'.format(file_name),
             file_name)


def _prepare_server_with_backup_archive(cluster):
    """
    Create folders for backup archive on master.
    Copy archive with backup archive to master.
    Start web server on master.
    :type cluster: KDIntegrationTestAPI
    """

    # create folders
    node = "node1"
    cmd = 'mkdir -p /usr/backups/{} /usr/backups/{}'.format(USER, USER_ID)
    cluster.ssh_exec(node, cmd)
    # exception means real error, because flag -p suppress AlreadyExists error

    # copy archives to node
    sftp = cluster.get_sftp(node)
    path = '/usr/backups'
    sftp.put('tests_integration/assets/pod_backups/disk_to_restore.tar.gz',
             '{}/{}/disk_to_restore.tar.gz'.format(path, USER_ID))
    sftp.put('tests_integration/assets/pod_backups/disk_to_restore.zip',
             '{}/{}/disk_to_restore.zip'.format(path, USER))

    # launch nginx container on node if it's not launched yet
    http_share(cluster, node, path)
