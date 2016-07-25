import fnmatch
import imp
import os
import traceback
from collections import namedtuple, Counter
from operator import attrgetter

from colorama import Fore
from pygments import highlight
from pygments.formatters.terminal256 import Terminal256Formatter
from pygments.lexers.python import PythonLexer

from tests_integration.lib.integration_test_utils import get_test_full_name, \
    center_text_message


class TestResultCollection(object):
    """
    Represents a container for collecting results of each test run
    """

    # Test result's status types:
    # 1. passed - test completed successfully
    # 2. failed - test gracefully failed
    # 3. pipeline_error - some unexpected error occurred during test execution
    TestResult = namedtuple('TestResult', 'name status pipeline')

    def __init__(self):
        self._results = []

    def register_failure(self, test, pipeline):
        # type: (str, str) -> None
        """
        Adds a test to the collection and marks it as a failed one
        """
        self._results.append(self.TestResult(test, 'failed', pipeline))

    def register_success(self, test, pipeline):
        # type: (str, str) -> None
        """
        Adds a test to the collection and marks it as a passed one
        """
        self._results.append(self.TestResult(test, 'passed', pipeline))

    def register_pipeline_error(self, pipeline, tests):
        # type: (str, list) -> None
        """
        Adds given tests to the collection and marks them as failed
        """
        test_names = (get_test_full_name(test) for test in tests)
        results = (
            self.TestResult(t, 'pipeline_error', pipeline) for t in test_names)

        self._results.extend(results)

    def pipeline_test_summary(self, name):
        # type: (str) -> str
        """
        Returns a string containing tests summary of a pipeline
        :param name: pipeline name
        :return: pipeline report
        """
        c = Counter(r.status for r in self._results if r.pipeline == name)
        failed, passed = c['failed'], c['passed']
        return '{} -> TEST RESULTS: {} failed, {} passed'.format(
            name, failed, passed)

    def has_any_failures(self, pipeline=None):
        # type: (str) -> bool
        """
        Indicates if a result collection has any failed test. Optionally can be
        filtered by a full pipeline name

        :param pipeline: optional full name of a pipeline to check
        :return: True of there is any failed test, False otherwise
        """

        results = self._results
        if pipeline is not None:
            results = (r for r in results if r.pipeline == pipeline)
        return any(r.status in ['pipeline_error', 'failed'] for r in results)

    def get_tests_report(self):
        """
        Returns a formatted report which contains information about all tests
        """

        def _make_report_entry(test):
            color = self._color_from_status(test.status)
            return '{} {} {}{}{}'.format(
                test.pipeline, test.name, color, test.status.upper(),
                Fore.RESET)

        results = sorted(self._results, key=attrgetter('pipeline'))
        entries = (_make_report_entry(t) for t in results)
        return center_text_message('TESTS SUMMARY') + '\n' + '\n'.join(entries)

    def _color_from_status(self, status):
        mapping = {
            'failed': Fore.RED,
            'passed': Fore.GREEN,
            'pipeline_error': Fore.RED
        }
        return mapping[status]


def discover_integration_tests(paths, mask='test_*.py'):
    """
    Tests are located in python files. Each test has a pipeline decorator
    which registers a test when the source code is parsed (imported). So
    this method goes through files given a mask and imports them thus
    triggering the test registration. Will be used later control which tests
    to execute

    :param paths: a path or a list of paths. If path is a directory then
        it's walked recursively
    :param mask: filename mask which is used to determine if it's a test file
    """

    discovered = []

    def process_file(path):
        filename = os.path.basename(path)
        imp.load_source(os.path.splitext(filename)[0], path)
        discovered.append(path)

    def process_dir(path):
        for root, _, file_names in os.walk(path):
            for filename in fnmatch.filter(file_names, mask):
                name = os.path.join(root, filename)
                imp.load_source(os.path.splitext(filename)[0], name)
                discovered.append(name)

    for path in paths:
        if os.path.isdir(path):
            process_dir(path)
        elif os.path.isfile(path):
            process_file(path)

    return discovered


def format_exception(exc_info):
    # TODO: Probably include the context/source code caused the exception
    trace = ''.join(traceback.format_exception(*exc_info))
    message = highlight_code(trace)
    return message


def highlight_code(code):
    """
    Returns highlighted via pygments version of a given source code

    :param code: string containing a source code
    :return: colorized string
    """
    return highlight(code, PythonLexer(), Terminal256Formatter(style='manni'))
