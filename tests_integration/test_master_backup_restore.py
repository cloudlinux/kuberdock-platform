import os
import pipes

from collections import defaultdict
from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.integration_test_utils import hooks
from tests_integration.lib.pipelines import pipeline

BACKUP_FOLDER = "/root/backups"
DEFAULT_SETTING_VALUE = "10"
SETTING_ID = 6
test_users = [("test_user_a", "test_user_a@cloudlinux.com"),
              ("test_user_b", "test_user_b@cloudlinux.com")]


def _setup_restore_test(cluster):
    _clear_master(cluster)


# @pipeline("master_backup_restore") # fixme AC-4278
@hooks(setup=_setup_restore_test)
def test_master_backup_restore(cluster):
    # Backup master after it was cleared from pods, PAs, node etc.
    empty_backup = _master_backup(cluster, BACKUP_FOLDER)
    empty_master_state = _MasterState(cluster)

    _fill_master_with_data_to_backup(cluster)

    # Backup master after it was filled by pods, PAs etc.
    non_empty_master_backup = _master_backup(cluster, BACKUP_FOLDER)
    non_empty_master_state = _MasterState(cluster)

    # Restore "empty" master
    _master_restore(cluster, empty_backup)

    # Check that backup was successful, i.e. data (such as nodes, pods, users,
    # ips ...) was removed from master
    empty_master_state.compare(_MasterState(cluster))

    # Restore master with data
    _master_restore(cluster, non_empty_master_backup)

    # Check that backup was successful
    non_empty_master_state.compare(_MasterState(cluster))


def _clear_master(cluster):
    """
    Remove all pods, IP pools, PAs and node from master
    """
    cluster.delete_all_ip_pools()
    cluster.delete_all_pods()
    cluster.delete_all_pvs()
    cluster.delete_all_predefined_applications()
    cluster.delete_node("node1")
    cluster.set_system_setting(SETTING_ID, DEFAULT_SETTING_VALUE)


def _fill_master_with_data_to_backup(cluster):
    predefined_applications = [
        ("dokuwiki", "/tmp/kuberdock_predefined_apps/dokuwiki.yaml"),
        ("drupal", "/tmp/kuberdock_predefined_apps/drupal.yaml")
    ]
    for name, path in predefined_applications:
        cluster.add_predefined_application(name, path)
    for username, email in test_users:
        password = username
        cluster.create_user(username, password, email)
    # Change "Persistent disk maximum size" (id = 6) to 15.
    cluster.set_system_setting(SETTING_ID, 15)

    cluster.recreate_routable_ip_pool()
    cluster.add_node("node1")
    cluster.preload_docker_image('nginx')
    cluster.create_pod("nginx", "test_nginx_pod_1", open_all_ports=True,
                       start=True)
    cluster.create_pod("nginx", "test_nginx_pod_2", open_all_ports=True,
                       start=True)


class _MasterState(object):
    def __init__(self, cluster):
        self.predefined_applications = cluster.get_predefined_applications()
        self.users = set(cluster.get_kd_users())
        self.pods = set(pipes.quote(pod['name']) for pod in
                        cluster.get_all_pods())
        self.control_setting_value = cluster.get_system_setting(SETTING_ID)
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
            'control_setting_value': "Setting of restored cluster differs from "
                                     "settings existing before backing up.",
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
        errors = [err_msg for field, err_msg in checks.items() if
                  getattr(self, field) != getattr(other, field)]
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
