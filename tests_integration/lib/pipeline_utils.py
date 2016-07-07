import logging
import os
from collections import defaultdict
from contextlib import contextmanager
from functools import wraps
from tempfile import NamedTemporaryFile

from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.integration_test_utils import merge_dicts, \
    center_text_message

PIPELINES_PATH = '.pipelines/'
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


class PipelineNotFound(Exception):
    pass


class PipelineInvalidName(Exception):
    pass


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

        self.vagrant_log = NamedTemporaryFile(delete=False)

        @contextmanager
        def cm():
            """
            Vagrant uses subprocess.check_call to execute each command.
            Thus we need a context manager which will catch it's stdout/stderr
            output and save it somewhere we can access it later
            """
            yield self.vagrant_log

        self.cluster = KDIntegrationTestAPI(override_envs=self.settings,
                                            err_cm=cm, out_cm=cm)

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
        try:
            self.cluster.start()
        except:
            self.destroy()
            raise

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
        try:
            self.cluster.destroy()
        except:
            pass
        finally:
            self._print_vagrant_log()

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
        try:
            available = {c.NAME: c for c in cls.__subclasses__()}
            return available[name.split('_')[0]](name)
        except KeyError:
            raise PipelineNotFound(name)

    def _print_vagrant_log(self):
        """
        Sends logs produced by vagrant to the default logger
        """
        self.vagrant_log.seek(0)
        log = self.vagrant_log.read() or '>>> EMPTY <<<'

        logger.debug(
            '\n-----------------> {name} VAGRANT LOGS ----------------->\n'
            '{log}'
            '\n<----------------- {name} VAGRANT LOGS <-----------------\n'
            .format(name=self.name, log=log)
        )


class MainPipeline(Pipeline):
    NAME = 'main'
    ENV = {
        'KD_NODES_COUNT': '1',
    }


class NetworkingPipeline(Pipeline):
    NAME = 'networking'
    ENV = {
        'KD_NODES_COUNT': '1',
    }


class NonfloatingPipeline(Pipeline):
    NAME = 'nonfloating'
    ENV = {
        'KD_NONFLOATING_PUBLIC_IPS': 'true',
        'KD_NODES_COUNT': '2',
    }

    def cleanup(self):
        super(NonfloatingPipeline, self).cleanup()
        self.cluster.delete_all_ip_pools()


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
