import logging
import os
import random
import subprocess
import time
from abc import ABCMeta, abstractmethod, abstractproperty
from contextlib import contextmanager
from datetime import datetime
from tempfile import NamedTemporaryFile

import vagrant

from exceptions import VmCreateError, VmProvisionError
from tests_integration.lib.nebula_ip_pool import NebulaIPPool
from tests_integration.lib.timing import log_timing_ctx, log_timing
from tests_integration.lib.utils import retry, all_subclasses, log_dict, \
    suppress

LOG = logging.getLogger(__name__)

INTEGRATION_TESTS_VNET = 'vlan_kuberdock_ci'
CLUSTER_CREATION_MAX_DELAY = 120


class InfraProvider(object):
    __metaclass__ = ABCMeta

    NAME = None
    created_at = None
    env = None

    @classmethod
    def from_name(cls, provider_name, env, provider_args):
        # type: (str, dict, dict) -> InfraProvider
        providers = {c.NAME: c for c in all_subclasses(cls)}
        return providers[provider_name](env, provider_args)

    @abstractmethod
    def __init__(self, env, provider_args):
        pass

    @abstractproperty
    @property
    def ssh_user(self):
        pass

    @abstractproperty
    @property
    def ssh_key(self):
        pass

    @abstractmethod
    def get_hostname(self, host):
        pass

    @abstractmethod
    def get_host_ssh_port(self, host):
        pass

    @abstractproperty
    @property
    def vm_names(self):
        pass

    @abstractproperty
    @property
    def node_names(self):
        pass

    @abstractproperty
    @property
    def rhost_names(self):
        pass

    @abstractproperty
    @property
    def any_vm_exists(self):
        pass

    @abstractmethod
    def get_host_ip(self, hostname):
        pass

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def destroy(self):
        pass

    @abstractmethod
    def power_on(self, host):
        pass

    @abstractmethod
    def power_off(self, host):
        pass


class VagrantProvider(InfraProvider):

    def __init__(self, env, provider_args):
        self.env = env
        self._vagrant_log = NamedTemporaryFile(delete=False)

        @contextmanager
        def cm():
            # Vagrant uses subprocess.check_call to execute each command.
            # Thus we need a context manager which will catch it's stdout/stderr
            # output and save it somewhere we can access it later
            yield self._vagrant_log

        self.vagrant = vagrant.Vagrant(
            quiet_stdout=False, quiet_stderr=False, env=env,
            out_cm=cm, err_cm=cm,
        )

    @property
    def ssh_user(self):
        return "root"

    def get_hostname(self, host):
        return self.vagrant.hostname(host)

    def get_host_ssh_port(self, host):
        return int(self.vagrant.port(host))

    @property
    def vm_names(self):
        return {
            "master": "kd_master",
            "node1": "kd_node1",
            "node2": "kd_node2",
            "node3": "kd_node3",
            "rhost1": "kd_rhost1",
        }

    @property
    def node_names(self):
        names = (n.name for n in self.vagrant.status() if '_node' in n.name)
        return [n.replace('kd_', '') for n in names]

    @property
    def rhost_names(self):
        names = (n.name for n in self.vagrant.status() if '_rhost' in n.name)
        return [n.replace('kd_', '') for n in names]

    @property
    def any_vm_exists(self):
        return any(vm.state != "not_created" for vm in self.vagrant.status())

    def get_host_ip(self, hostname):
        return self.vagrant.hostname('kd_{}'.format(hostname))

    def power_on(self, host):
        vm_name = self.vm_names[host]
        LOG.debug("VM Power On: '{}'".format(vm_name))
        retry(self.vagrant.up, tries=3, vm_name=vm_name)

    def power_off(self, host):
        vm_name = self.vm_names[host]
        LOG.debug("VM Power Off: '{}'".format(vm_name))
        self.vagrant.halt(vm_name=vm_name)

    def _log_vm_ips(self):
        for vm in self.vagrant.status():
            LOG.debug("{} IP is: {}".format(
                vm.name, self.vagrant.hostname(vm.name)))

    def _print_vagrant_log(self):
        self._vagrant_log.seek(0)
        log = self._vagrant_log.read() or '>>> EMPTY <<<'
        LOG.debug("\n{}\n".format(log))
        self._vagrant_log.seek(0)


class VboxProvider(VagrantProvider):
    NAME = "virtualbox"

    @property
    def ssh_key(self):
        # NOTE: this won't give proper results inside docker, another
        # reason why docker+vbox is not supported
        return self.vagrant.conf()["IdentityFile"]

    def start(self):
        log_dict(self.vagrant.env, "Cluster settings:")
        LOG.debug("Running vagrant provision")
        try:
            with log_timing_ctx("vagrant up (with provision)"):
                self.vagrant.up()
            self.created_at = datetime.utcnow()
        except subprocess.CalledProcessError:
            raise VmCreateError('Failed either to create or provision VMs')
        finally:
            self._print_vagrant_log()

    @log_timing
    def destroy(self):
        self.vagrant.destroy()


class OpenNebulaProvider(VagrantProvider):
    NAME = "opennebula"

    def __init__(self, env, provider_args):
        # type: (dict, dict) -> InfraProvider
        super(OpenNebulaProvider, self).__init__(env, provider_args)
        self.routable_ip_count = provider_args['routable_ip_count']
        self.routable_ip_pool = NebulaIPPool.factory(
            env['KD_ONE_URL'],
            env['KD_ONE_USERNAME'],
            env['KD_ONE_PASSWORD']
        )

    @property
    def ssh_key(self):
        def_key = "".join([os.environ.get("HOME"), "/.ssh/id_rsa"])
        return os.environ.get("KD_ONE_PRIVATE_KEY", def_key)

    def start(self):
        self._rnd_sleep()
        self._reserve_ips()
        log_dict(self.env, "Cluster settings:", hidden=('KD_ONE_PASSWORD',))

        LOG.debug("Running vagrant up...")
        try:
            with log_timing_ctx("vagrant up --no-provision"):
                retry(self.vagrant.up, tries=3, interval=15,
                      provider="opennebula", no_provision=True)
            self.created_at = datetime.utcnow()
            self._log_vm_ips()
        except subprocess.CalledProcessError:
            raise VmCreateError('Failed to create VMs in OpenNebula')
        finally:
            self._print_vagrant_log()

        LOG.debug("Running vagrant provision...")
        try:
            with log_timing_ctx("vagrant provision"):
                self.vagrant.provision()
        except subprocess.CalledProcessError:
            raise VmProvisionError('Failed Ansible provision')
        finally:
            self._print_vagrant_log()

        self._save_reserved_ips()

    def _rnd_sleep(self):
        delay = random.randint(0, CLUSTER_CREATION_MAX_DELAY)
        LOG.info("Sleep {}s to prevent Nebula from being flooded".format(delay))
        time.sleep(delay)

    def _reserve_ips(self):
        # Reserve Pod IPs in Nebula so that they are not taken by other
        # VMs/Pods
        ips = self.routable_ip_pool.reserve_ips(
            INTEGRATION_TESTS_VNET, self.routable_ip_count)
        # Save reserved IPs to self env so it is available for cluster to
        # appropriate IP Pool
        ips = ','.join(ips)
        self.vagrant.env['KD_ONE_PUB_IPS'] = ips
        self.env['KD_ONE_PUB_IPS'] = ips

    def _save_reserved_ips(self):
        # Write reserved IPs to master VM metadata for future GC
        master_ip = self.get_host_ip('master')
        self.routable_ip_pool.store_reserved_ips(master_ip)

    @log_timing
    def destroy(self):
        with suppress():
            self.routable_ip_pool.free_reserved_ips()
        with suppress():
            self.vagrant.destroy()


class AwsProvider(InfraProvider):
    NAME = "aws"

    def __init__(self, env, provider_args):
        self.env = self._aws_env(env)

    def _aws_env(self, env):
        pass

    @property
    def ssh_user(self):
        pass

    @property
    def ssh_key(self):
        pass

    def get_hostname(self, host):
        pass

    def get_host_ssh_port(self, host):
        pass

    @property
    def vm_names(self):
        pass

    @property
    def node_names(self):
        pass

    @property
    def rhost_names(self):
        pass

    @property
    def any_vm_exists(self):
        pass

    def get_host_ip(self, hostname):
        pass

    @log_timing
    def start(self):
        pass

    @log_timing
    def destroy(self):
        pass

    def power_on(self, host):
        pass

    def power_off(self, host):
        pass
