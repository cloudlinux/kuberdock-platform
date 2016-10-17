import os
from collections import defaultdict
from functools import wraps
from ipaddress import IPv4Network
from shutil import rmtree

from tests_integration.lib.pipelines_base import Pipeline, \
    UpgradedPipelineMixin
from tests_integration.lib.integration_test_utils import set_eviction_timeout
from tempfile import NamedTemporaryFile, mkdtemp

from tests_integration.lib.integration_test_utils import get_rnd_string


class MainPipeline(Pipeline):
    NAME = 'main'
    ROUTABLE_IP_COUNT = 1
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_TIMEZONE': 'Europe/Moscow'
    }


class MainUpgradedPipeline(UpgradedPipelineMixin, MainPipeline):
    NAME = 'main_upgraded'


class NetworkingPipeline(Pipeline):
    NAME = 'networking'
    ROUTABLE_IP_COUNT = 2
    ENV = {
        'KD_NODES_COUNT': '2',
        'KD_RHOSTS_COUNT': '1',
        # kube types are used to control pod-scheduling on specific nodes
        # Ex: pod with kube_type==Standard -> node1, kube_type==Tiny -> node2
        'KD_NODE_TYPES': 'node1=Standard,node2=Tiny',
        # rhost: use the same template as for master/nodes - cent7
        'KD_NEBULA_RHOST_TEMPLATE_ID': os.environ.get('KD_NEBULA_TEMPLATE_ID')
    }

    def set_up(self):
        super(NetworkingPipeline, self).set_up()
        self.cluster.preload_docker_image('nginx')
        self.cluster.recreate_routable_ip_pool()
        self.cluster.wait_for_service_pods()


class NetworkingUpgradedPipeline(UpgradedPipelineMixin, NetworkingPipeline):
    NAME = 'networking_upgraded'


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

    def cleanup(self):
        super(FixedIPPoolsPipeline, self).cleanup()
        self.cluster.ip_pools.clear()


class CephPipeline(Pipeline):
    NAME = 'ceph'
    ROUTABLE_IP_COUNT = 2
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_DEPLOY_SKIP': 'predefined_apps,cleanup,ui_patch,route',
        'KD_CEPH': '1',
        'KD_CEPH_USER': 'jenkins',
        'KD_CEPH_CONFIG': 'ceph_configs/ceph.conf',
        'KD_CEPH_USER_KEYRING': 'ceph_configs/client.jenkins.keyring',
        'KD_PD_NAMESPACE': 'jenkins_pool'
    }

    def tear_down(self):
        """
        Remove all Ceph images
        """
        self.cleanup()


class CephUpgradedPipeline(UpgradedPipelineMixin, CephPipeline):
    NAME = 'ceph_upgraded'


class KubeTypePipeline(Pipeline):
    NAME = 'kubetype'
    ROUTABLE_IP_COUNT = 2
    ENV = {
        'KD_NODES_COUNT': '2',
        'KD_NODE_TYPES': 'node1=standard,node2=tiny'
    }


class MovePodsPipeline(Pipeline):
    NAME = 'move_pods'
    ROUTABLE_IP_COUNT = 2
    ENV = {
        'KD_NODES_COUNT': '2',
    }

    def post_create_hook(self, *args, **kwargs):
        set_eviction_timeout(self.cluster, '30s')
        return super(MovePodsPipeline, self).post_create_hook(*args, **kwargs)


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

    def cleanup(self):
        super(PodRestorePipeline, self).cleanup()
        self.cluster.recreate_routable_ip_pool()


# TODO: Drop in 1.4 release
class PodRestoreUpgradedPipeline(UpgradedPipelineMixin, PodRestorePipeline):
    NAME = 'pod_restore_upgraded'


class MasterRestorePipeline(Pipeline):
    NAME = 'master_backup_restore'
    ROUTABLE_IP_COUNT = 2
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_DEPLOY_SKIP': 'cleanup,ui_patch'
    }

    def set_up(self):
        self.cleanup()


class ReleaseUpdatePipeline(Pipeline):
    NAME = 'release_update'
    ROUTABLE_IP_COUNT = 1
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_DEPLOY_SKIP': 'predefined_apps,cleanup,ui_patch,ippool',
        'KD_INSTALL_TYPE': 'release',
    }

    # TODO: Delete when 1.4.0 released
    def post_create_hook(self):
        super(ReleaseUpdatePipeline, self).post_create_hook()
        cmd = """
        MAIN_INTERFACE=$(ip route get 8.8.8.8 | egrep 'dev\s+.+?\s+src' -o | awk '{print $2}');  # noqa
        ip addr show dev $MAIN_INTERFACE | awk 'NR==3 { print $2 }'
        """
        _, main_ip, _ = self.cluster.ssh_exec('master', cmd)

        ip_pool = str(IPv4Network(unicode(main_ip), strict=False))
        cmd = 'create-ip-pool -s {}'.format(ip_pool)
        self.cluster.manage(cmd)


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


class SSHPipeline(Pipeline):
    NAME = 'ssh_feature'
    ROUTABLE_IP_COUNT = 1
    ENV = {
        'KD_NODES_COUNT': '1'
    }

    def set_up(self):
        self.cluster.temp_files = self._create_temp_files()
        super(SSHPipeline, self).set_up()

    def tear_down(self):
        super(SSHPipeline, self).tear_down()
        self._delete_temp_files()

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


pipelines = defaultdict(list)


def pipeline(name, thread=1):
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
    """

    def wrap(f):
        pipelines[(name, thread)].append(f)

        @wraps(f)
        def wrapped(*args, **kwargs):
            return f(*args, **kwargs)

        return wrapped

    return wrap
