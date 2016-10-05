import json
import logging
import os
import pipes
import subprocess
import sys
import time
import urllib2
import itertools

from collections import namedtuple
from contextlib import contextmanager
from datetime import datetime

import paramiko
import vagrant
import redis
import memcache
from ipaddress import IPv4Network

from exceptions import ServicePodsNotReady, NodeWasNotRemoved, \
    VmCreationError, VmProvisionError
from tests_integration.lib.exceptions import StatusWaitException, \
    UnexpectedKubectlResponse, DiskNotFound, PodIsNotRunning, \
    IncorrectPodDescription, CannotRestorePodWithMoreThanOneContainer
from tests_integration.lib.integration_test_utils import \
    ssh_exec, assert_eq, assert_in, kube_type_to_int, wait_net_port, \
    merge_dicts, retry, kube_type_to_str, escape_command_arg, log_dict, \
    get_rnd_low_string

OPENNEBULA = "opennebula"
VIRTUALBOX = "virtualbox"
PROVIDER = OPENNEBULA
DEFAULT_WAIT_POD_TIMEOUT = 10 * 60

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger("paramiko").setLevel(logging.WARNING)
LOG = logging.getLogger(__name__)


class KDIntegrationTestAPI(object):
    vm_names = {
        "master": "kd_master",
        "node1": "kd_node1",
        "node2": "kd_node2",
        "rhost1": "kd_rhost1",
    }

    def __init__(self, override_envs=None, out_cm=None, err_cm=None):
        """
        API client for interaction with kuberdock cluster

        :param override_envs: a dictionary of environment variables values
        to override. Useful when your integration test requires another
        cluster setup
        """
        defaults = {
            "VAGRANT_CWD": "dev-utils/dev-env/",
            "KD_LICENSE": "patch",
            "VAGRANT_NO_PARALLEL": "1"
        }

        env_vars = [
            "DOCKER_TLS_VERIFY",
            "DOCKER_HOST",
            "DOCKER_CERT_PATH",
            "DOCKER_MACHINE_NAME",
            "HOME",
            "PATH",
            "SSH_AUTH_SOCK",
            "VAGRANT_DOTFILE_PATH",
            "KD_ONE_PRIVATE_KEY",
            "KD_ONE_USERNAME",
            "KD_ONE_PASSWORD",
            "KD_ONE_PUB_IPS",
            "KD_INSTALL_TYPE",
            "KD_CEPH",
            "KD_CEPH_USER",
            "KD_CEPH_CONFIG",
            "KD_CEPH_USER_KEYRING",
            "KD_PD_NAMESPACE",
            "KD_FiXED_IP_POOLS",
            "KD_NEBULA_TEMPLATE_ID",
            "KD_NEBULA_RHOST_TEMPLATE_ID"
            "KD_NODE_TYPES",
        ]

        if override_envs is None:
            override_envs = {}

        kd_env = {e: os.environ.get(e) for e in env_vars if os.environ.get(e)}
        kd_env = merge_dicts(defaults, kd_env, override_envs)

        self.kuberdock_root = '/var/opt/kuberdock'
        self.vagrant = vagrant.Vagrant(quiet_stdout=False, quiet_stderr=False,
                                       env=kd_env, out_cm=out_cm,
                                       err_cm=err_cm)
        self.kd_env = kd_env
        self.ip_pools = IPPoolList(self)
        self.pods = PodList(self)
        self.pas = PAList(self)
        self.nodes = NodeList(self)
        self.pvs = PVList(self)
        self.users = UserList(self)
        self.created_at, self._ssh_connections = None, {}

    @staticmethod
    def _cut_vm_name_prefix(name):
        return name.replace('kd_', '')

    @property
    def node_names(self):
        names = (n.name for n in self.vagrant.status() if '_node' in n.name)
        return [self._cut_vm_name_prefix(n) for n in names]

    def get_host_ip(self, hostname):
        return self.vagrant.hostname('kd_{}'.format(hostname))

    def get_ssh(self, host):
        host = self.vm_names[host]
        if host in self._ssh_connections:
            return self._ssh_connections[host]

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if PROVIDER == OPENNEBULA:
            def_key = "".join([os.environ.get("HOME"), "/.ssh/id_rsa"])
            key_file = os.environ.get("KD_ONE_PRIVATE_KEY", def_key)
        else:
            # NOTE: this won't give proper results inside docker, another
            # reason why docker+vbox is not supported
            key_file = self.vagrant.conf()["IdentityFile"]

        ssh.connect(self.vagrant.hostname(host),
                    port=int(self.vagrant.port(host)),
                    username="root",
                    key_filename=key_file)

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
        self.ip_pools.add(ip_pool, includes=self.kd_env['KD_ONE_PUB_IPS'])

    def start(self, provider=PROVIDER):
        if self._any_vm_is_running():
            raise VagrantIsAlreadyUpException(
                "Vagrant is already up. Either perform \"vagrant destroy\" "
                "if you want to run tests on new cluster, or make sure you do "
                "not pass BUILD_CLUSTER env variable if you want run tests on "
                "the existing one.")

        log_dict(self.kd_env, "Cluster settings:", hidden=('KD_ONE_PASSWORD',))

        if provider == OPENNEBULA:
            try:
                retry(self.vagrant.up, tries=3, interval=15,
                      provider=provider, no_provision=True)
                self.created_at = datetime.utcnow()
            except subprocess.CalledProcessError:
                raise VmCreationError('Failed to create VMs')

            try:
                self.vagrant.provision()
            except subprocess.CalledProcessError:
                raise VmProvisionError('Failed to provision VMs')
        else:
            try:
                self.vagrant.up(provider=provider, no_provision=True)
                self.created_at = datetime.utcnow()
            except subprocess.CalledProcessError:
                raise VmCreationError(
                    'Failed either to create or provision VMs')

    def upgrade(self, upgrade_to='latest', use_testing=False,
                skip_healthcheck=False):
        args = ''
        if use_testing:
            args += ' -t'
        if upgrade_to != 'latest':
            args += " --local {0}".format(upgrade_to)
        if skip_healthcheck:
            args += ' --skip-health-check'
        self.ssh_exec(
            "master", "yes | /usr/bin/kuberdock-upgrade {}".format(args))

    def destroy(self):
        self.vagrant.destroy()

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

    def power_off(self, host):
        vm_name = self.vm_names[host]
        LOG.debug("VM Power Off: '{}'".format(vm_name))
        self.vagrant.halt(vm_name=vm_name)

    def power_on(self, host):
        vm_name = self.vm_names[host]
        LOG.debug("VM Power On: '{}'".format(vm_name))
        retry(self.vagrant.up, tries=3, vm_name=vm_name)

    def get_host_status(self, host):
        _, out, _ = self.kdctl("nodes list", out_as_dict=True)
        return next(s['status']
                    for s in out['data']
                    if s['hostname'] == host)

    def assert_pods_number(self, number):
        assert_eq(len(self.pods.filter_by_owner()), number)

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
        for node in nodes:
            retry(self.docker, interval=5, tries=3,
                  cmd='pull {}'.format(image), node=node)

    def wait_for_service_pods(self):
        def _check_service_pods():
            _, response, _ = self.kdctl(
                'pods list --owner kuberdock-internal', out_as_dict=True)
            statuses = (pod['status'] for pod in response['data'])
            if not all(s == 'running' for s in statuses):
                raise ServicePodsNotReady()

        retry(_check_service_pods, tries=40, interval=15)

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

    def _any_vm_is_running(self):
        return any(vm.state != "not_created" for vm in self.vagrant.status())

    def _kcli_config_path(self, user):
        if user is not None:
            return '/etc/kubecli_{}.conf'.format(user)


class RESTMixin(object):
    # Expectations:
    # self.public_ip

    def do_GET(self, scheme="http", path='/'):
        url = '{0}://{1}{2}'.format(scheme, self.public_ip, path)
        LOG.debug("Issuing GET to {0}".format(url))
        req = urllib2.urlopen(url)
        res = unicode(req.read(), 'utf-8')
        LOG.debug(u"Response:\n{0}".format(res))
        return res

    def do_POST(self, path='/', headers=None, body=""):
        pass


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
        self.cluster.manage(cmd)

    def delete(self, pool):
        self.cluster.manage('delete-ip-pool -s {}'.format(pool['network']))

    def clear(self):
        for p in self:
            self.delete(p)
        self.cluster.pods.forget_all()

    def __iter__(self):
        _, pools, _ = self.cluster.manage('list-ip-pools', out_as_dict=True)
        for p in pools:
            yield p


class PodList(object):
    def __init__(self, cluster):
        # type: (KDIntegrationTestAPI) -> None
        self.cluster = cluster

    def create(self, image, name, kube_type="Standard", kubes=1,
               open_all_ports=False, restart_policy="Always", pvs=None,
               start=True, wait_ports=False, healthcheck=False,
               wait_for_status=None, owner='test_user', password=None):
        assert_in(kube_type, ("Tiny", "Standard", "High memory"))
        assert_in(restart_policy, ("Always", "Never", "OnFailure"))

        pod = KDPod.create(self.cluster, image, name, kube_type, kubes,
                           open_all_ports, restart_policy, pvs, owner,
                           password=(owner or password))
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
                  healthcheck=False, wait_for_status=None,
                  owner='test_user'):
        pod = KDPAPod.create(self.cluster, template_name, plan_id, owner)

        if wait_for_status:
            pod.wait_for_status(wait_for_status)
        if wait_ports:
            pod.wait_for_ports()
        if healthcheck:
            LOG.info("Waiting 15 sec. Needed to starting application correctly")
            time.sleep(15)
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


class KDPod(RESTMixin):
    # Image or PA name
    SRC = None
    Port = namedtuple('Port', 'port proto')

    def __init__(self, cluster, image, name, kube_type, kubes,
                 open_all_ports, restart_policy, pvs, owner):
        self.cluster = cluster
        self.name = name
        self.image = image
        self.kube_type = kube_type
        self.kubes = kubes
        self.restart_policy = restart_policy
        self.owner = owner
        self.pvs = pvs
        self.open_all_ports = open_all_ports

    @property
    def public_ip(self):
        spec = self.get_spec()
        return spec.get('public_ip')

    @property
    def ports(self):
        def _get_ports(containers):
            all_ports = itertools.chain(
                *[c['ports'] for c in containers])
            return [port['containerPort']
                    for port in all_ports if port.get('isPublic') is True]

        spec = self.get_spec()
        return _get_ports(spec['containers'])

    @classmethod
    def create(cls, cluster, image, name, kube_type, kubes,
               open_all_ports, restart_policy, pvs, owner, password):
        """
        Create new pod in kuberdock
        :param open_all_ports: if true, open all ports of image (does not mean
        these are Public IP ports, depends on a cluster setup)
        :return: object via which Kuberdock pod can be managed
        """

        def _get_image_ports(img):
            _, out, _ = cluster.kcli(
                'image_info {}'.format(img), out_as_dict=True, user=owner)

            return [
                cls.Port(int(port['number']), port['protocol'])
                for port in out['ports']]

        def _ports_to_dict(ports):
            """
            :return: list of dictionaries with ports, necessary for
            creation of general pod via kcli2
            """
            ports_list = []
            for port in ports:
                ports_list.append(dict(containerPort=port.port,
                                       hostPort=port.port,
                                       isPublic=open_all_ports,
                                       protocol=port.proto))
            return ports_list

        escaped_name = pipes.quote(name)
        kube_types = {
            "Tiny": 0,
            "Standard": 1,
            "High memory": 2
        }
        pod_spec = dict(kube_type=kube_types[kube_type],
                        restartPolicy=restart_policy,
                        name=escaped_name)
        container = dict(kubes=kubes, image=image,
                         name=get_rnd_low_string(length=11))
        ports = retry(_get_image_ports, img=image)
        container.update(ports=_ports_to_dict(ports))
        if pvs is not None:
            container.update(volumeMounts=[pv.volume_mount_dict for pv in pvs])
            pod_spec.update(volumes=[pv.volume_dict for pv in pvs])
        pod_spec.update(containers=[container])
        pod_spec = json.dumps(pod_spec, ensure_ascii=False)

        _, out, _ = cluster.kcli2(u"pods create '{}'".format(pod_spec),
                                  out_as_dict=True,
                                  user=owner,
                                  password=(password or owner))
        this_pod_class = cls._get_pod_class(image)
        return this_pod_class(cluster, image, name, kube_type, kubes,
                              open_all_ports, restart_policy, pvs, owner)

    @classmethod
    def restore(cls, cluster, user, file_path=None, pod_dump=None,
                pv_backups_location=None, pv_backups_path_template=None,
                flags=None, return_as_json=False):
        """
        Restore pod using "kdctl pods restore" command
        :return: instance of KDPod object.
        """

        def get_image(file_path=None, pod_dump=None):
            if pod_dump is None:
                _, pod_dump, _ = cluster.ssh_exec("master",
                                                  "cat {}".format(file_path))
            pod_dump = json.loads(pod_dump)
            container = pod_dump['pod_data']["containers"]
            if len(container) > 1:
                # In current implementation of KDPod class we cannot
                # manage consisting of more than on container, therefore
                # creation of such container is prohibited
                raise CannotRestorePodWithMoreThanOneContainer(
                    "Unfortunately currently we cannot restore pod with more "
                    "than one container. KDPod class should be overwritten to "
                    "allow correct managing such containers to nake this "
                    "operation possible."
                )
            return pipes.quote(container[0]["image"])

        owner = pipes.quote(user)
        if return_as_json:
            cmd = "-j "
        else:
            cmd = ""
        if file_path and pod_dump:
            raise IncorrectPodDescription(
                "Only file_path OR only pod_description should be "
                "privoded. Hoverwer provided both parameters."
            )
        elif file_path:
            image = get_image(file_path=file_path)
            cmd += u"pods restore -f {}" \
                .format(file_path)
        elif pod_dump:
            image = get_image(pod_dump=pod_dump)
            cmd += u"pods restore \'{}\'" \
                .format(pod_dump)
        else:
            raise IncorrectPodDescription(
                "Either file_path or pod_description should not be empty")

        if pv_backups_location is not None:
            cmd += " --pv-backups-location={}".format(pv_backups_location)

        if pv_backups_path_template is not None:
            cmd += " --pv-backups-path-template={}".format(
                pv_backups_path_template)

        if flags is not None:
            cmd += " {}".format(flags)
        cmd += " --owner {}".format(owner)
        _, pod_description, _ = cluster.kdctl(cmd, out_as_dict=True)
        data = pod_description['data']
        name = data['name']
        kube_type = kube_type_to_str(data['kube_type'])
        restart_policy = data['restartPolicy']
        this_pod_class = cls._get_pod_class(image)
        return this_pod_class(cluster, "", name, kube_type, "", True,
                              restart_policy, "", owner)

    @classmethod
    def _get_pod_class(cls, image):
        pod_classes = {c.SRC: c for c in cls.__subclasses__()}
        return pod_classes.get(image, cls)

    def command(self, command):
        data = dict(command=command)
        return self.cluster.kcli2(
            u"pods update --name {} '{}'".format(self.name, json.dumps(data)),
            user=self.owner,
            out_as_dict=True)

    def start(self):
        _, out, _ = self.command("start")
        try:
            self.public_ip = out['data']['public_ip']
        except KeyError:
            pass

    def stop(self):
        self.command("stop")

    def delete(self):
        self.cluster.kcli2(
            u"pods delete --name {}".format(self.escaped_name),
            user=self.owner)

    def redeploy(self):
        data = {
            'command': 'redeploy', 'commandOptions': {'wipeOut': True}
        }
        self.cluster.kcli2(
            u"pods update --name {} '{}'".format(
                self.escaped_name, json.dumps(data), user=self.owner))

    def wait_for_ports(self, ports=None, timeout=DEFAULT_WAIT_POD_TIMEOUT):
        ports = ports or self.ports
        self._wait_for_ports(ports, timeout)

    def _wait_for_ports(self, ports, timeout):
        # NOTE: we still don't know if this is in a routable network, so
        # open_all_ports does not exactly mean wait_for_ports pass.
        # But for sure it does not make sense to wait if no ports open.
        if not self.open_all_ports:
            raise Exception("Cannot wait for ports on a pod with no ports open"
                            "(must pass open_all_ports=True)")
        for p in ports:
            wait_net_port(self.public_ip, p, timeout)

    def wait_for_status(self, status, tries=50, interval=5, delay=0):
        """
        Wait till POD's status changes to the given one

        :param status: the desired status to wait for
        :param tries: number of tries to check the status for
        :param interval: delay between the tries in seconds
        :param delay: the initial delay before a first check
        :return:
        """
        time.sleep(delay)
        for _ in range(tries):
            if self.status == status:
                return
            time.sleep(interval)
        raise StatusWaitException()

    @property
    def info(self):
        try:
            _, out, _ = self.cluster.kubectl(
                u'get pod {}'.format(self.escaped_name), out_as_dict=True,
                user=self.owner)
            return out[0]
        except KeyError:
            raise UnexpectedKubectlResponse()

    @property
    def status(self):
        return self.info['status']

    @property
    def escaped_name(self):
        return pipes.quote(self.name)

    @property
    def ssh_credentials(self):
        return retry(self._get_creds, tries=10, interval=1)

    def _get_creds(self):
        direct_access = self.get_spec()['direct_access']
        links = [v.split('@') for v in direct_access['links'].values()]
        return {
            'password': direct_access['auth'],
            'users': [v[0] for v in links],
            'hosts': [v[1] for v in links]
        }

    def get_container_ip(self, container_id):
        """
        Returns internal IP of a given container within the current POD
        """
        _, out, _ = self.docker_exec(container_id, 'hostname --ip-address')
        return out

    def get_spec(self):
        _, out, _ = self.cluster.kubectl(
            u"describe pods {}".format(self.escaped_name), out_as_dict=True,
            user=self.owner)
        return out

    def get_dump(self):
        cmd = u"pods dump {pod_id}".format(pod_id=self.pod_id)
        _, out, _ = self.cluster.kdctl(cmd, out_as_dict=True)
        rv = out['data']
        return rv

    @property
    def pod_id(self):
        return self.get_spec()['id']

    def docker_exec(self, container_id, command, detached=False):
        if self.status != 'running':
            raise PodIsNotRunning()

        node_name = self.info['host']
        args = '-d' if detached else ''
        docker_cmd = u'exec {} {} bash -c {}'.format(
            args, container_id, pipes.quote(command))
        return self.cluster.docker(docker_cmd, node_name)

    def healthcheck(self):
        LOG.warning(
            "This is a generic KDPod class health check. Inherit KDPod and "
            "implement health check for {0} image.".format(self.image))
        self._generic_healthcheck()

    def _generic_healthcheck(self):
        spec = self.get_spec()
        assert_eq(spec['kube_type'], kube_type_to_int(self.kube_type))
        for container in spec['containers']:
            assert_eq(container['kubes'], self.kubes)
        assert_eq(spec['restartPolicy'], self.restart_policy)
        assert_eq(spec['status'], "running")
        return spec


class _NginxPod(KDPod):
    SRC = "nginx"

    def wait_for_ports(self, ports=None, timeout=DEFAULT_WAIT_POD_TIMEOUT):
        # Though nginx also has 443, it is not turned on in a clean image.
        ports = ports or [80]
        self._wait_for_ports(ports, timeout)

    def healthcheck(self):
        if not self.open_all_ports:
            raise Exception(
                "Cannot perform nginx healthcheck without public IP"
                "(must pass open_all_ports=True)")
        self._generic_healthcheck()
        assert_in("Welcome to nginx!", self.do_GET())


class KDPAPod(KDPod):
    def __init__(self, cluster, pod_name, plan_id, kube_type, restart_policy,
                 owner):
        self.cluster = cluster
        self.name = pod_name
        self.plan_id = plan_id
        self.owner = owner
        self.open_all_ports = True
        self.kube_type = kube_type
        self.restart_policy = restart_policy

    @classmethod
    def create(cls, cluster, template_name, plan_id, owner, rnd_str=None):

        pa_data = cluster.pas.get_by_name(template_name)
        pa_id = pa_data['id']
        data = json.dumps({'PD_RAND': rnd_str or 'test_data_random'})
        _, pod_description, _ = cluster.kcli2(
            "predefined-apps create-pod {} {} '{}'".format(
                pa_id, plan_id, data),
            out_as_dict=True)

        data = pod_description['data']
        pod_name = data['name']
        kube_type = kube_type_to_str(data['kube_type'])
        restart_policy = data['restartPolicy']
        this_pod_class = cls._get_pod_class(template_name)
        return this_pod_class(cluster, pod_name, plan_id, kube_type,
                              restart_policy, owner)

    def _generic_healthcheck(self):
        spec = self.get_spec()
        assert_eq(spec['kube_type'], kube_type_to_int(self.kube_type))
        assert_eq(spec['restartPolicy'], self.restart_policy)
        assert_eq(spec['status'], "running")
        return spec


class _RedisPaPod(KDPAPod):
    SRC = 'redis.yaml'

    def healthcheck(self):
        spec = self._generic_healthcheck()
        assert_eq(len(spec['containers']), 1)
        assert_eq(spec['containers'][0]['image'], 'redis:3')
        r = redis.StrictRedis(host=self.public_ip, port=6379, db=0)
        r.set('foo', 'bar')
        assert_eq(r.get('foo'), 'bar')


class _DokuwikiPaPod(KDPAPod):
    SRC = 'dokuwiki.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        assert_in("Welcome to your new DokuWiki",
                  self.do_GET(path='/doku.php?id=wiki:welcome'))


class _DrupalPaPod(KDPAPod):
    SRC = 'drupal.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        # Change assertion string after fix AC-4487
        page = self.do_GET(path='/core/install.php')
        assert_in("Drupal", page)


class _ElasticsearchPaPod(KDPAPod):
    SRC = 'elasticsearch.yaml'

    def wait_for_ports(self):
        "Elastic PA isn't listen public ip"
        pass

    def healthcheck(self):
        self._generic_healthcheck()


class _RedminePaPods(KDPAPod):
    SRC = 'redmine.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        assert_in("Redmine", self.do_GET())


class _JoomlaPaPod(KDPAPod):
    SRC = 'joomla.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/installation/index.php')
        assert_in(u"Joomla! - Open Source Content Management", page)


class _MemcachedPaPod(KDPAPod):
    SRC = 'memcached.yaml'

    def healthcheck(self):
        spec = self._generic_healthcheck()
        assert_eq(len(spec['containers']), 1)
        assert_eq(spec['containers'][0]['image'], 'memcached:1')
        mc = memcache.Client(['{host}:11211'.format(host=self.public_ip)],
                             debug=0)
        mc.set("foo", "bar")
        assert_eq(mc.get("foo"), "bar")


class _Gallery3PaPod(KDPAPod):
    SRC = 'gallery3.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/installer/')
        assert_in(u"Installing Gallery is easy.  "
                  "We just need a place to put your photos", page)


class _MagentoPaPod(KDPAPod):
    SRC = 'magento.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/index.php/install/')
        assert_in(u"Magento is a trademark of Magento Inc.", page)


class _MantisPaPod(KDPAPod):
    SRC = 'mantis.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/admin/install.php')
        assert_in(u"Administration - Installation - MantisBT", page)


class VagrantIsAlreadyUpException(Exception):
    pass


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
        """
        Create new PV in Kuberdock.

        Create Python object which models PV in Kuberdock
        and also create new PV in the Kuberdock.
        """
        self.size = size
        self.cluster.kcli(u"drives add --size {} {}".format(
            self.size, self.name), self.owner)

    def _create_dummy(self, size):
        """
        Create Python object, which models PV.

        Don't create PV in the Kuberdock. This object will be used
        for creation of new PV in Kuberdock together with pod.
        """
        self.size = size

    def _load_existing(self, size):
        """
        Find PV in Kuberdock.

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
