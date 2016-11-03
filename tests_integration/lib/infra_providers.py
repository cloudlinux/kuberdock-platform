import logging
import os
import subprocess
from abc import ABCMeta, abstractmethod, abstractproperty
from datetime import datetime

import vagrant

from exceptions import VmCreateError, VmProvisionError
from tests_integration.lib.timing import log_timing_ctx
from tests_integration.lib.utils import retry, all_subclasses

LOG = logging.getLogger(__name__)


class InfraProvider(object):
    __metaclass__ = ABCMeta

    PROVIDER = None
    created_at = None

    @classmethod
    def create(cls, provider_name, env, provider_args):
        # type: (str, dict, dict) -> InfraProvider
        providers = {c.PROVIDER: c for c in all_subclasses(cls)}
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

    @abstractmethod
    def log_vm_ips(self):
        pass


class VagrantProvider(InfraProvider):

    def __init__(self, env, provider_args):
        self.vagrant = vagrant.Vagrant(
            quiet_stdout=False, quiet_stderr=False,
            env=env, **provider_args
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
    def any_vm_exists(self):
        return any(vm.state != "not_created" for vm in self.vagrant.status())

    def get_host_ip(self, hostname):
        return self.vagrant.hostname('kd_{}'.format(hostname))

    def destroy(self):
        self.vagrant.destroy()

    def power_on(self, host):
        vm_name = self.vm_names[host]
        LOG.debug("VM Power On: '{}'".format(vm_name))
        retry(self.vagrant.up, tries=3, vm_name=vm_name)

    def power_off(self, host):
        vm_name = self.vm_names[host]
        LOG.debug("VM Power Off: '{}'".format(vm_name))
        self.vagrant.halt(vm_name=vm_name)

    def log_vm_ips(self):
        for vm in self.vagrant.status():
            LOG.debug("{} IP is: {}".format(
                vm.name, self.vagrant.hostname(vm.name)))


class VboxProvider(VagrantProvider):
    PROVIDER = "virtualbox"

    @property
    def ssh_key(self):
        # NOTE: this won't give proper results inside docker, another
        # reason why docker+vbox is not supported
        return self.vagrant.conf()["IdentityFile"]

    def start(self):
        try:
            with log_timing_ctx("vagrant up (with provision)"):
                self.vagrant.up(provider=self.PROVIDER)
            self.created_at = datetime.utcnow()
        except subprocess.CalledProcessError:
            raise VmCreateError(
                'Failed either to create or provision VMs')


class OpenNebulaProvider(VagrantProvider):
    PROVIDER = "opennebula"

    @property
    def ssh_key(self):
        def_key = "".join([os.environ.get("HOME"), "/.ssh/id_rsa"])
        return os.environ.get("KD_ONE_PRIVATE_KEY", def_key)

    def start(self):
        try:
            with log_timing_ctx("vagrant up --no-provision"):
                retry(self.vagrant.up, tries=3, interval=15,
                      provider=self.PROVIDER, no_provision=True)
            self.created_at = datetime.utcnow()
            self.log_vm_ips()
        except subprocess.CalledProcessError:
            raise VmCreateError('Failed to create VMs in OpenNebula')

        try:
            with log_timing_ctx("vagrant provision"):
                self.vagrant.provision()
        except subprocess.CalledProcessError:
            raise VmProvisionError('Failed Ansible provision')


class AwsProvider(InfraProvider):
    pass
