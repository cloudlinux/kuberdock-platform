import logging
import os
import random
import time
from contextlib import contextmanager
from tempfile import NamedTemporaryFile

from tests_integration.lib.exceptions import PipelineNotFound, \
    NonZeroRetCodeException, ClusterUpgradeError, VmCreationError
from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.integration_test_utils import NebulaIPPool, \
    merge_dicts, get_test_full_name, center_text_message, suppress

PIPELINES_PATH = '.pipelines/'
INTEGRATION_TESTS_VNET = 'vlan_kuberdock_ci'
CLUSTER_CREATION_MAX_DELAY = 30
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


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

    def __init__(self, name):
        # type: (str) -> None
        self.name = name
        self.settings = self._get_settings()
        self.cluster = None

        self.routable_ip_count = getattr(self, 'ROUTABLE_IP_COUNT', 0)
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
            'KD_NODE_MEMORY': '3048',
            'KD_LICENSE': 'patch',
            'KD_TESTING_REPO': 'true',
            'KD_DEPLOY_SKIP': 'predefined_apps,cleanup,ui_patch',
            'VAGRANT_NO_PARALLEL': '1',
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
        test_name = get_test_full_name(test)
        logger.debug(center_text_message('{} START'.format(test_name)))
        self.set_up()
        try:
            test(self.cluster)
        finally:
            self.tear_down()
            logger.debug(center_text_message('{} END'.format(test_name)))

    def post_create_hook(self):
        """
        This function will be called once cluster is created.
        You can pass change any default settings, if you need to.
        """
        pass

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
            self.cluster = KDIntegrationTestAPI(
                override_envs=self.settings, err_cm=cm, out_cm=cm)
            logger.info('BUILD_CLUSTER flag not passed. Pipeline create '
                        'call skipped.')
            return

        # Prevent Nebula from being flooded by vm-create requests (AC-3914)
        delay = random.randint(0, CLUSTER_CREATION_MAX_DELAY)
        time.sleep(delay)

        try:
            # Reserve Pod IPs in Nebula so that they are not taken by other
            # VMs/Pods
            ips = self.routable_ip_pool.reserve_ips(
                INTEGRATION_TESTS_VNET, self.routable_ip_count)
            # Tell reserved IPs to cluster so it creates appropriate IP Pool
            self._add_public_ips(ips)
            # Create cluster
            self.cluster = KDIntegrationTestAPI(override_envs=self.settings,
                                                err_cm=cm, out_cm=cm)
            self.cluster.start()
            # Write reserved IPs to master VM metadata for future GC
            master_ip = self.cluster.get_host_ip('master')
            self.routable_ip_pool.store_reserved_ips(master_ip)
            self.post_create_hook()
        except:
            self.destroy()
            raise
        finally:
            self._print_vagrant_log()

    def cleanup(self):
        """
        Cleans artifacts created by tests like pods/pvs, etc. Each pipeline
        may extend this method if it produces additional artifacts
        """
        self.cluster.delete_all_pods()
        self.cluster.forget_all_pods()
        self.cluster.delete_all_pvs()

    def destroy(self):
        """
        Destroys KD cluster
        """
        if not self.build_cluster:
            logger.info('BUILD_CLUSTER flag not passed. Pipeline destroy '
                        'call skipped')
            return

        with suppress():
            self.routable_ip_pool.free_reserved_ips()
        with suppress():
            self.cluster.destroy()

    def set_up(self):
        """
        Perform a set up for test before running it. By default it performs a
        cluster cleanup
        """
        self.cleanup()
        self.cluster.preload_docker_image('nginx')

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

        def all_subclasses(c):
            return c.__subclasses__() + \
                   [g for s in c.__subclasses__() for g in all_subclasses(s)]

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

    def _print_vagrant_log(self):
        """
        Sends logs produced by vagrant to the default logger
        """
        self.vagrant_log.seek(0)
        log = self.vagrant_log.read() or '>>> EMPTY <<<'

        message = '\n\n{header}\n{log}\n{footer}\n\n'
        logger.debug(
            message.format(
                header=center_text_message(
                    'BEGIN {} VAGRANT LOGS'.format(self.name)),
                log=log,
                footer=center_text_message(
                    'END {} VAGRANT LOGS'.format(self.name)),
            )
        )


class UpgradedPipelineMixin(object):
    ENV = {
        'KD_INSTALL_TYPE': 'release',
        # TODO: Remove ippool tag as soon as create-ip-pool manage.py
        # command is updated in release
        'KD_DEPLOY_SKIP': 'predefined_apps,cleanup,ui_patch,ippool,route',
        'KD_LICENSE': '../../../../../../tests_integration/assets/fake_license.json',
    }

    def post_create_hook(self):
        super(UpgradedPipelineMixin, self).post_create_hook()
        try:
            self.cluster.upgrade('/tmp/prebuilt_rpms/kuberdock.rpm',
                                 use_testing=True, skip_healthcheck=True)
        except NonZeroRetCodeException:
            raise ClusterUpgradeError('Could not upgrade cluster')
        # TODO: This is needed because we skip IP pool creation during
        # vagrant provisioning. See TODO in the ENV
        self.cluster.recreate_routable_ip_pool()
