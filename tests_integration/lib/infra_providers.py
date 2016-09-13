import logging
import os
import random
import subprocess
import shutil
import time
import tempfile
from abc import ABCMeta, abstractmethod, abstractproperty
from contextlib import contextmanager
from datetime import datetime
from tempfile import NamedTemporaryFile

import vagrant
import boto3.ec2

from exceptions import VmCreateError, VmProvisionError, VmNotFoundError
from tests_integration.lib.nebula_ip_pool import NebulaIPPool
from tests_integration.lib.timing import log_timing_ctx, log_timing
from tests_integration.lib.utils import retry, all_subclasses, log_dict, \
    suppress, local_exec_live

LOG = logging.getLogger(__name__)
logging.getLogger('boto').setLevel(logging.WARNING)

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
    __metaclass__ = ABCMeta

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
            "node4": "kd_node4",
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
        return self.env.get("KD_ONE_PRIVATE_KEY", def_key)

    def start(self):
        self._rnd_sleep()
        self._reserve_ips()
        log_dict(self.env, "Cluster settings:")

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
        self.env = env
        self._ec2_cached = None
        self._host_to_id_cached = None
        self._inventory = None

    @property
    def _ec2(self):
        if self._ec2_cached:
            return self._ec2_cached

        self._ec2_cached = boto3.resource(
            'ec2',
            self.env['AWS_S3_REGION'],
            aws_access_key_id=self.env['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=self.env['AWS_SECRET_ACCESS_KEY']
        )
        return self._ec2_cached

    @property
    def ssh_user(self):
        return "centos"

    @property
    def ssh_key(self):
        return self.env['AWS_SSH_KEY']

    def _get_ec2_instance(self, name):
        try:
            instance, = self._ec2.instances.filter(Filters=[
                {"Name": 'tag:Name', "Values": [name, ]},
                {
                    "Name": 'instance-state-name',
                    "Values": ["pending", "running", "shutting-down",
                               "stopping", "stopped"]}
            ])
        except ValueError:
            raise VmNotFoundError("No vm with name `{0}`".format(name))
        return instance

    def get_hostname(self, host):
        instance = self._get_ec2_instance(host)
        return instance.public_dns_name

    def get_host_ssh_port(self, host):
        return 22

    @property
    def vm_names(self):
        prefix = self.env["KUBE_AWS_INSTANCE_PREFIX"]
        result = {
            "master": "{0}-master".format(prefix),
            "node1": "{0}-minion-1".format(prefix),
            "node2": "{0}-minion-2".format(prefix),
            "node3": "{0}-minion-3".format(prefix),
            # "rhost1": "kd_rhost1",
        }
        for instance in result.values():
            try:
                host = self._get_ec2_instance(instance).private_dns_name
                result[host] = instance
            except VmNotFoundError:
                pass
        return result

    @property
    def node_names(self):
        result = []
        for name in ['node1', 'node2', 'node3']:
            try:
                self._get_ec2_instance(self.vm_names[name])
                result.append(name)
            except VmNotFoundError:
                pass
        return result

    @property
    def rhost_names(self):
        pass

    @property
    def any_vm_exists(self):
        pass

    def get_host_ip(self, hostname):
        if hostname not in self.vm_names:
            raise VmNotFoundError("Host with name `{0}` not found.")
        instance = self._get_ec2_instance(self.vm_names[hostname])
        result = instance.public_ip_address
        if result is None:
            raise VmCreateError("No IP assigned to `{0}`".format(hostname))
        return result

    def _get_inventory(self):
        with tempfile.NamedTemporaryFile(prefix="inv-", delete=False) as inv:
            hosts = {}
            for name in ['master', ] + self.node_names:
                hosts[name] = retry(
                    self.get_host_ip, tries=3, interval=20,
                    hostname=name)
            for host, host_ip in hosts.items():
                inv.write('kd_{0} ansible_host={1} '
                          'ansible_ssh_user=centos\n'.format(host, host_ip))
            inv.write('[master]\nkd_master\n')
            hosts.pop('master')
            inv.write('[node]\n{0}'.format(
                '\n'.join("kd_{0}".format(node) for node in hosts)))
            return inv.name

    @property
    def extra_vars(self):
        keys_map = [
            ("add_ssh_pub_keys", 'KD_ADD_SHARED_PUB_KEYS'),
            ("install_type", 'KD_INSTALL_TYPE'),
            ("host_builds_path", 'KD_BUILD_DIR'),
            ("dotfiles", 'KD_DOT_FILES'),
            ("hook", 'KD_MASTER_HOOK'),
            ("license_path", 'KD_LICENSE'),
            ("no_wsgi", 'KD_NO_WSGI'),
            ("git_ref", 'KD_GIT_REF'),
            ("public_ips", 'KD_ONE_PUB_IPS'),
            ("fixed_ip_pools", 'KD_FIXED_IP_POOLS'),
            ("use_ceph", 'KD_CEPH'),
            ("ceph_user", 'KD_CEPH_USER'),
            ("ceph_config", 'KD_CEPH_CONFIG'),
            ("ceph_user_keyring", 'KD_CEPH_USER_KEYRING'),
            ("pd_namespace", 'KD_PD_NAMESPACE'),
            ("node_types", 'KD_NODE_TYPES'),
            ("timezone", 'KD_TIMEZONE'),
            ("install_plesk", 'KD_INSTALL_PLESK'),
            ("plesk_license", 'KD_PLESK_LICENSE'),
            ("use_zfs", 'KD_USE_ZFS'),
            ("install_whmcs", 'KD_INSTALL_WHMCS'),
            ("whmcs_license", 'KD_WHMCS_LICENSE'),
            ("whmcs_domain_name", 'KD_WHMCS_DOMAIN_NAME'),
            ("add_timestamps", 'KD_ADD_TIMESTAMPS'),
            ("testing", 'KD_TESTING_REPO'),
        ]
        env = self.env
        return ' '.join(
            "{0}={1}".format(var_name, env[key]) for
            var_name, key in keys_map if key in env)

    def _check_rpms(self):
        install_type = self.env['KD_INSTALL_TYPE']
        if install_type == 'release':
            if os.path.exists('./kuberdock.rpm'):
                raise VmCreateError("Kuberdock rpm found.")
        else:
            rpm_location = './builds/kuberdock.rpm'
            if os.path.exists(rpm_location):
                shutil.copy(rpm_location, ".")
            else:
                raise VmCreateError("No kuberdock package.")

    @property
    def _host_to_id(self):
        if self._host_to_id_cached is not None:
            return self._host_to_id_cached
        else:
            instances = self._ec2.instances.filter(Filters=[{
                "Name": "tag:KubernetesCluster",
                "Values": [self.env['KUBE_AWS_INSTANCE_PREFIX'], ]
            }])
            result = {}
            for instance in instances:
                tags = dict((tag['Key'], tag['Value'])
                            for tag in instance.tags)
                inst_id = instance.id
                result[tags['Name']] = inst_id
            LOG.debug("Host to ip maping: {0}".format(result))
            return result

    def _get_node_types(self):
        node_types = self.env.get('KD_NODE_TYPES')
        parsed_types = (pair.split('=') for pair
                        in node_types.split(','))
        converted = ((self.vm_names[node], "%s" % size)
                     for node, size in parsed_types)
        return ';'.join("=".join(item) for item in converted)

    @log_timing
    def start(self):
        log_dict(self.env, "Cluster settings:")
        LOG.debug("Running aws-kd-deploy.sh...")

        if self._ec2 is None:
            raise VmCreateError('Failed to connect AWS')

        self._check_rpms()
        node_types = self._get_node_types()
        local_exec_live([
            "bash", "-c",
            "KUBE_AWS_USE_TESTING={0} NUM_NODES={1} "
            "KUBE_AWS_NODE_TYPES=\"{2}\" "
            "aws-kd-deploy/cluster/aws-kd-deploy.sh".format(
                "yes" if self.env.get('KD_TESTING_REPO') else "no",
                self.env['KD_NODES_COUNT'], node_types
            )])
        log_dict(self.env, "Cluster settings:")
        LOG.debug("Generating inventory")
        self._inventory = self._get_inventory()
        LOG.debug("Running ansible provision...")
        skip_tags = ','.join(
            self.env['KD_DEPLOY_SKIP'].split(',') + ['non_aws', ])
        extra_vars = self.extra_vars
        local_exec_live([
            "ansible-playbook", "dev-utils/dev-env/ansible/main.yml", "-i",
            self._inventory, "--skip-tags", skip_tags,
            '--extra-vars="{0}"'.format(extra_vars)])

    @log_timing
    def destroy(self):
        LOG.debug("Running aws-kd-down.sh...")
        local_exec_live(['bash', 'aws-kd-deploy/cluster/aws-kd-down.sh'])
        os.remove(self._inventory)

    def power_on(self, host):
        vm_id = self._host_to_id[self.vm_names[host]]
        self._ec2.stop_instances(instance_ids=[vm_id])

    def power_off(self, host):
        vm_id = self._host_to_id[self.vm_names[host]]
        self._ec2.start_instances(instance_ids=[vm_id])
