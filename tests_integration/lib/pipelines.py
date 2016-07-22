import logging
import os
from collections import defaultdict
from contextlib import contextmanager
from functools import wraps
from tempfile import NamedTemporaryFile

from tests_integration.lib.exceptions import PipelineNotFound
from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.integration_test_utils import merge_dicts, \
    center_text_message, NebulaIPPool, suppress

PIPELINES_PATH = '.pipelines/'
INTEGRATION_TESTS_VNET = 'vlan_kuberdock_ci'
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
        self.defaults = {
            'KD_MASTER_CPUS': '2',
            'KD_MASTER_MEMORY': '4096',
            'KD_NODES_COUNT': '2',
            'KD_NODE_MEMORY': '3048',
            'KD_LICENSE': 'patch',
            'KD_TESTING_REPO': 'true',
            'KD_DEPLOY_SKIP': 'predefined_apps,cleanup,ui_patch',
        }
        self.name = name
        self.settings = merge_dicts(self.defaults, getattr(self, 'ENV', {}))
        self.settings['VAGRANT_DOTFILE_PATH'] = os.path.join(
            PIPELINES_PATH, self.name)
        self.routable_ip_count = getattr(self, 'ROUTABLE_IP_COUNT', 0)
        self.vagrant_log = NamedTemporaryFile(delete=False)

        self.routable_ip_pool = NebulaIPPool.factory(
            os.environ['KD_ONE_URL'],
            os.environ['KD_ONE_USERNAME'],
            os.environ['KD_ONE_PASSWORD'])
        self.cluster = None

    def run_test(self, test):
        """
        Runs a given test executing set_up/tear_down before/after a test

        :param test: a callable which represents a test and accepts one a
            KDIntegrationAPI object as a first argument
        """
        test_name = '{}::{}'.format(test.__module__, test.__name__)
        logger.debug(center_text_message('{} START'.format(test_name)))
        self.set_up()
        try:
            test(self.cluster)
        finally:
            self.tear_down()
            logger.debug(center_text_message('{} END'.format(test_name)))

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

        try:
            # Reserve Pod IPs in Nebula so that they are not taken by otherVMs/Pods
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
        with suppress():
            self.routable_ip_pool.free_reserved_ips()
        with suppress():
            self.cluster.destroy()

    def set_up(self):
        """
        Perform a set up for test before running it. Be default it performs a
        cluster cleanup
        """
        self.cleanup()
        self.cluster.preload_docker_image('nginx:latest')

    def tear_down(self):
        """
        Runs right after a test even if it failed or raised an exception. By
        default does nothing
        """
        pass

    @classmethod
    def from_name(cls, name):
        """
        Fabric method for creating a specific pipeline class instance
        depending on a given name
        """
        available = {c.NAME: c for c in cls.__subclasses__()}
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

        # KD_ONE_PUB_IPS is a list of last IP octets
        kd_pub_ips = ','.join(i.split('.')[-1] for i in ip_list)
        self.settings['KD_ONE_PUB_IPS'] = kd_pub_ips

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


class MainPipeline(Pipeline):
    NAME = 'main'
    ROUTABLE_IP_COUNT = 1
    ENV = {
        'KD_NODES_COUNT': '1',
    }


class NetworkingPipeline(Pipeline):
    NAME = 'networking'
    ROUTABLE_IP_COUNT = 2
    ENV = {
        # TODO: AC-3584 When the isolation rules are fixed so pods on
        # different nodes correctly communicate with each other raise that
        # number to 2
        'KD_NODES_COUNT': '1',
    }

    def set_up(self):
        super(NetworkingPipeline, self).set_up()
        self.cluster.recreate_routable_ip_pool()


class NonfloatingPipeline(Pipeline):
    NAME = 'nonfloating'
    ROUTABLE_IP_COUNT = 3
    ENV = {
        'KD_NONFLOATING_PUBLIC_IPS': 'true',
        'KD_NODES_COUNT': '2',
    }

    def cleanup(self):
        super(NonfloatingPipeline, self).cleanup()
        self.cluster.delete_all_ip_pools()


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


class KubeTypePipeline(Pipeline):
    NAME = 'kubetype'
    ROUTABLE_IP_COUNT = 2
    ENV = {
        'KD_NODES_COUNT': '2',
        'KD_NODE_TYPES': 'node1=standard,node2=tiny'
    }


class FailConditionsPipeline(Pipeline):
    NAME = 'fail_conditions'
    ROUTABLE_IP_COUNT = 1
    ENV = {
        'KD_NODES_COUNT': '1',
    }


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
