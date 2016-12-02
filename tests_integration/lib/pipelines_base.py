import logging
import os
import sys

from tests_integration.lib.exceptions import PipelineNotFound, \
    ClusterAlreadyCreated
from tests_integration.lib.infra_providers import InfraProvider
from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.timing import log_timing, log_timing_ctx
from tests_integration.lib.utils import merge_dicts, \
    all_subclasses, get_func_fqn, \
    format_exception, log_begin, log_end

PIPELINES_PATH = '.pipelines/'
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


class Pipeline(object):
    """
    The idea is that an integration test requires a KD cluster of some type,
    created with some specific parameters. Creating a cluster for each
    test is slow so we can group tests which require the same type of cluster
    and execute them on a same cluster. We call that group a pipeline.

    Pipeline is responsible for creating a KD cluster with a given set of
    settings and running tests on it. Also a Pipeline has some unittest-like
    set_up/tear_down methods which are executed before/after test, so someone
    may think of it as a TestCase where setUpClass creates a cluster.

    Derived Pipeline class may contain an ENV class variable which defines
    environment variables which are used by vagrant/ansible to deploy
    cluster. These settings are merged with the self.default and override
    real environment variables. So the order settings are considered is:
    DerivedPipelineClass.ENV <- BasePipelineClass.defaults <- environment
    variables
    """
    INFRA_PROVIDER = "opennebula"
    ROUTABLE_IP_COUNT = 0
    skip_reason = ""
    tags = ["general"]

    def __init__(self, name):
        # type: (str) -> None
        self.name = name
        self.env = self._get_pipeline_env()
        self.infra_provider = InfraProvider.from_name(
            self.INFRA_PROVIDER, self.env,
            {"routable_ip_count": self.ROUTABLE_IP_COUNT}
        )
        self.cluster = KDIntegrationTestAPI(self.infra_provider)

    def _get_pipeline_env(self):
        default_env = {
            'KD_MASTER_CPUS': '2',
            'KD_MASTER_MEMORY': '4096',
            'KD_NODES_COUNT': '1',
            'KD_NODE_CPUS': '2',
            'KD_NODE_MEMORY': '3048',
            'KD_INSTALL_TYPE': 'qa',
            'KD_LICENSE': 'patch',
            'KD_TESTING_REPO': 'true',
            'KD_DEPLOY_SKIP': 'predefined_apps,cleanup,ui_patch',

            'MASTER_SIZE': 'm3.medium',
            'NODE_SIZE': 'm3.medium',
            'NUM_NODES': '1',
            'AWS_EBS_DEFAULT_SIZE': '3',
            'KUBE_AWS_INSTANCE_PREFIX': 'jenkins-kd',
        }
        take_from_os = [
            "HOME",
            "PATH",
            "SSH_AUTH_SOCK",

            "DOCKER_TLS_VERIFY",
            "DOCKER_HOST",
            "DOCKER_CERT_PATH",

            "VAGRANT_CWD",
            "VAGRANT_NO_PARALLEL",
            "VAGRANT_DOTFILE_PATH",

            "ANSIBLE_CALLBACK_WHITELIST",

            "KD_ONE_URL",
            "KD_ONE_USERNAME",
            "KD_ONE_PASSWORD",
            "KD_ONE_PRIVATE_KEY",

            "KD_MASTER_MEMORY",
            "KD_MASTER_CPUS",
            "KD_NODE_MEMORY",
            "KD_NODE_CPUS",
            "KD_NODES_COUNT",
            "KD_NODE_TYPES",
            "KD_NEBULA_TEMPLATE_ID",

            "KD_RHOSTS_COUNT",
            "KD_NEBULA_RHOST_TEMPLATE_ID",

            "KD_ONE_PUB_IPS",
            "KD_LICENSE",
            "KD_INSTALL_TYPE",
            "KD_TESTING_REPO",
            "KD_FIXED_IP_POOLS",
            "KD_TIMEZONE"

            "KD_CEPH",
            "KD_CEPH_USER",
            "KD_CEPH_CONFIG",
            "KD_CEPH_USER_KEYRING",
            "KD_PD_NAMESPACE",

            "KD_INSTALL_PLESK",
            "KD_PLESK_LICENSE",

            "KUBE_AWS_ZONE",
            "AWS_S3_REGION",
            "MASTER_SIZE",
            "NODE_SIZE",
            "AWS_EBS_DEFAULT_SIZE",
            "KUBE_AWS_INSTANCE_PREFIX",
            "AWS_SSH_KEY",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",

            "KD_ADD_TIMESTAMPS"
        ]
        os_env = {e: os.environ.get(e)
                  for e in take_from_os if os.environ.get(e)}

        pipeline_envs = [getattr(c, 'ENV', {})
                         for c in reversed(self.__class__.__mro__)]

        full_env = merge_dicts(default_env, os_env, *pipeline_envs)

        if self.build_cluster:
            # Allow to build multiple vagrant pipelines in parallel
            full_env['VAGRANT_DOTFILE_PATH'] = os.path.join(
                PIPELINES_PATH, self.name)

        return full_env

    @property
    def build_cluster(self):
        """
        Indicator whenever cluster creation was requested or not
        """
        return os.environ.get('BUILD_CLUSTER', '0') == '1'

    @log_timing
    def create(self):
        """
        Create a pipeline. Underneath creates a KD cluster and destroys it
        automatically if any error occurs during that process
        """
        # Do not create cluster if wasn't requested.
        if not self.build_cluster:
            LOG.info('BUILD_CLUSTER flag not passed. Pipeline create '
                     'call skipped.')
            return

        if self.infra_provider.any_vm_exists:
            raise ClusterAlreadyCreated(
                "Cluster is already up. Either perform \"vagrant destroy\" "
                "(or provider alternative) if you want to run tests on new "
                "cluster, or make sure you do not pass BUILD_CLUSTER env "
                "variable if you want run tests on the existing one.")

        try:
            log_begin("Provision", self.name)
            self.infra_provider.start()
            log_end("Provision", self.name)

            log_begin("Pipeline post create hook", self.name)
            with log_timing_ctx("'{}' post_create_hook".format(self.name)):
                self.post_create_hook()
            log_end("Pipeline post create hook", self.name)
        except:
            self.destroy()
            raise

    def post_create_hook(self):
        """
        This function will be called once cluster is created.
        You can pass change any default settings, if you need to.
        """
        self.cluster.preload_docker_image('nginx')

    def run_test(self, test):
        """
        Runs a given test executing set_up/tear_down before/after a test

        :param test: a callable which represents a test and accepts one a
            KDIntegrationAPI object as a first argument
        """
        test_fqn = get_func_fqn(test)
        log_begin(test_fqn, self.name)

        with log_timing_ctx("Pipeline {} set_up".format(self.name)):
            self.set_up()
        try:
            with log_timing_ctx("Test {}".format(test_fqn)):
                test(self.cluster)
        except Exception:
            trace = format_exception(sys.exc_info())
            LOG.error("Test {} FAILED:\n{}".format(test_fqn, trace))
            raise
        finally:
            with log_timing_ctx("Pipeline {} tear_down".format(self.name)):
                self.tear_down()
            log_end(test_fqn, self.name)

    def cleanup(self):
        """
        Cleans artifacts created by tests like pods/pvs, etc. Each pipeline
        may extend this method if it produces additional artifacts
        """
        self.cluster.pods.clear()
        self.cluster.pods.forget_all()
        self.cluster.pvs.clear()
        self.cluster.login_to_kcli2("test_user")

    def destroy(self):
        """
        Destroys KD cluster
        """
        if not self.build_cluster:
            LOG.info('BUILD_CLUSTER flag not passed. Pipeline destroy '
                     'call skipped')
            return

        log_begin("Destroy", self.name)
        self.infra_provider.destroy()
        log_end("Destroy", self.name)

    def set_up(self):
        """
        Perform a set up for test before running it. By default it performs a
        cluster cleanup
        """
        self.cleanup()

    def tear_down(self):
        """
        Runs right after a test even if it failed or raised an exception. By
        default does nothing
        """
        pass

    @classmethod
    def class_from_name(cls, name):
        """
        Fabric method for returning a specific pipeline class
        depending on a given pipe's full name (name_threadID)
        """

        available = {
            c.NAME: c for c in all_subclasses(cls) if hasattr(c, 'NAME')}

        # Cut the thread ID
        pipe_name = name.rsplit('_', 1)[0]

        if pipe_name not in available:
            raise PipelineNotFound(name)

        return available[pipe_name]

    @classmethod
    def from_name(cls, name):
        # type: (str) -> Pipeline
        """
        Fabric method for creating a specific pipeline class instance
        depending on a given pipe's full name (name_threadID)
        """
        return cls.class_from_name(name)(name)


class UpgradedPipelineMixin(object):
    ENV = {
        'KD_INSTALL_TYPE': 'release',
        'KD_DEPLOY_SKIP': 'predefined_apps,cleanup,ui_patch,route',
        'KD_LICENSE': '../../../../../../tests_integration/assets/fake_license.json',  # noqa
    }

    def post_create_hook(self):
        self._add_beta_repos()  # TODO remove when 1.5.0 is released
        self.cluster.upgrade('/tmp/prebuilt_rpms/kuberdock.rpm',
                             use_testing=True, skip_healthcheck=True)
        self.cluster.upgrade_rhosts('/tmp/git-kcli-deploy.sh',
                                    use_testing=True)
        super(UpgradedPipelineMixin, self).post_create_hook()

    def _add_beta_repos(self):
        all_hosts = ['master']
        all_hosts.extend(self.cluster.node_names)
        all_hosts.extend(self.cluster.rhost_names)
        for host in all_hosts:
            cmd = """cat > /etc/yum.repos.d/kube-cloudlinux-beta6.repo << EOF
[kube-beta6]
name=kube-beta-6
baseurl=http://repo.cloudlinux.com/kuberdock-beta/6/x86_64/
enabled=1
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF"""
            self.cluster.ssh_exec(host, cmd)
            cmd = """cat > /etc/yum.repos.d/kube-cloudlinux-beta7.repo << EOF
[kube-beta7]
name=kube-beta-7
baseurl=http://repo.cloudlinux.com/kuberdock-beta/7/x86_64/
enabled=1
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF"""
            self.cluster.ssh_exec(host, cmd)
