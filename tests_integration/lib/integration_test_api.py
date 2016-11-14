import json
import logging
import os
import pipes
import sys
import time
from contextlib import contextmanager

import paramiko
from ipaddress import IPv4Network

from exceptions import ServicePodsNotReady, NodeWasNotRemoved, \
    NonZeroRetCodeException, ClusterUpgradeError
from tests_integration.lib.exceptions import DiskNotFound
from tests_integration.lib.infra_providers import InfraProvider
from tests_integration.lib.pa import KDPAPod
from tests_integration.lib.pod import KDPod
from tests_integration.lib.timing import log_timing, log_timing_ctx
from tests_integration.lib.utils import \
    ssh_exec, assert_eq, assert_in, retry, \
    escape_command_arg, get_rnd_low_string

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger("paramiko").setLevel(logging.WARNING)
LOG = logging.getLogger(__name__)


class KDIntegrationTestAPI(object):
    def __init__(self, provider):
        # type: (InfraProvider) -> KDIntegrationTestAPI
        """
        API client for interaction with kuberdock cluster
        """

        self._provider = provider
        self.kuberdock_root = '/var/opt/kuberdock'
        self.ip_pools = IPPoolList(self)
        self.pods = PodList(self)
        self.pas = PAList(self)
        self.nodes = NodeList(self)
        self.pvs = PVList(self)
        self.users = UserList(self)
        self._ssh_connections = {}

    @property
    def env(self):
        return self._provider.env

    @property
    def created_at(self):
        return self._provider.created_at

    @property
    def node_names(self):
        return self._provider.node_names

    def get_host_ip(self, hostname):
        return self._provider.get_host_ip(hostname)

    def get_ssh(self, host):
        host = self._provider.vm_names[host]
        if host in self._ssh_connections:
            return self._ssh_connections[host]

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        with log_timing_ctx("ssh.connect({})".format(host)):
            ssh.connect(self._provider.get_hostname(host),
                        port=self._provider.get_host_ssh_port(host),
                        username=self._provider.ssh_user,
                        key_filename=self._provider.ssh_key)

        self._ssh_connections[host] = ssh
        return ssh

    def get_sftp(self, host, timeout=10):
        ssh = self.get_ssh(host)
        sftp = ssh.open_sftp()
        sftp.get_channel().settimeout(timeout)
        return sftp

    def recreate_routable_ip_pool(self):
        self.ip_pools.clear()
        # First we parse get the default interface:
        # 8.8.8.8 via 192.168.115.254 dev ens3  src 192.168.113.245
        #
        # Then we extract IP/Preffix from this:
        # 2: ens3: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast
        # link/ether 02:00:c0:a8:71:f5 brd ff:ff:ff:ff:ff:ff
        # inet 192.168.113.245/22 brd 192.168.115.255 scope global ens3

        cmd = """
        MAIN_INTERFACE=$(ip route get 8.8.8.8 | egrep 'dev\s+.+?\s+src' -o | awk '{print $2}');  # noqa
        ip addr show dev $MAIN_INTERFACE | awk 'NR==3 { print $2 }'
        """
        _, main_ip, _ = self.ssh_exec('master', cmd)

        ip_pool = str(IPv4Network(unicode(main_ip), strict=False))
        self.ip_pools.add(ip_pool, includes=self.env['KD_ONE_PUB_IPS'])

    @log_timing
    def upgrade(self, upgrade_to='latest', use_testing=False,
                skip_healthcheck=False):
        args = ''
        if use_testing:
            args += ' -t'
        if upgrade_to != 'latest':
            args += " --local {0}".format(upgrade_to)
        if skip_healthcheck:
            args += ' --skip-health-check'
        try:
            self.ssh_exec("master",
                          "yes | /usr/bin/kuberdock-upgrade {}".format(args))
        except NonZeroRetCodeException:
            # This is needed because NonZeroRetCode will carry whole upgrade
            # log in stdout, which is huge. We replace it with short message
            # while full log is still printed by ssh_exec logging
            raise ClusterUpgradeError('kuberdock-upgrade non-zero retcode')

    @contextmanager
    def temporary_stop_host(self, host):
        """
        Powers off the host for the duration of the with block.
        Makes sure that the host is back on even if the exception occurs.

        :param host:  Name of the host to be powered off.
        """
        self.power_off(host)
        try:
            yield
        finally:
            self.power_on(host)

    @log_timing
    def power_off(self, host):
        self._provider.power_off(host)

    @log_timing
    def power_on(self, host):
        self._provider.power_on(host)

    def get_host_status(self, host):
        _, out, _ = self.kdctl("nodes list", out_as_dict=True)
        return next(s['status']
                    for s in out['data']
                    if s['hostname'] == host)

    def assert_pods_number(self, number):
        assert_eq(len(self.pods.filter_by_owner()), number)

    @log_timing
    def preload_docker_image(self, image, node=None):
        """
        Pulls given docker image in advance either for a specified node or
        for all nodes in a cluster. Useful in cases when a node can be quite
        overloaded. Then the image pull can take quite a long time and when you
        create a test pod you can't be sure if the image pull takes too long
        or something bad happened during pod creation. In these situations
        use this function. With it you will be sure that image is in place.

        :param image: name in a docker format (nginx, nginx:latest, etc)
        :param node: a hostname. If not specified - replaced with all nodes in
        cluster
        """

        nodes = node if node is not None else self.node_names
        # TODO parallel execution on all nodes
        for node in nodes:
            retry(self.docker, interval=5, tries=3,
                  cmd='pull {}'.format(image), node=node)

    @log_timing
    def wait_for_service_pods(self):
        def _check_service_pods():
            _, response, _ = self.kdctl(
                'pods list --owner kuberdock-internal', out_as_dict=True)
            statuses = (pod['status'] for pod in response['data'])
            if not all(s == 'running' for s in statuses):
                raise ServicePodsNotReady()

        retry(_check_service_pods, tries=40, interval=15)

    @log_timing
    def healthcheck(self):
        # Not passing for now: AC-3199
        rc, _, _ = self.ssh_exec("master",
                                 "kuberdock-upgrade health-check-only")
        assert_eq(rc, 0)

    def kcli(self, cmd, out_as_dict=False, user=None):
        kcli_cmd = ['kcli', '-k']

        if user is not None:
            config_path = self._kcli_config_path(user)
            kcli_cmd.extend(['-c', config_path])

        if out_as_dict:
            kcli_cmd.extend(['-j', 'kuberdock', cmd])
            rc, out, err = self.ssh_exec('master', ' '.join(kcli_cmd))
            return rc, json.loads(out), err

        kcli_cmd.extend(['kuberdock', cmd])
        return self.ssh_exec('master', ' '.join(kcli_cmd))

    # TODO: rid of the login in favour of "kcli2 -c /config/file"
    def kcli2(self, cmd, out_as_dict=False, user=None, password=None):
        if user:
            self.login_to_kcli2(user, password)
        kcli2_cmd = ['kcli2', '-k', cmd]
        rc, out, err = self.ssh_exec("master", u' '.join(kcli2_cmd))
        if out_as_dict:
            out = json.loads(out)

        return rc, out, err

    def login_to_kcli2(self, user, password=None):
        self.kcli2(u"login -u {} -p {}".format(user, password or user))

    # TODO: Kubectl will be moved out of KCLI so this code duplication won't
    #  hurt that much
    def kubectl(self, cmd, out_as_dict=False, user=None):
        kcli_cmd = ['kcli', '-k']

        if user is not None:
            config_path = self._kcli_config_path(user)
            kcli_cmd.extend(['-c', config_path])

        if out_as_dict:
            kcli_cmd.extend(['-j', 'kubectl', cmd])
            rc, out, err = self.ssh_exec('master', ' '.join(kcli_cmd))
            return rc, json.loads(out), err

        kcli_cmd.extend(['kubectl', cmd])
        return self.ssh_exec('master', ' '.join(kcli_cmd))

    def kdctl(self, cmd, out_as_dict=False):
        rc, out, err = self.ssh_exec("master", u"kdctl -k {}".format(cmd))
        if out_as_dict:
            out = json.loads(out)
        return rc, out, err

    def manage(self, args, out_as_dict=False, check_retcode=True):
        manage_cmd_path = os.path.join(self.kuberdock_root, 'manage.py')
        cmd = u"/usr/bin/env python {} {}".format(manage_cmd_path, args)
        rc, out, err = self.ssh_exec("master", cmd, check_retcode)
        if out_as_dict:
            return rc, json.loads(out), err
        return rc, out, err

    def docker(self, cmd, node="node1"):
        return self.ssh_exec(node, u"docker {}".format(cmd))

    def ssh_exec(self, node, cmd, check_retcode=True):
        ssh = self.get_ssh(node)
        # Forcibly source profile, so all additional ENV variables are exported
        cmd = '. /etc/profile; ' + cmd
        return ssh_exec(ssh, cmd, check_retcode=check_retcode)

    # TODO move to cluster.settings
    def set_system_setting(self, value, setting_id=None, name=None):
        cmd = "system-settings update "
        if setting_id:
            cmd += "--id {}".format(setting_id)
        if name:
            cmd += u"--name {}".format(name)
        self.kdctl(u"{} {}".format(cmd, value))

    def get_system_setting(self, setting_id=None, name=None):
        cmd = "system-settings get "
        if setting_id:
            cmd += "--id {}".format(setting_id)
        if name:
            cmd += u"--name {}".format(name)
        _, data, _ = self.kdctl(cmd, out_as_dict=True)
        return data['data']['value']

    def _kcli_config_path(self, user):
        if user is not None:
            return '/etc/kubecli_{}.conf'.format(user)


class UserList(object):
    def __init__(self, cluster):
        self.cluster = cluster

    def get_kd_users(self):
        _, out, _ = self.cluster.kdctl('users list', out_as_dict=True)
        sys_users = ['kuberdock-internal', 'admin']
        user_names = (u['username'] for u in out['data'])
        return (u for u in user_names if u not in sys_users)

    def create(self, name, password, email, role="User", active="True",
               package="Standard package"):
        name = escape_command_arg(name)
        password = escape_command_arg(password)
        email = escape_command_arg(email)
        user = {
            'active': active,
            'email': email,
            'package': package,
            'rolename': role,
            'username': name,
            'password': password
        }
        data = json.dumps(user, ensure_ascii=False)
        self.cluster.kdctl(u"users create '{}'".format(data))

    def delete(self, name):
        self.cluster.kdctl(
            "users delete --id {}".format(escape_command_arg(name)))


class PVList(object):
    def __init__(self, cluster):
        self.cluster = cluster

    def add(self, kind, name, mount_path='/some_mnt_pth', size=1):
        return PV(self.cluster, kind, name, mount_path, size)

    def clear(self):
        for user in self.cluster.users.get_kd_users():
            for pv in self.filter(user):
                name = escape_command_arg(pv['name'])
                self.cluster.kcli(u'drives delete {0}'.format(name), user=user)

    def filter(self, owner=None):
        _, pvs, _ = self.cluster.kcli("drives list", out_as_dict=True,
                                      user=owner)
        return pvs


class NodeList(object):
    def __init__(self, cluster):
        # type: (KDIntegrationTestAPI) -> None
        self.cluster = cluster

    def delete(self, node_name, timeout=60):
        self.cluster.manage("delete-node --hostname {}".format(node_name))
        end = time.time() + timeout
        while time.time() < end:
            if not self.node_exists(node_name):
                return
        raise NodeWasNotRemoved("Node {} failed to be removed in past {} "
                                "seconds".format(node_name, timeout))

    def add(self, node_name, kube_type="Standard"):
        docker_options = \
            '--insecure-registry=192.168.115.165:5001' \
            '--registry-mirror=http://192.168.115.165:5001' \
            '' \
            ''

        add_cmd = 'add-node --hostname {} --kube-type {} --do-deploy -t ' \
                  '--docker-options="{}"'.format(node_name, kube_type,
                                                 docker_options)

        self.cluster.manage(add_cmd)
        self.cluster.manage("wait-for-nodes --nodes {}".format(node_name))

    def node_exists(self, hostname):
        _, out, _ = self.cluster.kdctl("nodes list", out_as_dict=True)
        data = out['data']
        for node in data:
            if node['hostname'] == hostname:
                return True
        return False

    def get_node_info(self, name):
        # type: (str) -> dict
        _, out, _ = self.cluster.manage(
            u'node-info -n {}'.format(pipes.quote(name)), out_as_dict=True)
        return out


class PAList(object):
    def __init__(self, cluster):
        # type: (KDIntegrationTestAPI) -> None
        self.cluster = cluster

    def add(self, name, file_path, validate=False, origin=None):
        """
        Add predefined application from yaml-file into list of predefined
        applications
        :param file_path: path to the yaml-file on the master (not on the
        host!)
        """
        name = escape_command_arg(name)
        file_path = escape_command_arg(file_path)
        cmd = "predefined-apps create --name {} -f {}".format(name, file_path)
        if validate:
            cmd += " --validate"
        if origin:
            cmd += " --origin '{}'".format(origin)
        self.cluster.kdctl(cmd)

    def get_all(self):
        _, out, _ = self.cluster.kdctl("predefined-apps list",
                                       out_as_dict=True)
        data = out['data']
        return [pa for pa in data]

    def get_by_name(self, name):
            return next(
                (pa for pa in self.get_all() if pa['name'] == name),
                None)

    def delete(self, id_):
        self.cluster.kdctl("predefined-apps delete --id {}".format(id_))

    def delete_all(self):
        for pa in self.get_all():
            self.delete(pa['id'])


class IPPoolList(object):
    def __init__(self, cluster):
        # type: (KDIntegrationTestAPI) -> None
        self.cluster = cluster

    def add(self, subnet, hostname=None, excludes='', includes=''):
        cmd = 'create-ip-pool -s {}'.format(subnet)
        if hostname is not None:
            cmd += ' --node {}'.format(hostname)
        cmd += ' -e "{}"'.format(excludes)
        cmd += ' -i "{}"'.format(includes)
        return self.cluster.manage(cmd)

    def delete(self, pool):
        return self.cluster.manage(
            'delete-ip-pool -s {}'.format(pool['network']))

    def clear(self):
        for p in self:
            self.delete(p)
        self.cluster.pods.forget_all()

    def get(self, network):
        for p in self:
            if p['network'] == network:
                return p

    def __iter__(self):
        _, pools, _ = self.cluster.manage('list-ip-pools', out_as_dict=True)
        for p in pools:
            yield p


class PodList(object):
    def __init__(self, cluster):
        # type: (KDIntegrationTestAPI) -> None
        self.cluster = cluster

    def create(self, image, name, kube_type="Standard", kubes=1,
               open_all_ports=False, ports_to_open=(),
               restart_policy="Always", pvs=None, start=True, wait_ports=False,
               healthcheck=False, wait_for_status=None, owner='test_user',
               password=None):
        """
        Create new pod in kuberdock
        :param open_all_ports: if true, open all ports of image (does not mean
        these are Public IP ports, depends on a cluster setup)
        :param ports_to_open: if open_all_ports is False, open only the ports
        from this list
        :return: object via which Kuberdock pod can be managed
        """
        assert_in(kube_type, ("Tiny", "Standard", "High memory"))
        assert_in(restart_policy, ("Always", "Never", "OnFailure"))

        pod = KDPod.create(self.cluster, image, name, kube_type, kubes,
                           open_all_ports, restart_policy, pvs, owner,
                           owner or password, ports_to_open)
        if start:
            pod.start()
        if wait_for_status:
            pod.wait_for_status(wait_for_status)
        if wait_ports:
            pod.wait_for_ports()
        if healthcheck:
            pod.healthcheck()
        return pod

    def create_pa(self, template_name, plan_id=1, wait_ports=False,
                  healthcheck=False, wait_for_status=None, owner='test_user',
                  command="kcli2", rnd_str='test_data_'):
        """Create new pod with predefined application in the Kuberdock.

        :param rnd_str: string which will be applied to the name of
            persistent volumes, which will be created with the pod
        :return: object via which Kuberdock pod can be managed

        """
        pod = KDPAPod.create(
            self.cluster, template_name, plan_id, owner, command,
            rnd_str=get_rnd_low_string(prefix=rnd_str, length=5))

        if wait_for_status:
            pod.wait_for_status(wait_for_status)
        if wait_ports:
            pod.wait_for_ports()
        if healthcheck:
            pod.healthcheck()

        return pod

    def restore(self, user, file_path=None, pod_dump=None,
                pv_backups_location=None, pv_backups_path_template=None,
                flags=None, return_as_json=False, wait_for_status=None):

        pod = KDPod.restore(self.cluster, user, file_path, pod_dump,
                            pv_backups_location, pv_backups_path_template,
                            flags, return_as_json)
        if wait_for_status:
            pod.wait_for_status(wait_for_status)
        return pod

    def forget_all(self):
        for user in self.cluster.users.get_kd_users():
            _, pods, _ = self.cluster.kcli('list', out_as_dict=True, user=user)

            for pod in pods:
                name = escape_command_arg(pod['name'])
                self.cluster.kcli(u'forget {}'.format(name), user=user)

    def filter_by_owner(self, owner='test_user'):
        # type: (str) -> dict
        _, pods, _ = self.cluster.kubectl(
            "get pods", out_as_dict=True, user=owner)
        return pods

    def clear(self):
        for user in self.cluster.users.get_kd_users():
            for pod in self.cluster.pods.filter_by_owner(user):
                name = escape_command_arg(pod['name'])
                self.cluster.kcli(u'delete {}'.format(name), user=user)


class PV(object):
    def __init__(self, cluster, kind, name, mount_path, size, owner=None):
        self.cluster = cluster
        self.name = name
        self.owner = owner
        self.mount_path = mount_path
        self.volume_name = get_rnd_low_string(length=11)
        inits = {
            "new": self._create_new,
            "existing": self._load_existing,
            "dummy": self._create_dummy
        }
        try:
            inits[kind](size)
        except KeyError:
            raise AssertionError("Integration test API PV type not in {}"
                                 .format(inits.keys()))

    def _create_new(self, size):
        """Create new PV in Kuberdock.

        Create Python object which models PV in Kuberdock
        and also create new PV in the Kuberdock.

        """
        self.size = size
        self.cluster.kcli(u"drives add --size {} {}".format(
            self.size, self.name), self.owner)

    def _create_dummy(self, size):
        """Create Python object, which models PV.

        Don't create PV in the Kuberdock. This object will be used
        for creation of new PV in Kuberdock together with pod.

        """
        self.size = size

    def _load_existing(self, size):
        """Find PV in Kuberdock.

        Create Python obejct which models PV and link it to PV which
        already exist in Kuberdock.

        """
        # TODO: Currently this method is never used. May be it will be
        # TODO: in use, when we start testing PAs. If it will not
        # TODO: it can be removed together with exception
        pv = self._get_by_name(self.name)
        if not pv:
            raise DiskNotFound(u"Disk {0} doesn't exist".format(self.name))
        self.size = pv['size']

    def _get_by_name(self, name):
        _, pvs, _ = self.cluster.kcli(
            'drives list', out_as_dict=True, user=self.owner)
        for pv in pvs:
            if pv['name'] == name:
                return pv

    def delete(self):
        self.cluster.kcli(
            "drives delete {0}".format(self.name), user=self.owner)

    def exists(self):
        return self._get_by_name(self.name) is not None

    @property
    def volume_dict(self):
        """
        :return: dictionary contain description of volume, necessary for
            creation of general pod via kcli2

        """
        persistent_disk = dict(pdName=self.name, pdSize=self.size)
        return dict(name=self.volume_name, persistentDisk=persistent_disk)

    @property
    def volume_mount_dict(self):
        """
        :return: dictionary contain description of volume mount, necessary for
            creation of general pod via kcli2

        """
        return dict(mountPath=self.mount_path, name=self.volume_name)
