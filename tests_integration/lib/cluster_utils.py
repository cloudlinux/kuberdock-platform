import re
from os import path
import logging
from time import sleep

from tests_integration.lib.exceptions import NonZeroRetCodeException


LOG = logging.getLogger(__name__)


def http_share(cluster, host, shared_dir=None):
    def _is_running():
        cmd = "curl -X GET http://{}".format("127.0.0.1:8080")
        try:
            cluster.ssh_exec(host, cmd)
            return True
        except NonZeroRetCodeException:
            return False

    if not _is_running():
        cmd = "docker run -d -p 8080:80 -v " \
              "{}:/usr/share/nginx/html/backups:ro nginx".format(shared_dir)
        cluster.ssh_exec(host, cmd)


def enable_beta_repos(cluster):
    all_hosts = ['master']
    all_hosts.extend(cluster.node_names)
    all_hosts.extend(cluster.rhost_names)
    for host in all_hosts:
        LOG.debug("Adding beta repos to {}".format(host))
        cmd = """cat > /etc/yum.repos.d/kube-cloudlinux-beta6.repo << EOF
[kube-beta6]
name=kube-beta-6
baseurl=http://repo.cloudlinux.com/kuberdock-beta/6/x86_64/
enabled=1
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF"""
        cluster.ssh_exec(host, cmd)
        cmd = """cat > /etc/yum.repos.d/kube-cloudlinux-beta7.repo << EOF
[kube-beta7]
name=kube-beta-7
baseurl=http://repo.cloudlinux.com/kuberdock-beta/7/x86_64/
enabled=1
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF"""
        cluster.ssh_exec(host, cmd)


def set_eviction_timeout(cluster, timeout):
    """
    Adds --pod-eviction-timeout setting to the KUBE_CONTROLLER_MANAGER_ARGS in
    /etc/kubernetes/controller-manager and restarts kube-controller-manager to
    apply the new settings.
    """
    sftp = cluster.get_sftp('master')
    tmp_filename = '/tmp/controller-manager-conf_tmp'
    conf_filename = '/etc/kubernetes/controller-manager'
    conf = sftp.open(conf_filename)
    tmp_file = sftp.open(tmp_filename, 'w')
    for line in conf:
        if re.match(r'^\s*KUBE_CONTROLLER_MANAGER_ARGS', line):
            line = re.sub(r'"(.*)"',
                          r'"\1 --pod-eviction-timeout={}"'.format(timeout),
                          line)
        tmp_file.write(line)
    conf.close()
    tmp_file.close()

    cluster.ssh_exec('master', 'sudo mv {0} {1}'.format(tmp_filename,
                                                        conf_filename))
    cluster.ssh_exec('master',
                     'sudo systemctl restart kube-controller-manager')


def set_kubelet_multipliers(cluster, cpu_mult=None, ram_mult=None):
    LOG.debug("Setting the new kubelet multipliers: CPU {}; RAM {}".format(
              cpu_mult, ram_mult))
    cluster.set_system_setting(cpu_mult, name="cpu_multiplier")
    cluster.set_system_setting(ram_mult, name="memory_multiplier")
    # wait until applied on the nodes
    sleep(5)
    # wait until nodes are active (kubelet restart)
    for n_name in cluster.node_names:
        cluster.nodes.get_node(n_name).wait_for_status("running")


def add_pa_from_url(cluster, url):
    LOG.debug("Adding the new PA to KD using template '{}'".format(url))
    cluster.ssh_exec("master", "curl --remote-name {}".format(url))
    name = path.basename(url)
    try:
        # Replace existing PA if any
        pa = cluster.pas.get_by_name(name)
        cluster.pas.delete(pa['id'])
        LOG.debug("add_pa_from_url deleted previously existing PA {}".format(
            name))
    except Exception:
        pass
    cluster.pas.add(name, name)
    return name
