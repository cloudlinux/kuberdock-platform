import logging
import os
import sys
import random
import time
from contextlib import contextmanager
from tempfile import NamedTemporaryFile

from tests_integration.lib.exceptions import PipelineNotFound
from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.utils import merge_dicts, \
    center_text_message, suppress, all_subclasses, get_func_fqn, \
    format_exception
from tests_integration.lib.nebula_ip_pool import NebulaIPPool
from tests_integration.lib.timing import log_timing, log_timing_ctx

PIPELINES_PATH = '.pipelines/'
INTEGRATION_TESTS_VNET = 'vlan_kuberdock_ci'
CLUSTER_CREATION_MAX_DELAY = 120
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

    def __init__(self, name):
        # type: (str) -> None
        self.name = name
        self.settings = self._get_settings()
        self.cluster = None

        self.routable_ip_count = self.ROUTABLE_IP_COUNT
        self.vagrant_log = NamedTemporaryFile(delete=False)

        self.routable_ip_pool = NebulaIPPool.factory(
            os.environ['KD_ONE_URL'],
            os.environ['KD_ONE_USERNAME'],
            os.environ['KD_ONE_PASSWORD'])

    def _get_settings(self):
        self.defaults = {
            'KD_MASTER_CPUS': '2',
            'KD_MASTER_MEMORY': '4096',
            'KD_NODES_COUNT': '2',
            'KD_NODE_CPUS': '2',
            'KD_NODE_MEMORY': '3048',
            'KD_INSTALL_TYPE': 'qa',
            'KD_LICENSE': 'patch',
            'KD_TESTING_REPO': 'true',
            'KD_DEPLOY_SKIP': 'predefined_apps,cleanup,ui_patch',
        }
        env_list = (
            getattr(c, 'ENV', {}) for c in reversed(self.__class__.__mro__))

        settings = merge_dicts(self.defaults, *env_list)
        if self.build_cluster:
            # Allow to build multiple pipelines in parallel
            settings['VAGRANT_DOTFILE_PATH'] = os.path.join(
                PIPELINES_PATH, self.name)
        return settings

    @property
    def build_cluster(self):
        """
        Indicator whenever cluster creation was requested or not
        """
        return os.environ.get('BUILD_CLUSTER', '0') == '1'

    def run_test(self, test):
        """
        Runs a given test executing set_up/tear_down before/after a test

        :param test: a callable which represents a test and accepts one a
            KDIntegrationAPI object as a first argument
        """
        with wrap_test_log(test):
            with log_timing_ctx("Pipeline {} set_up".format(self.name)):
                self.set_up()
            test_fqn = get_func_fqn(test)
            try:
                with log_timing_ctx("Test {}".format(test_fqn)):
                    test(self.cluster)
            except Exception:
                trace = format_exception(sys.exc_info())
                LOG.error("Test {} FAILED:\n{}".format(test_fqn, trace))
                raise
            finally:
                with log_timing_ctx("Pipeline {} tear_down".format(
                        self.name)):
                    self.tear_down()

    def post_create_hook(self):
        """
        This function will be called once cluster is created.
        You can pass change any default settings, if you need to.
        """
        self.cluster.preload_docker_image('nginx')

    @log_timing
    def create(self):
        """
        Create a pipeline. Underneath creates a KD cluster and destroys it
        automatically if any error occurs during that process
        """

        @contextmanager
        def cm():
            """
            Vagrant uses subprocess.check_call to execute each command.
            Thus we need a context manager which will catch it's stdout/stderr
            output and save it somewhere we can access it later
            """
            yield self.vagrant_log

        # Do not reserve IPs and do not create cluster if wasn't requested
        if not self.build_cluster:
            self.cluster = KDIntegrationTestAPI(self.INFRA_PROVIDER,
                                                override_envs=self.settings,
                                                err_cm=cm, out_cm=cm)
            LOG.info('BUILD_CLUSTER flag not passed. Pipeline create '
                     'call skipped.')
            return

        delay = random.randint(0, CLUSTER_CREATION_MAX_DELAY)
        LOG.info("Sleep {}s to prevent Nebula from being flooded".format(delay))
        time.sleep(delay)

        try:
            self._log_begin("IP reservation")
            # Reserve Pod IPs in Nebula so that they are not taken by other
            # VMs/Pods
            ips = self.routable_ip_pool.reserve_ips(
                INTEGRATION_TESTS_VNET, self.routable_ip_count)
            # Tell reserved IPs to cluster so it creates appropriate IP Pool
            self._add_public_ips(ips)
            self._log_end("IP reservation")
            self._log_begin("Provision")
            # Create cluster
            self.cluster = KDIntegrationTestAPI(self.INFRA_PROVIDER,
                                                override_envs=self.settings,
                                                err_cm=cm, out_cm=cm)
            self.cluster.start()
            # Write reserved IPs to master VM metadata for future GC
            master_ip = self.cluster.get_host_ip('master')
            self.routable_ip_pool.store_reserved_ips(master_ip)
            self._log_end("Provision")
        except:
            self.destroy()
            raise
        finally:
            self._print_vagrant_log()

        try:
            self._log_begin("Post create hook")
            with log_timing_ctx("'{}' post_create_hook".format(self.name)):
                self.post_create_hook()
            self._log_end("Post create hook")
        except:
            self.destroy()
            raise

    def cleanup(self):
        """
        Cleans artifacts created by tests like pods/pvs, etc. Each pipeline
        may extend this method if it produces additional artifacts
        """
        self.cluster.pods.clear()
        self.cluster.pods.forget_all()
        self.cluster.pvs.clear()

    def destroy(self):
        """
        Destroys KD cluster
        """
        if not self.build_cluster:
            LOG.info('BUILD_CLUSTER flag not passed. Pipeline destroy '
                     'call skipped')
            return

        with suppress():
            self._log_begin("IP release")
            self.routable_ip_pool.free_reserved_ips()
            self._log_end("IP release")
        with suppress():
            self._log_begin("Destroy")
            self.cluster.destroy()
            self._log_end("Destroy")

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
    def from_name(cls, name):
        # type: (str) -> Pipeline
        """
        Fabric method for creating a specific pipeline class instance
        depending on a given pipe's full name (name_threadID)
        """

        available = {
            c.NAME: c for c in all_subclasses(cls) if hasattr(c, 'NAME')}

        # Cut the thread ID
        pipe_name = name.rsplit('_', 1)[0]

        if pipe_name not in available:
            raise PipelineNotFound(name)

        return available[pipe_name](name)

    def _add_public_ips(self, ip_list):
        """
        Adds given public IP addresses to the cluster settings. Will be used on
        cluster creation during provisioning

        :param ip_list: array of IPv4 in x.x.x.x format
        """

        self.settings['KD_ONE_PUB_IPS'] = ','.join(ip_list)

    def _log_begin(self, op):
        op = op.upper()
        LOG.debug(center_text_message('BEGIN {} {}'.format(self.name, op)))

    def _log_end(self, op):
        op = op.upper()
        LOG.debug(center_text_message('END {} {}'.format(self.name, op)))

    def _print_vagrant_log(self):
        """
        Sends logs produced by vagrant to the default logger
        """
        self.vagrant_log.seek(0)
        log = self.vagrant_log.read() or '>>> EMPTY <<<'

        message = '\n\n{header}\n{log}\n{footer}\n\n'
        LOG.debug(
            message.format(
                header=center_text_message(
                    'BEGIN {} VAGRANT LOGS'.format(self.name)),
                log=log,
                footer=center_text_message(
                    'END {} VAGRANT LOGS'.format(self.name)),
            )
        )


@contextmanager
def wrap_test_log(test):
    """
    Wraps test log output with START/END markers
    """
    test_name = get_func_fqn(test)
    try:
        LOG.debug(center_text_message('{} START'.format(test_name)))
        yield
    finally:
        LOG.debug(center_text_message('{} END'.format(test_name)))


class UpgradedPipelineMixin(object):
    skip_reason = "Disabled until 1.5.0 Beta becomes Release"
    ENV = {
        'KD_INSTALL_TYPE': 'release',
        'KD_DEPLOY_SKIP': 'predefined_apps,cleanup,ui_patch,route',
        'KD_LICENSE': '../../../../../../tests_integration/assets/fake_license.json',  # noqa
    }

    def post_create_hook(self):
        self.cluster.upgrade('/tmp/prebuilt_rpms/kuberdock.rpm',
                             use_testing=True, skip_healthcheck=True)
        super(UpgradedPipelineMixin, self).post_create_hook()
