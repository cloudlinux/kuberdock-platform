import json
import logging
import os
import pipes
import sys
import time
import urllib2
from datetime import datetime

import paramiko
import vagrant
import yaml

from tests_integration.lib.exceptions import StatusWaitException, \
    UnexpectedKubectlResponse, DiskNotFoundException, PodIsNotRunning
from tests_integration.lib.integration_test_utils import \
    ssh_exec, assert_eq, assert_in, kube_type_to_int, wait_net_port, \
    merge_dicts, retry

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

    def __init__(self, override_envs=None,
                 version='latest',
                 upgrade_to='latest', out_cm=None, err_cm=None):
        """
        API client for interaction with kuberdock cluster

        :param override_envs: a dictionary of environment variables values
        to override. Useful when your integration test requires another
        cluster setup
        :param version:
        :param upgrade_to:
        """
        defaults = {"VAGRANT_CWD": "dev-utils/dev-env/", "KD_LICENSE": "patch"}

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
            "KD_NONFLOATING_PUBLIC_IPS",
            "KD_NEBULA_TEMPLATE_ID",
            "KD_NODE_TYPES",
        ]

        if override_envs is None:
            override_envs = {}

        kd_env = {e: os.environ.get(e) for e in env_vars if os.environ.get(e)}
        kd_env = merge_dicts(defaults, kd_env, override_envs)

        if kd_env.get('KD_INSTALL_TYPE') == 'dev':
            self.kuberdock_root = '/vagrant'
        else:
            self.kuberdock_root = '/var/opt/kuberdock'

        self.vagrant = vagrant.Vagrant(quiet_stdout=False, quiet_stderr=False,
                                       env=kd_env, out_cm=out_cm,
                                       err_cm=err_cm)
        self.kd_env = kd_env
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

    def recreate_routable_ip_pool(self):
        self.delete_all_ip_pools()
        # First we parse get the default interface:
        # 8.8.8.8 via 192.168.115.254 dev ens3  src 192.168.113.245
        #
        # Then we extract IP/Preffix from this:
        # 2: ens3: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast
        # link/ether 02:00:c0:a8:71:f5 brd ff:ff:ff:ff:ff:ff
        # inet 192.168.113.245/22 brd 192.168.115.255 scope global ens3

        cmd = """
        MAIN_INTERFACE=$(ip route get 8.8.8.8 | egrep 'dev\s+.+?\s+src' -o | awk '{print $2}');
        ip addr show dev $MAIN_INTERFACE | awk 'NR==3 { print $2 }'
        """
        _, main_ip, _ = self.ssh_exec('master', cmd)

        # TODO: AC-3928 Right now ansible can only use /24 network while we
        # have /22 Remove this as soon as ansible can deal with that
        # Cut the actual prefix length and replace it with /24
        ip_pool = str(main_ip.rsplit('.', 1)[0]) + '.0/24'
        requested_ip_octets = set(self.kd_env['KD_ONE_PUB_IPS'].split(','))
        all_ip_octets = set(str(i) for i in range(0, 256))

        excludes = ','.join(all_ip_octets - requested_ip_octets)
        self.add_ip_pool(ip_pool, excludes=excludes)

    def _build_cluster_flag(self, op_name):
        build_flag = "BUILD_CLUSTER"
        if os.environ.get(build_flag):
            LOG.info(
                "{0} flag passed. {1} call is executed.".format(build_flag,
                                                                op_name))
            return True
        LOG.info("{0} flag not passed. Reusing existing cluster "
                 "({1} call is skipped).".format(build_flag, op_name))
        return False

    def _any_vm_is_running(self):
        return any(vm.state != "not_created" for vm in self.vagrant.status())

    def get_node_info(self, name):
        _, out, _ = self.manage(
            'node-info -n {}'.format(pipes.quote(name)), out_as_dict=True)
        return out

    def start(self, provider=PROVIDER):
        if not self._build_cluster_flag("start"):
            return

        if self._any_vm_is_running():
            raise VagrantIsAlreadyUpException(
                "Vagrant is already up. Either perform \"vagrant destroy\" "
                "if you want to run tests on new cluster, or make sure you do "
                "not pass BUILD_CLUSTER env variable if you want run tests on "
                "the existing one.")

        if provider == OPENNEBULA:
            retry(self.vagrant.up, tries=3,
                  provider=provider, no_provision=True)
            self.created_at = datetime.utcnow()
            self.vagrant.provision()
        else:
            self.vagrant.up(provider=provider, no_provision=True)
            self.created_at = datetime.utcnow()

    def upgrade(self, upgrade_to='latest'):
        if not self._build_cluster_flag("upgrade"):
            return

        local_arg = ''
        if upgrade_to != 'latest':
            local_arg = "--local {0}".format(upgrade_to)
        self.ssh_exec("master", "kuberdock-upgrade {0}".format(local_arg))

    def destroy(self):
        if self._build_cluster_flag("destroy"):
            self.vagrant.destroy()

    def power_off(self, host):
        vm_name = self.vm_names[host]
        LOG.debug("VM Power Off: '{}'".format(vm_name))
        self.vagrant.halt(vm_name=vm_name)

    def power_on(self, host):
        vm_name = self.vm_names[host]
        LOG.debug("VM Power On: '{}'".format(vm_name))
        self.vagrant.up(vm_name=vm_name)

    def get_kd_users(self):
        _, out, _ = self.kdctl('users list', out_as_dict=True)
        sys_users = ['kuberdock-internal', 'admin']
        user_names = (u['username'] for u in out['data'])
        return (u for u in user_names if u not in sys_users)

    def delete_all_pods(self):
        for user in self.get_kd_users():
            for pod in self.get_all_pods(user):
                name = self._escape_command_arg(pod['name'])
                self.kcli('delete {}'.format(name), user=user)

    def forget_all_pods(self):
        for user in self.get_kd_users():
            _, pods, _ = self.kcli('list', out_as_dict=True, user=user)

            for pod in pods:
                name = self._escape_command_arg(pod['name'])
                self.kcli('forget {}'.format(name), user=user)

    def delete_all_ip_pools(self):
        _, pools, _ = self.manage('list-ip-pools', out_as_dict=True)
        for pool in pools:
            self.delete_ip_pool(pool)

        self.forget_all_pods()

    def get_all_pods(self, owner='test_user'):
        _, pods, _ = self.kubectl("get pods", out_as_dict=True, user=owner)
        return pods

    def assert_pods_number(self, number):
        assert_eq(len(self.get_all_pods()), number)

    def delete_ip_pool(self, pool):
        self.manage('delete-ip-pool -s {}'.format(pool['network']))

    def add_ip_pool(self, subnet, hostname=None, excludes=''):
        cmd = 'create-ip-pool -s {}'.format(subnet)
        if hostname is not None:
            cmd += ' --node {}'.format(hostname)
        cmd += ' -e "{}"'.format(excludes)
        self.manage(cmd)

    def create_pod(self, image, name, kube_type="Standard", kubes=1,
                   open_all_ports=False, restart_policy="Always", pvs=None,
                   start=True, wait_ports=False, healthcheck=False,
                   wait_for_status=None, owner='test_user'):
        assert_in(kube_type, ("Tiny", "Standard", "High memory"))
        assert_in(restart_policy, ("Always", "Never", "OnFailure"))

        pod = self._create_pod_object(image, kube_type, kubes, name,
                                      open_all_ports, restart_policy, pvs,
                                      owner)
        if start:
            pod.start()
        if wait_for_status:
            pod.wait_for_status(wait_for_status)
        if wait_ports:
            pod.wait_for_ports()
        if healthcheck:
            pod.healthcheck()
        return pod

    def _create_pod_object(self, image, kube_type, kubes, name, open_all_ports,
                           restart_policy, pvs, owner='test_user'):
        """
        Given an image name creates an instance of a corresponding pod class
        """
        pod_classes = {c.SRC: c for c in KDPod.__subclasses__()}

        this_pod_class = pod_classes.get(image, KDPod)
        return this_pod_class(self, image, name, kube_type, kubes,
                              open_all_ports, restart_policy, pvs, owner)

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
            self.docker('pull {}'.format(image), node)

    def create_pa(self, yml, size="M", start=True):
        pass

    def healthcheck(self):
        # Not passing for now: AC-3199
        rc, _, _ = self.ssh_exec("master",
                                 "kuberdock-upgrade health-check-only")
        assert_eq(rc, 0)

    def kcli(self, cmd, out_as_dict=False, user=None):
        kcli_cmd = ['kcli']

        if user is not None:
            config_path = self._kcli_config_path(user)
            kcli_cmd.extend(['-c', config_path])

        if out_as_dict:
            kcli_cmd.extend(['-j', 'kuberdock', cmd])
            rc, out, err = self.ssh_exec('master', ' '.join(kcli_cmd))
            return rc, json.loads(out), err

        kcli_cmd.extend(['kuberdock', cmd])
        return self.ssh_exec('master', ' '.join(kcli_cmd))

    # TODO: Kubectl will be moved out of KCLI so this code duplication won't
    #  hurt that much
    def kubectl(self, cmd, out_as_dict=False, user=None):
        kcli_cmd = ['kcli']

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
        rc, out, err = self.ssh_exec("master", "kdctl {}".format(cmd))
        if out_as_dict:
            out = json.loads(out)
        return rc, out, err

    def docker(self, cmd, node="node1"):
        return self.ssh_exec(node, "docker {0}".format(cmd))

    def manage(self, args, out_as_dict=False, check_retcode=True):
        manage_cmd_path = os.path.join(self.kuberdock_root, 'manage.py')
        cmd = "/usr/bin/env python {} {}".format(manage_cmd_path, args)
        rc, out, err = self.ssh_exec("master", cmd, check_retcode)
        if out_as_dict:
            return rc, json.loads(out), err
        return rc, out, err

    def ssh_exec(self, node, cmd, check_retcode=True):
        ssh = self.get_ssh(node)
        return ssh_exec(ssh, cmd, check_retcode=check_retcode)

    def _escape_command_arg(self, arg):
        return pipes.quote(arg)

    def _kcli_config_path(self, user):
        if user is not None:
            return '/etc/kubecli_{}.conf'.format(user)

    def create_pv(self, kind, name, mount_path='/some_mnt_pth', size=1):
        return PV(self, kind, name, mount_path, size)

    def delete_all_pvs(self):
        for user in self.get_kd_users():
            for pv in self.get_all_pvs(user):
                name = self._escape_command_arg(pv['name'])
                self.kcli('drives delete {0}'.format(name), user=user)

    def get_all_pvs(self, owner=None):
        _, pvs, _ = self.kcli("drives list", out_as_dict=True, user=owner)
        return pvs


class RESTMixin(object):
    # Expectations:
    # self.public_ip

    def do_GET(self, scheme="http", path='/'):
        url = '{0}://{1}{2}'.format(scheme, self.public_ip, path)
        LOG.debug("Issuing GET to {0}".format(url))
        res = urllib2.urlopen(url).read()
        LOG.debug("Response:\n{0}".format(res))
        return res

    def do_POST(self, path='/', headers=None, body=""):
        pass


class KDPod(RESTMixin):
    # Image or PA name
    SRC = None

    def __init__(self, cluster, image, name, kube_type, kubes,
                 open_all_ports, restart_policy, pvs, owner):
        self.cluster = cluster
        self.name = name
        self.image = image
        self.kube_type = kube_type
        self.kubes = kubes
        self.restart_policy = restart_policy
        self.public_ip = None
        self.owner = owner
        self.ports = self._get_ports(image)
        self.pv_cmd = ''
        if pvs is not None:
            # TODO: when kcli allows using multiple PVs for single POD
            # (AC-3722), update the way of pc_cmd creation
            self.pv_cmd = "-s {} -p {} --mount-path {}".format(
                pvs[0].size, pvs[0].name, pvs[0].mount_path)
        pv_cmd = self.pv_cmd
        escaped_name = self.escaped_name

        # Does not mean these are Public IP ports, depends on a cluster setup.
        self.open_all_ports = open_all_ports
        ports_arg = ''
        if open_all_ports:
            pub_ports = ",".join(["+{0}".format(p) for p in self.ports])
            ports_arg = "--container-port {0}".format(pub_ports)

        self.cluster.kcli(
            "create -C {image} --kube-type {kube_type} --kubes {kubes} "
            "--restart-policy {restart_policy} {ports_arg} {pv_cmd} "
            "{escaped_name}".format(
                **locals()), user=self.owner)
        self.cluster.kcli(
            "save {0}".format(self.escaped_name), user=self.owner)

    def _get_ports(self, image):
        _, out, _ = self.cluster.kcli(
            'image_info {}'.format(image), out_as_dict=True, user=self.owner)
        return [int(p['number']) for p in out['ports']]

    def start(self):
        rc, out, err = self.cluster.kcli("start {0}".format(self.escaped_name),
                                         user=self.owner)
        # TODO: Handle exclamation mark in a response correctly
        self.public_ip = yaml.load(out).get('public_ip')

    def stop(self):
        self.cluster.kcli(
            "stop {0}".format(self.escaped_name), user=self.owner)

    def delete(self):
        self.cluster.kcli(
            "delete {0}".format(self.escaped_name), user=self.owner)

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
                'get pod {}'.format(self.escaped_name), out_as_dict=True,
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

    def get_container_ip(self, container_id):
        """
        Returns internal IP of a given container within the current POD
        """
        _, out, _ = self.docker_exec(container_id, 'hostname --ip-address')
        return out

    def get_spec(self):
        _, out, _ = self.cluster.kubectl(
            "describe pods {}".format(self.escaped_name), out_as_dict=True,
            user=self.owner)
        return out

    def docker_exec(self, container_id, command):
        if self.status != 'running':
            raise PodIsNotRunning()

        node_name = self.info['host']
        docker_cmd = 'exec {} {}'.format(container_id, command)
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


class KDPredefinedApp(KDPod):
    pass


class VagrantIsAlreadyUpException(Exception):
    pass


class PV(object):
    def __init__(self, cluster, kind, name, mount_path, size, owner=None):
        self.cluster = cluster
        self.name = name
        self.owner = owner
        self.mount_path = mount_path
        inits = {"new": self._create_new,
                 "existing": self._load_existing,
                 "dummy": self._create_dummy}
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
        self.cluster.kcli("drives add --size {} {}".format(
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
            raise DiskNotFoundException("Disk {0} doesn't exist".
                                        format(self.name))
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
