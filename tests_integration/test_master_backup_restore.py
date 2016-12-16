import os
import pipes
from collections import defaultdict

from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.utils import hooks, POD_STATUSES
from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.pod import Port

BACKUP_FOLDER = "/root/backups"
DEFAULT_SETTING_VALUE = "10"
SETTING_NAME = "persitent_disk_max_size"
test_users = [
    ("test_user_a", "test_user_a@cloudlinux.com"),
    ("test_user_b", "test_user_b@cloudlinux.com")]


def _setup_restore_test(cluster):
    _cleanup_master(cluster)


@pipeline("master_backup_restore")
@hooks(setup=_setup_restore_test)
def test_master_backup_restore(cluster):
    # Backup master after it was cleared from pods, PAs, node etc.
    empty_backup = _master_backup(cluster, BACKUP_FOLDER)
    empty_master_state = _MasterState(cluster)

    pods = _fill_master_with_data_to_backup(cluster)

    # Backup master after it was filled by pods, PAs etc.
    non_empty_master_backup = _master_backup(cluster, BACKUP_FOLDER)
    non_empty_master_state = _MasterState(cluster)

    # Restore "empty" master
    _master_restore(cluster, empty_backup)

    # Check that restore was successful, i.e. data (such as nodes, pods, users,
    # ips ...) was removed from master
    empty_master_state.compare(_MasterState(cluster))

    # Restore master with data
    _master_restore(cluster, non_empty_master_backup)

    # Check that restore was successful
    non_empty_master_state.compare(_MasterState(cluster))
    for pod in pods:
        pod.healthcheck()
    cluster.pods.create("nginx", "test_nginx_pod_3", open_all_ports=True,
                        start=True, wait_ports=True,
                        wait_for_status=POD_STATUSES.running,
                        ports=(Port(80, public=True), ))


def _cleanup_master(cluster):
    """
    Remove all pods, IP pools, PAs from master
    """
    cluster.ip_pools.clear()
    cluster.pods.clear()
    cluster.pvs.clear()
    cluster.pas.delete_all()
    cluster.set_system_setting(DEFAULT_SETTING_VALUE, name=SETTING_NAME)


def _fill_master_with_data_to_backup(cluster):
    predefined_applications = [
        ("dokuwiki", "/tmp/kuberdock_predefined_apps/dokuwiki.yaml"),
        ("drupal", "/tmp/kuberdock_predefined_apps/drupal.yaml")
    ]
    for name, path in predefined_applications:
        cluster.pas.add(name, path)
    for username, email in test_users:
        password = username
        cluster.users.create(username, password, email)
    # Change "Persistent disk maximum size" (id = 6) to 15.
    cluster.set_system_setting(15, name=SETTING_NAME)

    cluster.recreate_routable_ip_pool()
    cluster.nodes.add("node1")
    cluster.preload_docker_image('nginx')
    return [cluster.pods.create("nginx", name, open_all_ports=True,
                                start=True, wait_ports=True,
                                wait_for_status=POD_STATUSES.running,
                                ports=(Port(80, public=True), ))
            for name in ("test_nginx_pod_1", "test_nginx_pod_2")]


class _MasterState(object):
    def __init__(self, cluster):
        self.predefined_applications = cluster.pas.get_all()
        self.users = set(cluster.users.get_kd_users())
        self.pods = set(
            pipes.quote(pod['name']) for pod in
            cluster.pods.filter_by_owner())
        self.control_setting_value = cluster.get_system_setting(
            name=SETTING_NAME)
        self.free_ips, self.used_ips, self.blocked_ips = \
            self._get_ip_allocation(cluster)

    def _get_ip_allocation(self, cluster):
        # TODO: when AC-3630 is fixed, refactor this method, using "kdctl
        # ippool list", "kdctl ippool get"
        _, data, _ = cluster.manage("list-ip-pools", out_as_dict=True)
        r = defaultdict(set)
        allocations = [network['allocation'] for network in data]
        for allocation in allocations:
            for ip, _, status in allocation:
                r[status].add(ip)
        return r['free'], r['used'], r['blocked']

    def compare(self, other):
        checks = {
            'users': "List of users of restored cluster differs from list of"
                     " users existing before backing up.",
            'pods': "List of pods of restored cluster differs from "
                    "list of pods existing before backing up.",
            'control_setting_value': "Setting of restored cluster differs from"
                                     " settings existing before backing up.",
            'free_ips': "List of free IPs of restored cluster differs "
                        "from list existing before backing up.",
            'used_ips': "List of user IPs of restored cluster differs "
                        "from list existing before backing up.",
            'blocked_ips': "List of blocked IPs of restored cluster "
                           "differs from list existing before backing up.",
            'predefined_applications': "List of PAs of restored cluster "
                                       "differs from list of PAs existing "
                                       "before backing up."
        }
        errors = [
            err_msg for field, err_msg in checks.items()
            if getattr(self, field) != getattr(other, field)]
        if errors:
            raise MasterRestoredWithErrors("\n".join(errors))


def _master_backup(master, backup_folder):
    def _master_backup():
        master.ssh_exec("master", "kd-backup-master backup {}".
                        format(backup_folder))

    def _find_archives():
        sftp = master.get_sftp("master")
        all_files = sftp.listdir(backup_folder)
        return [f for f in all_files if os.path.splitext(f)[1] == ".zip"]

    def _find_new_archive():
        for f in current_archives:
            if f not in old_archives:
                # archive name is escaped because it contains colons (":")
                return pipes.quote(f)

    try:
        # Assume that there is no such folder on master yet
        master.ssh_exec("master", "mkdir {}".format(backup_folder))
        _master_backup()
        archive_name = _find_archives()[0]
    except NonZeroRetCodeException:
        # Folder for backups already exists (and may contain archives)
        old_archives = _find_archives()
        _master_backup()
        current_archives = _find_archives()
        archive_name = _find_new_archive()
    return "{}/{}".format(backup_folder, archive_name)


def _master_restore(master, archive_path):
    master.ssh_exec("master",
                    "kd-backup-master restore {}".format(archive_path))


class MasterRestoredWithErrors(Exception):
    pass
