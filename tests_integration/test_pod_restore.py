import json

from os.path import basename, normpath

from tests_integration.lib.cluster_utils import http_share
from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.pod import Port
from tests_integration.lib.utils import assert_in, assert_raises, assert_eq, \
    assert_not_eq, get_rnd_low_string, hooks

USER = "test_user"
USER_ID = 3


local_dir = 'tests_integration/assets/pod_backups/'
NGINX_WITHOUT_PV = {'local_path': local_dir + 'nginx_no_pv.json',
                    'master_path': '/tmp/nginx_no_pv.json'}
NGINX_WITH_DOMAIN = {'local_path': local_dir + 'nginx_with_domain.json',
                     'master_path': '/tmp/nginx_with_domain_pv.json'}
NGINX_WITH_PV = {'local_path': local_dir + 'nginx_with_pv.json',
                 'master_path': '/tmp/nginx_with_pv.json'}


def setup_non_pv_test(cluster):
    """:type cluster: KDIntegrationTestAPI"""
    _generate_restore_file_without_pv(cluster, domain=False)


def setup_domain_test(cluster):
    """:type cluster: KDIntegrationTestAPI"""
    cluster.domains.configure_cpanel_integration()
    _generate_restore_file_without_pv(cluster, domain=True)


def teardown_domain_test(cluster):
    """:type cluster: KDIntegrationTestAPI"""
    cluster.domains.stop_sharing_ip()


def setup_pv_test(cluster):
    """:type cluster: KDIntegrationTestAPI"""
    _prepare_server_for_backup_archive(cluster)
    _generate_restore_file_with_pv(cluster)


@pipeline('pod_restore')
@hooks(setup=setup_non_pv_test)
def test_restore_pod_from_cmd(cluster):
    """Test that pod can be restored from the cmd
    and that pod can't be restored if is't name is already in use.

    :type cluster: KDIntegrationTestAPI
    """
    # Test that pod can be restored from the cmd
    _, pod_dump, _ = cluster.ssh_exec("master",
                                      "cat {}".format(NGINX_WITHOUT_PV['master_path']))
    pod = cluster.pods.restore(USER, pod_dump=pod_dump)
    pod.wait_for_ports()
    pod.healthcheck()


@pipeline('pod_restore')
@pipeline('pod_restore_aws')
@hooks(setup=setup_non_pv_test)
def test_restore_from_file(cluster):
    """Test that pod without PVs can be restored from json-file.

    :type cluster: KDIntegrationTestAPI
    """
    _restore_from_file(cluster, domain=False)


@pipeline('pod_restore')
@pipeline('pod_restore_aws')
@hooks(setup=setup_domain_test, teardown=teardown_domain_test)
def test_restore_pod_with_domain_from_file(cluster):
    """Test that pod without PVs can be restored from json-file.

    :type cluster: KDIntegrationTestAPI
    """
    _restore_from_file(cluster, domain=True)


@pipeline('pod_restore')
@pipeline('pod_restore_aws')
@hooks(setup=setup_pv_test)
def test_pod_with_pv_restore(cluster):
    """Test that pod with PVs can be restored.

    :type cluster: KDIntegrationTestAPI
    """
    file_name = NGINX_WITH_PV['master_path']
    # To be sure that pv is restore from archive we need to use prepared
    # archive. In order to be used, this archive needs to be renamed nd
    # copied to web-server, which is already running on the node
    with open(NGINX_WITH_PV['local_path']) as f:
        dump = json.load(f)
        volume_name = dump['pod_data']['volumes'][0]['name']
        volume_folder = dump['volumes_map'][volume_name]
        disk_name = basename(normpath(volume_folder))
        path = '/tmp/backups'
        sftp = cluster.get_sftp("node1")
        sftp.put('tests_integration/assets/pod_backups/disk_to_restore.tar.gz',
                 '{}/{}/{}.tar.gz'.format(path, USER_ID, disk_name))
        sftp.put('tests_integration/assets/pod_backups/disk_to_restore.tar.gz',
                 '{}/{}/{}.tar.gz'.format(path, USER, disk_name))

    backup_url = "http://{}:8080/backups".format(cluster.get_hostname("node1"))
    path_template = "{owner_id}/{volume_name}.tar.gz"
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
    path_template = '{owner_name}/{volume_name}.tar.gz'
    pod2 = cluster.pods.restore(USER, file_path=file_name,
                                pv_backups_location=backup_url,
                                pv_backups_path_template=path_template,
                                flags="--force-delete",
                                return_as_json=True)
    # If pod was restored than it's id should distinguish from id of pod
    # with same name, that has just been removed
    assert_not_eq(old_id, pod2.pod_id)
    pod2.wait_for_ports()
    assert_in("This page has been restored from tar.gz",
              pod2.do_GET(path='/restored_location/'))


def _generate_restore_file_with_pv(cluster):
    """:type cluster: KDIntegrationTestAPI"""

    f = NGINX_WITH_PV
    if not _exists_on_master(cluster, f['master_path']):
        pod_with_pv, pv = _create_nginx_pod_with_pv(cluster)
        pod_dump = pod_with_pv.get_dump()
        with open(f['local_path'], "w") as fl:
            json.dump(pod_dump, fl)
        _copy_backup_to_master(cluster, f)
        pod_with_pv.delete()
        pv.delete()


def _generate_restore_file_without_pv(cluster, domain):
    """:type cluster: KDIntegrationTestAPI"""

    f = NGINX_WITH_DOMAIN if domain else NGINX_WITHOUT_PV

    if not _exists_on_master(cluster, f['master_path']):
        pod_without_pv = _create_nginx_pod_without_pv(cluster)
        pod_dump = pod_without_pv.get_dump()
        with open(f['local_path'], "w") as fl:
            json.dump(pod_dump, fl)
        _copy_backup_to_master(cluster, f)
        pod_without_pv.delete()


def _exists_on_master(cluster, file_path):
    """:type cluster: KDIntegrationTestAPI"""
    cmd = "[ -f ~{} ]".format(file_path)
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
    pod = cluster.pods.create("nginx", pod_name, pvs=[pv], start=True,
                              wait_for_status='running',
                              ports=[Port(80, public=True)])
    return pod, pv


def _create_nginx_pod_without_pv(cluster):
    """:type cluster: KDIntegrationTestAPI"""
    pod_name = "nginx{}".format(get_rnd_low_string(length=5))
    pod = cluster.pods.create("nginx", pod_name, start=True,
                              wait_for_status='running',
                              ports=[Port(80, public=True)],
                              domain=cluster.domains.get_first_domain())
    return pod


def _copy_backup_to_master(cluster, f):
    """:type cluster: KDIntegrationTestAPI"""
    ssh = cluster.get_ssh("master")
    sftp = ssh.open_sftp()
    sftp.get_channel().settimeout(10)
    sftp.put(f['local_path'], f['master_path'])


def _prepare_server_for_backup_archive(cluster):
    """
    Create folders for backup archive on master.
    Start web server on master.
    :type cluster: KDIntegrationTestAPI
    """

    # create folders
    node = "node1"
    cmd = 'mkdir -p /tmp/backups/{} /tmp/backups/{}'.format(USER, USER_ID)
    cluster.ssh_exec(node, cmd)
    # exception means real error, because flag -p suppress AlreadyExists error

    # copy archives to node
    path = '/tmp/backups'

    # launch nginx container on node if it's not launched yet
    http_share(cluster, node, path)


def _restore_from_file(cluster, domain):
    """Restore pod without PVs from json-file.

    :type cluster: KDIntegrationTestAPI
    """
    pod = cluster.pods.restore(
        USER,
        file_path=NGINX_WITH_DOMAIN['master_path'] if domain else
                  NGINX_WITHOUT_PV['master_path'],
        wait_for_status='running')
    pod.wait_for_ports()
    pod.healthcheck()
    cluster.assert_pods_number(1)
