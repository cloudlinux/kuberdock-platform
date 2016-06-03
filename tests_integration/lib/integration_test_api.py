import json
import logging
import os
import sys
import time
import urllib2
import pipes

import paramiko
import vagrant
import yaml

from tests_integration.lib.integration_test_utils import \
    ssh_exec, wait_net_port, kube_type_to_int, assert_eq, assert_in

OPENNEBULA = "opennebula"
VIRTUALBOX = "virtualbox"
PROVIDER = OPENNEBULA
DEFAULT_WAIT_POD_TIMEOUT = 10 * 60

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger("paramiko").setLevel(logging.WARNING)
LOG = logging.getLogger(__name__)


class KDIntegrationTestAPI(object):
    def __init__(self, version='latest', upgrade_to='latest'):
        # TODO: handle args
        kd_env = {
            "VAGRANT_CWD": "dev-utils/dev-env/",
            "HOME": os.environ.get("HOME"),
            "PATH": os.environ.get("PATH"),
            "SSH_AUTH_SOCK": os.environ.get("SSH_AUTH_SOCK"),
            "KD_ONE_PRIVATE_KEY": os.environ.get("KD_ONE_PRIVATE_KEY"),
            "KD_ONE_USERNAME": os.environ.get("KD_ONE_USERNAME"),
            "KD_ONE_PASSWORD": os.environ.get("KD_ONE_PASSWORD"),
            "KD_ONE_PUB_IPS": os.environ.get("KD_ONE_PUB_IPS"),
            "KD_DEV_INSTALL": os.environ.get("KD_DEV_INSTALL"),
            "KD_LICENSE": "patch",
        }
        kd_env = {k: v for k, v in kd_env.iteritems() if v}
        self.vagrant = vagrant.Vagrant(quiet_stdout=False, quiet_stderr=False,
                                       env=kd_env)

    def get_ssh(self, host):
        hosts = {
            "master": "kd_master",
            "node": "kd_node1",
            "node1": "kd_node1",
        }
        host = hosts[host]
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.vagrant.hostname(host),
                    port=int(self.vagrant.port(host)),
                    username="root",
                    key_filename=self.vagrant.conf()["IdentityFile"])
        return ssh

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
        for vm in self.vagrant.status():
            if vm.state != "not_created":
                return True
        return False

    def start(self, provider=PROVIDER):
        if not self._build_cluster_flag("start"):
            return

        if self._any_vm_is_running():
            raise VagrantIsAlreadyUpException(
                "Vagrant is already up. Please, either perform \"vagrant destroy\" "
                "if you want to run tests on new cluster, or make sure you do not "
                "pass BUILD_CLUSTER env variable if you want run tests on the "
                "existing one.")

        if provider == OPENNEBULA:
            self.vagrant.up(provider=provider, no_provision=True)
            time.sleep(60)
            self.vagrant.provision()
        else:
            self.vagrant.up(provider=provider)

    def upgrade(self, upgrade_to='latest'):
        if not self._build_cluster_flag("upgrade"):
            return

        local_arg = ''
        if upgrade_to != 'latest':
            local_arg = "--local {0}".format(upgrade_to)
        ssh = self.get_ssh("master")
        ssh_exec(ssh, "kuberdock-upgrade {0}".format(local_arg))

    def cleanup(self):
        rc, out, err = self.kubectl("get pods", out_as_dict=True)
        pods = out
        for pod in pods:
            name = self._escape_command_arg(pod['name'])
            self.kcli('delete {0}'.format(name))

    def destroy(self):
        if not self._build_cluster_flag("destroy"):
            return
        self.vagrant.destroy()

    def create_pod(self, image, name, kube_type="Standard", kubes=1,
                   open_all_ports=True, restart_policy="Always",
                   start=True, wait_ports=True, healthcheck=True):
        assert_in(kube_type, ("Standard",))
        assert_in(restart_policy, ("Always", "Never", "OnFailure"))

        pod_classes = {}
        for c in KDPod.__subclasses__():
            pod_classes[c.SRC] = c

        this_pod_class = pod_classes.get(image, KDPod)
        pod = this_pod_class(self, image, name, kube_type, kubes,
                             open_all_ports, restart_policy)
        if start:
            pod.start()
        if wait_ports:
            pod.wait_for_ports()
        if healthcheck:
            pod.healthcheck()
        return pod

    def create_pa(self, yml, size="M", start=True):
        pass

    def healthcheck(self):
        # Not passing for now: AC-3199
        ssh = self.get_ssh("master")
        retcode, out, err = ssh_exec(ssh,
                                     "kuberdock-upgrade health-check-only")
        assert_eq(retcode, 0)

    def kcli(self, cmd):
        ssh = self.get_ssh("master")
        return ssh_exec(ssh, "kcli kuberdock {0}".format(cmd))

    def kubectl(self, cmd, out_as_dict=False):
        ssh = self.get_ssh("master")
        if out_as_dict:
            rc, out, err = ssh_exec(ssh, "kcli -j kubectl {}".format(cmd))
            return rc, json.loads(out), err
        return ssh_exec(ssh, "kcli kubectl {}".format(cmd))

    def docker(self, cmd, node="node1"):
        ssh = self.get_ssh(node)
        return ssh_exec(ssh, "docker {0}".format(cmd))

    def _escape_command_arg(self, arg):
        return pipes.quote(arg)


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
                 open_all_ports, restart_policy):
        self.cluster = cluster
        self.name = name
        self.image = image
        self.kube_type = kube_type
        self.kubes = kubes
        self.restart_policy = restart_policy
        self.public_ip = None
        self.ports = self._get_ports(image)
        escaped_name = self.escaped_name

        ports_arg = ''
        if open_all_ports:
            pub_ports = ",".join(["+{0}".format(p) for p in self.ports])
            ports_arg = "--container-port {0}".format(pub_ports)

        self.cluster.kcli(
            "create -C {image} --kube-type {kube_type} "
            "--kubes {kubes} --restart-policy {restart_policy} {ports_arg} {"
            "escaped_name}".format(
                **locals()))
        self.cluster.kcli("save {0}".format(self.escaped_name))

    def _get_ports(self, image):
        # Duplicated keys in yml out, pyyaml won't work :(
        # AC-3205
        rc, out, err = self.cluster.kcli(
            "image_info %s | grep number | awk -F ':' '{print $2}'" % image)
        return [int(l) for l in out.splitlines()]

    def start(self):
        rc, out, err = self.cluster.kcli("start {0}".format(self.escaped_name))
        # TODO: Handle exclamation mark in a response correctly
        self.public_ip = yaml.load(out)['public_ip']

    def stop(self):
        self.cluster.kcli("stop {0}".format(self.escaped_name))

    def delete(self):
        self.cluster.kcli("delete {0}".format(self.escaped_name))

    def wait_for_ports(self, ports=None, timeout=DEFAULT_WAIT_POD_TIMEOUT):
        ports = ports or self.ports
        self._wait_for_ports(ports, timeout)

    @property
    def escaped_name(self):
        return pipes.quote(self.name)

    def _wait_for_ports(self, ports, timeout):
        for p in ports:
            wait_net_port(self.public_ip, p, timeout)

    def get_spec(self):
        rc, out, err = self.cluster.kubectl(
            "describe pods {0}".format(self.escaped_name))
        # NOTE: Duplicated entries will be hidden!
        return yaml.load(out)

    def healthcheck(self):
        LOG.warning(
            "This is a generic KDPod class healthcheck. It might be not precise. "
            "Inherit KDPod and implement healtcheck for {0} image.".format(
                self.image))
        self._generic_healthcheck()

    def _generic_healthcheck(self):
        spec = self.get_spec()
        assert_eq(spec['kube_type'], kube_type_to_int(self.kube_type))
        assert_eq(spec['containers']['kubes'], self.kubes)
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
        self._generic_healthcheck()
        assert_in("Welcome to nginx!", self.do_GET())


class KDPredefinedApp(KDPod):
    pass


class VagrantIsAlreadyUpException(Exception):
    pass
