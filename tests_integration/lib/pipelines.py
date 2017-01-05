import logging
import os
from collections import defaultdict
from functools import wraps
from shutil import rmtree
from tempfile import NamedTemporaryFile, mkdtemp

from tests_integration.lib.cluster_utils import enable_beta_repos, \
    set_eviction_timeout
from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.pipelines_base import Pipeline, \
    UpgradedPipelineMixin
from tests_integration.lib.utils import (
    log_debug, assert_eq, assert_in, wait_for_status, get_rnd_string,
    NODE_STATUSES)

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


class MainPipeline(Pipeline):
    NAME = 'main'
    ROUTABLE_IP_COUNT = 1
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_TIMEZONE': 'Europe/Moscow',
        'KD_DEPLOY_SKIP': 'cleanup,ui_patch'
    }

    def set_up(self):
        super(MainPipeline, self).set_up()

        # In one of the tests node is rebooted, so we need to make sure that
        # it is running before executing any tests
        nodes = self.cluster.node_names
        for node in nodes:
            self.cluster.nodes.get_node(node).wait_for_status(
                NODE_STATUSES.running)

    def post_create_hook(self):
        super(MainPipeline, self).post_create_hook()
        self.cluster.wait_for_service_pods()
        # NOTE: One of the tests reboots node and checks whether pod becomes
        # 'running' afterwards, by lowering eviction timeout pod is
        # terminated faster (default is 5 minutes)
        set_eviction_timeout(self.cluster, '30s')


class MainUpgradedPipeline(UpgradedPipelineMixin, MainPipeline):
    NAME = 'main_upgraded'


class MainAwsPipeline(MainPipeline):
    INFRA_PROVIDER = 'aws'
    NAME = 'main_aws'


class MainAwsUpgradedPipeline(UpgradedPipelineMixin, MainAwsPipeline):
    INFRA_PROVIDER = 'aws'
    NAME = 'main_aws_upgraded'


class NetworkingPipeline(Pipeline):
    NAME = 'networking'
    ROUTABLE_IP_COUNT = 2
    TCP_PORT_TO_OPEN = 8002
    UDP_PORT_TO_OPEN = 8003
    ENV = {
        'KD_NODES_COUNT': '2',
        'KD_RHOSTS_COUNT': '1',
        # kube types are used to control pod-scheduling on specific nodes
        # Ex: pod with kube_type==Standard -> node1, kube_type==Tiny -> node2
        'KD_NODE_TYPES': 'node1=Standard,node2=Tiny',
        # rhost: use the same template as for master/nodes - cent7
        'KD_NEBULA_RHOST_TEMPLATE_ID': os.environ.get('KD_NEBULA_TEMPLATE_ID'),
        # NOTE: PAs are used as a workaround for AC-4925.
        # Once AC-4448 is complete, this can be removed and test reworked.
        'KD_DEPLOY_SKIP': 'cleanup,ui_patch',
    }

    def set_up(self):
        super(NetworkingPipeline, self).set_up()
        self.cluster.recreate_routable_ip_pool()

    def post_create_hook(self):
        super(NetworkingPipeline, self).post_create_hook()
        self.cluster.preload_docker_image('nginx')
        # NOTE: Preload these imaeges so that wordpress_elasticsearch PA
        # starts quicker. Remove 'wordpress', 'mysql' and 'elasticsearch'
        # preload once AC-4448 is completed.
        self.cluster.preload_docker_image('wordpress:4')
        self.cluster.preload_docker_image('kuberdock/mysql:5.7')
        self.cluster.preload_docker_image('elasticsearch:1.7.3')
        self.cluster.wait_for_service_pods()
        # NOTE: Open some custom ports and check that isolation is still
        # working properly
        self._open_custom_ports()

    def _open_custom_ports(self):
        try:
            self.cluster.kdctl('allowed-ports open {} {}'.format(
                self.TCP_PORT_TO_OPEN, 'tcp'))
            self.cluster.kdctl('allowed-ports open {} {}'.format(
                self.UDP_PORT_TO_OPEN, 'udp'))
            _, out, _ = self.cluster.kdctl('allowed-ports list',
                                           out_as_dict=True)
            custom_ports = out['data']
            # Make sure that two ports are opened
            assert_eq(len(custom_ports), 2)

            # Make sure that both ports opened correctly
            assert_in(dict(port=self.TCP_PORT_TO_OPEN, protocol='tcp'),
                      custom_ports)
            assert_in(dict(port=self.UDP_PORT_TO_OPEN, protocol='udp'),
                      custom_ports)

        except (NonZeroRetCodeException, AssertionError) as e:
            log_debug("Couldn't open ports. Reason: {}".format(e), LOG)


class NetworkingPipelineAWS(NetworkingPipeline):
    INFRA_PROVIDER = 'aws'
    NAME = 'networking_aws'


class NetworkingUpgradedPipeline(UpgradedPipelineMixin, NetworkingPipeline):
    NAME = 'networking_upgraded'
    ENV = {
        # NOTE: PAs are used as a workaround for AC-4925.
        # Once AC-4448 is complete, this can be removed and test reworked.
        'KD_DEPLOY_SKIP': 'cleanup,ui_patch',
    }


class NetworkingRhostCent6Pipeline(NetworkingPipeline):
    NAME = 'networking_rhost_cent6'
    ENV = {
        # KD_NEBULA_RHOST_TEMPLATE_ID set in kuberdock-ci-env points to cent6
        'KD_NEBULA_RHOST_TEMPLATE_ID':
            os.environ['KD_NEBULA_RHOST_TEMPLATE_ID']
    }


class FixedIPPoolsPipeline(Pipeline):
    NAME = 'fixed_ip_pools'
    ROUTABLE_IP_COUNT = 3
    ENV = {
        'KD_FIXED_IP_POOLS': 'true',
        'KD_NODES_COUNT': '2',
    }

    def post_create_hook(self):
        super(FixedIPPoolsPipeline, self).post_create_hook()
        set_eviction_timeout(self.cluster, '30s')
        self.cluster.wait_for_service_pods()

    def cleanup(self):
        super(FixedIPPoolsPipeline, self).cleanup()
        self.cluster.ip_pools.clear()


class CephPipeline(Pipeline):
    NAME = 'ceph'
    ROUTABLE_IP_COUNT = 2
    root = os.path.abspath(os.path.join(
        __file__, '../../../dev-utils/dev-env/ansible/ceph_configs'))
    ENV = {
        'KD_NODES_COUNT': '4',
        'KD_NODE_TYPES':
            'node1=Standard,node2=Tiny,node3=High memory,node4=Standard',
        'KD_DEPLOY_SKIP': 'predefined_apps,cleanup,ui_patch,route',
        'KD_CEPH': '1',
        'KD_CEPH_USER': 'jenkins',
        'KD_CEPH_CONFIG': os.path.join(root, 'ceph.conf'),
        'KD_CEPH_USER_KEYRING': os.path.join(root, 'client.jenkins.keyring'),
        'KD_PD_NAMESPACE': 'jenkins_pool'
    }

    def tear_down(self):
        """
        Remove all CEPH volumes (PVs) after each test
        """
        self.cleanup()

    def post_create_hook(self):
        super(CephPipeline, self).post_create_hook()
        set_eviction_timeout(self.cluster, '30s')


class CephUpgradedPipeline(UpgradedPipelineMixin, CephPipeline):
    NAME = 'ceph_upgraded'


class CephFixedIPPoolsPipeline(CephPipeline):
    NAME = 'ceph_fixed_ip_pools'
    ENV = {
        'KD_FIXED_IP_POOLS': 'true',
    }

    def cleanup(self):
        super(CephFixedIPPoolsPipeline, self).cleanup()
        self.cluster.ip_pools.clear()


class KubeTypePipeline(Pipeline):
    NAME = 'kubetype'
    ROUTABLE_IP_COUNT = 3
    ENV = {
        'KD_NODES_COUNT': '3',
        'KD_NODE_TYPES': 'node1=Standard,node2=Tiny,node3=High memory',
        'KD_DEPLOY_SKIP': 'cleanup,ui_patch',
    }

    def post_create_hook(self):
        super(KubeTypePipeline, self).post_create_hook()
        self.cluster.wait_for_service_pods()
        sftp = self.cluster.get_sftp('master')
        sftp.put('tests_integration/assets/custom_redis.yaml',
                 '/tmp/custom_redis.yaml')
        self.cluster.pas.add('custom_redis.yaml', '/tmp/custom_redis.yaml')


class MovePodsPipeline(Pipeline):
    NAME = 'move_pods'
    ROUTABLE_IP_COUNT = 2
    ENV = {
        'KD_NODES_COUNT': '2',
    }

    def post_create_hook(self):
        super(MovePodsPipeline, self).post_create_hook()
        set_eviction_timeout(self.cluster, '30s')
        self.cluster.wait_for_service_pods()


class MovePodsPipelineAWS(MovePodsPipeline):
    INFRA_PROVIDER = 'aws'
    NAME = 'move_pods_aws'


class FailConditionsPipeline(Pipeline):
    NAME = 'fail_conditions'
    ROUTABLE_IP_COUNT = 1
    ENV = {
        'KD_NODES_COUNT': '1',
    }


class PodRestorePipeline(Pipeline):
    NAME = 'pod_restore'
    ROUTABLE_IP_COUNT = 2
    ENV = {
        'KD_NODES_COUNT': '1',
    }


class PodRestorePipelineAWS(PodRestorePipeline):
    INFRA_PROVIDER = 'aws'
    NAME = 'pod_restore_aws'


class MasterRestorePipeline(Pipeline):
    NAME = 'master_backup_restore'
    ROUTABLE_IP_COUNT = 3
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_DEPLOY_SKIP': 'cleanup,ui_patch,node_deploy,ippool'
    }

    def post_create_hook(self):
        pass  # Do nothing


class ReleaseUpdatePipeline(Pipeline):
    NAME = 'release_update'
    ROUTABLE_IP_COUNT = 3
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_DEPLOY_SKIP': 'predefined_apps,cleanup,ui_patch',
        'KD_INSTALL_TYPE': 'release',
    }

    def post_create_hook(self):
        enable_beta_repos(self.cluster)  # TODO remove when 1.5.0 is released
        # Upgrade itself is done later, in the mid of test
        super(ReleaseUpdatePipeline, self).post_create_hook()


class ReleaseUpdatePipelineAWS(ReleaseUpdatePipeline):
    INFRA_PROVIDER = 'aws'
    NAME = 'release_update_aws'


class ReleaseUpdateNoNodesPipeline(ReleaseUpdatePipeline):
    NAME = 'release_update_no_nodes'
    ENV = {
        'KD_NODES_COUNT': '0',
    }


class WebUIPipeline(Pipeline):
    NAME = 'web_ui'
    ROUTABLE_IP_COUNT = 1
    ENV = {
        'KD_NODES_COUNT': '1',
    }

    def post_create_hook(self):
        super(WebUIPipeline, self).post_create_hook()
        self.cluster.wait_for_service_pods()


class PredefinedApps(Pipeline):
    NAME = 'predefined_apps'
    ROUTABLE_IP_COUNT = 2
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_DEPLOY_SKIP': 'cleanup,ui_patch'
    }

    def post_create_hook(self):
        super(PredefinedApps, self).post_create_hook()
        self.cluster.wait_for_service_pods()


class PredefinedAppsAWS(PredefinedApps):
    NAME = 'predefined_apps_aws'
    INFRA_PROVIDER = 'aws'


class SSHPipeline(Pipeline):
    NAME = 'ssh_feature'
    ROUTABLE_IP_COUNT = 1
    ENV = {
        'KD_NODES_COUNT': '1'
    }

    def set_up(self):
        super(SSHPipeline, self).set_up()
        self.cluster.temp_files = self._create_temp_files()

    def tear_down(self):
        super(SSHPipeline, self).tear_down()
        self._delete_temp_files()

    # TODO move this to @hooks(setup, teardown) !!!
    def _create_temp_files(self):
        local_src_file = self._create_file()
        # Need to make an extra subdirectory level to avoid conflicts during
        # testing
        local_src_dir = mkdtemp(dir=mkdtemp())
        local_src_subdir = mkdtemp(dir=local_src_dir)
        local_files = [os.path.basename(self._create_file(
                       dst_dir=local_src_dir))
                       for _ in range(3)]
        local_files.append(os.path.join(
            os.path.basename(local_src_subdir),
            os.path.basename(self._create_file(dst_dir=local_src_subdir))))

        local_dst_file = self._create_file()
        local_dst_dir = mkdtemp()

        remote_src_file = self._create_file()
        remote_src_dir = mkdtemp(dir=local_dst_dir)
        remote_src_subdir = mkdtemp(dir=remote_src_dir)
        remote_files = [os.path.basename(self._create_file(
                        dst_dir=remote_src_dir))
                        for _ in range(3)]
        remote_files.append(os.path.join(
            os.path.basename(remote_src_subdir),
            os.path.basename(self._create_file(dst_dir=remote_src_subdir))))

        remote_dst_file = self._create_file()
        remote_dst_dir = os.path.dirname(local_src_dir)

        return {
            'local_src_file': local_src_file,
            'local_src_dir': local_src_dir,
            'local_src_subdir': local_src_subdir,
            'local_files': local_files,
            'local_dst_file': local_dst_file,
            'local_dst_dir': local_dst_dir,
            'remote_src_file': remote_src_file,
            'remote_src_dir': remote_src_dir,
            'remote_src_subdir': remote_src_subdir,
            'remote_files': remote_files,
            'remote_dst_file': remote_dst_file,
            'remote_dst_dir': remote_dst_dir
        }

    def _create_file(self, dst_dir=None):
        with NamedTemporaryFile(delete=False, dir=dst_dir) as f:
            f.write(get_rnd_string(prefix='source_file_string_'))
            f.close()
            return f.name

    def _delete_temp_files(self):
        for key in self.cluster.temp_files:
            if key != 'local_files' and key != 'remote_files':
                if os.path.isdir(self.cluster.temp_files[key]):
                    rmtree(self.cluster.temp_files[key])
                elif os.path.exists(self.cluster.temp_files[key]):
                    os.unlink(self.cluster.temp_files[key])


class SSHPipelineAWS(SSHPipeline):
    NAME = 'ssh_feature_aws'
    INFRA_PROVIDER = 'aws'


class PACatalogPipeline(Pipeline):
    NAME = 'PA_catalog'
    ROUTABLE_IP_COUNT = 1
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_DEPLOY_SKIP': 'cleanup,ui_patch',
    }


class DeleteNodePipeline(Pipeline):
    NAME = 'delete_node'
    ENV = {
        'KD_NODES_COUNT': '2',
        'KD_NODE_TYPES': 'node1=Standard,node2=Tiny',
    }


class ZFSStoragePipeline(Pipeline):
    NAME = 'zfs'
    ROUTABLE_IP_COUNT = 1
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_USE_ZFS': '1',
        'KD_DEPLOY_SKIP': 'cleanup,ui_patch',
    }

    def post_create_hook(self):
        super(ZFSStoragePipeline, self).post_create_hook()
        self.cluster.wait_for_service_pods()

        # NOTE: We need to make sure that ZFS uses EBS volumes on AWS
        for node in self.cluster.node_names:
            self.cluster.ssh_exec(node, 'zpool status', sudo=True)

        # Change default persistent disk removal schedule from 1hr to 1m, so
        # that if a first attempt to remove a disk failes we don't have to
        # wait for 1hr
        self._change_delete_pd_schedule()

    def _change_delete_pd_schedule(self):
        conf_path = '/var/opt/kuberdock/kubedock/settings.py'

        chmod_cmd = 'chmod a+rw {}'.format(conf_path)
        self.cluster.ssh_exec('master', chmod_cmd, sudo=True)

        new_schedule = (
            'printf "%s\\n" '
            '"CELERYBEAT_SCHEDULE[\'clean-deleted-persistent-drives\']'
            '[\'schedule\'] = timedelta(minutes=1)" >> {}').format(conf_path)
        self.cluster.ssh_exec('master', new_schedule, sudo=True)

        # Change settings file permissions just in case.
        chown_cmd = 'chown nginx:nginx {}'.format(conf_path)

        self.cluster.ssh_exec('master', chown_cmd, sudo=True)
        # Restart emperor
        self.cluster.ssh_exec('master', 'systemctl restart emperor.uwsgi',
                              sudo=True)


class ZFSStorageUpgradedPipeline(UpgradedPipelineMixin, ZFSStoragePipeline):
    NAME = 'zfs_upgraded'


class ZFSStorageAWSPipeline(ZFSStoragePipeline):
    INFRA_PROVIDER = 'aws'
    NAME = 'zfs_aws'


class ZFSStorageAWSUpgradedPipeline(UpgradedPipelineMixin, ZFSStoragePipeline):
    INFRA_PROVIDER = 'aws'
    NAME = 'zfs_aws_upgraded'


class SharedIPPipeline(Pipeline):
    NAME = 'shared_ip'
    ROUTABLE_IP_COUNT = 1
    ENV = {
        'KD_NODES_COUNT': '2',
        'KD_NODE_TYPES':
            'node1=Standard,node2=High memory',
    }


class SharedIPPipelineAWS(SharedIPPipeline):
    INFRA_PROVIDER = 'aws'
    NAME = 'shared_ip_aws'


class VerticalScalabilityPipeline(Pipeline):
    NAME = 'vertical_scalability'
    ROUTABLE_IP_COUNT = 3
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_NODE_CPUS': '4',
        'KD_NODE_MEMORY': '4096',
        'KD_DEPLOY_SKIP': 'cleanup,ui_patch',
        'KD_NODE_TYPES': 'node1=standard'
    }


class LoadTestingNodeResizePipeline(Pipeline):
    NAME = 'load_testing_node_resize'
    tags = ['load']
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_NODE_TYPES': 'node1=Standard',
        'KD_DEPLOY_SKIP': 'cleanup,ui_patch'
    }


class LoadTestingNodeResizePipelineAWS(LoadTestingNodeResizePipeline):
    NAME = 'load_testing_node_resize_aws'
    INFRA_PROVIDER = 'aws'
    ENV = {
        'NODE_SIZE': 't2.medium'
    }


class StressTestingPipeline(Pipeline):
    NAME = 'stress_testing'
    ROUTABLE_IP_COUNT = 10
    ENV = {
        'KD_NODES_COUNT': '10',
        'KD_DEPLOY_SKIP': 'cleanup,ui_patch',
        'KD_NODE_TYPES': ('node1=Tiny,node2=Tiny,node3=Tiny,node4=Tiny,'
                          'node5=Tiny,node6=Tiny,node7=Tiny,node8=Tiny,'
                          'node9=Tiny,node10=Tiny'),
    }
    tags = ['load']

    def post_create_hook(self):
        super(StressTestingPipeline, self).post_create_hook()
        self.cluster.wait_for_service_pods()


class LoadTestingPipeline(Pipeline):
    NAME = 'load_testing'
    ROUTABLE_IP_COUNT = 50
    tags = ['load']
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_NODE_CPUS': '4',
        'KD_NODE_MEMORY': '8192',
    }


class LoadTestingAwsPipeline(LoadTestingPipeline):
    NAME = 'load_testing_aws'
    INFRA_PROVIDER = 'aws'
    ENV = {
        'KD_NODES_COUNT': '1',
        'NODE_SIZE': 'c3.xlarge'  # https://aws.amazon.com/ec2/instance-types/
    }


class LoadTestingPipeline2(LoadTestingPipeline):
    # TODO: remove this pipeline once AC-5648 is implemented
    NAME = 'load_testing_2'


class LoadTestingAwsPipeline2(LoadTestingAwsPipeline):
    # TODO: remove this pipeline once AC-5648 is implemented
    NAME = 'load_testing_aws_2'


class HugeClusterUpgradePipeline(Pipeline):
    NAME = 'huge_cluster_upgrade'
    tags = ['load']
    ENV = {
        'KD_INSTALL_TYPE': 'release',
        'KD_NODES_COUNT': '15',  # Increase to 50 after test
        'KD_NODE_TYPES': ','.join(
            ["node{}=Tiny".format(n) for n in range(1, 16)]),  # Increase to 50 after test
        'KD_NODE_CPUS': '1',
        'KD_NODE_MEMORY': '2048',
    }


class HugeClusterUpgradeAwsPipeline(HugeClusterUpgradePipeline):
    NAME = 'huge_cluster_upgrade_aws'
    INFRA_PROVIDER = 'aws'
    ENV = {
        'NODE_SIZE': 't2.micro'  # https://aws.amazon.com/ec2/instance-types/
    }


# How many pipelines can be created at time when running on infra provider.
infra_provider_slots = {
    "opennebula": 35,
    "aws": 2
}
pipelines = defaultdict(list)


def pipeline(name, thread=1, skip_reason=""):
    """
    Register that a test should be executed in a pipeline with a given name
    in a specified thread. Decorator can be used multiple times which means
    that a test should be executed in different pipelines.
    That allows a test runner to know which pipelines should it create and
    which tests should it run in them. Does nothing to the test function

    :param name: the name of a pipeline. Is used to find a Pipeline class
        defined above
    :param thread: the thread id to pin the test to. Is used to create
        multiple pipelines of the same type and run a test in a particular
        one.
        Eg. If you decorate one test with pipeline('main', thread=1) and
        another with pipeline('main', thread=2) then a runner will create 2
        main clusters and run each test on its own cluster
    :param skip_reason: Ticket number - why the test is skipped.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)

        wrapper.meta = {}
        if skip_reason:
            wrapper.meta['skip_reason'] = skip_reason

        pipelines[(name, thread)].append(wrapper)
        # Return original f so that next @pipeline does not create nested wrap
        return f

    return decorator


class DensityPipeline(Pipeline):
    NAME = 'density'
    ROUTABLE_IP_COUNT = 70
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_NODE_CPUS': '4',
        'KD_NODE_MEMORY': '8192',
        'KD_DEPLOY_SKIP': 'cleanup,ui_patch',
        'KD_NODE_TYPES': 'node1=standard'
    }


class DensityPipelineAWS(DensityPipeline):
    INFRA_PROVIDER = 'aws'
    NAME = 'density_aws'
    ENV = {
        'NODE_SIZE': 't2.large'
    }
