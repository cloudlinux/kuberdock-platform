import fnmatch
import imp
import os
import traceback
from collections import namedtuple, Counter
from itertools import groupby
from operator import attrgetter

from colorama import Fore
from junit_xml import TestCase, TestSuite
from pygments import highlight
from pygments.formatters.terminal256 import Terminal256Formatter
from pygments.lexers.python import PythonTracebackLexer

from tests_integration.lib.integration_test_utils import center_text_message
from tests_integration.lib.timing import ElapsedTime


class TestResultCollection(object):
    """
    Represents a container for collecting results of each test run
    """

    # Test result's status types:
    # 1. passed - test completed successfully
    # 2. failed - test gracefully failed
    # 3. pipeline_error - some unexpected error occurred during test execution
    TestResult = namedtuple(
        'TestResult',
        'pipeline module name status elapsed_time error_message'
    )

    def __init__(self):
        self._results = []

    def register_failure(self, test, elapsed_time, pipeline,
                         error_message=None):
        # type: (function, ElapsedTime, str, unicode) -> None
        """
        Adds a test to the collection and marks it as a failed one
        """
        self._results.append(
            self._make_test_result(pipeline, test, 'failed', elapsed_time,
                                   error_message))

    def register_success(self, test, elapsed_time, pipeline):
        # type: (function, ElapsedTime, str) -> None
        """
        Adds a test to the collection and marks it as a passed one
        """
        self._results.append(self._make_test_result(pipeline, test, 'passed',
                                                    elapsed_time))

    def register_skip(self, test, pipeline, msg):
        # type: (function, str, unicode) -> None
        """
        Adds a test to the collection and marks it as a skipped one
        """
        self._results.append(self._make_test_result(pipeline, test, 'skipped',
                                                    error_message=msg))

    def register_pipeline_error(self, pipeline, tests, error_message=None):
        # type: (str, list, unicode) -> None
        """
        Adds given tests to the collection and marks them as failed
        """
        results = (
            self._make_test_result(
                pipeline, t, 'pipeline_error', error_message=error_message)
            for t in tests
        )
        self._results.extend(results)

    def pipeline_test_summary(self, name):
        # type: (str) -> str
        """
        Returns a string containing tests summary of a pipeline
        :param name: pipeline name
        :return: pipeline report
        """
        c = Counter(r.status for r in self._results if r.pipeline == name)
        failed, skipped, passed = c['failed'], c['skipped'], c['passed']
        return '{} -> TEST RESULTS: {} failed, {} skipped, {} passed'.format(
            name, failed, skipped, passed)

    def get_test_report(self):
        """
        Returns a formatted report which contains information about all tests
        """

        def _short_err_msg(msg):
            if len(msg) > 100:
                msg = "{}...".format(msg[:100])
            msg = msg.replace("\n", " ")
            return msg

        def _make_report_entry(test):
            color = self._color_from_status(test.status)
            err_msg = '({})'.format(_short_err_msg(test.error_message)) if \
                test.error_message else ''
            elapsed = ' ({})'.format(test.elapsed_time) if \
                test.elapsed_time else ''
            return '{} {} {}{}{} {}{}'.format(
                test.pipeline, test.name, color, test.status.upper(),
                elapsed, err_msg, Fore.RESET)

        results = sorted(self._results, key=attrgetter('pipeline'))
        entries = (_make_report_entry(t) for t in results)
        return center_text_message('TESTS SUMMARY') + '\n' + '\n'.join(entries)

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

    @property
    def grouped_by_pipeline(self):
        key = attrgetter('pipeline')
        results = sorted(self, key=key)
        return {g: list(t) for g, t in groupby(results, key=key)}

    def _color_from_status(self, status):
        mapping = {
            'failed': Fore.RED,
            'skipped': Fore.YELLOW,
            'passed': Fore.GREEN,
            'pipeline_error': Fore.RED
        }
        return mapping[status]

    def __iter__(self):
        for r in self._results:
            yield r

    def _make_test_result(self, pipeline, test, result, elapsed_time=None,
                          error_message=None):
        # type: (str, function, str, ElapsedTime, unicode) -> TestResult
        return self.TestResult(
            pipeline, test.__module__, test.__name__, result, elapsed_time,
            error_message
        )


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
    return highlight(code, PythonTracebackLexer(),
                     Terminal256Formatter(style='manni'))


def write_junit_xml(fp, results):
    """
    Writes results in a jUnit XML report form to a given file object
    :param fp: file-like object
    :param results: TestResults object
    """

    def make_test_suite(pipeline, results):
        def make_test_case(r):
            case = TestCase(r.name, '{}.{}'.format(pipeline, r.module))
            if r.status == 'failed':
                case.add_failure_info('Test failed', output=r.error_message)
            elif r.status == 'skipped':
                case.add_skipped_info('Test skipped', output=r.error_message)
            elif r.status == 'pipeline_error':
                case.add_error_info('Failed to create a pipeline',
                                    output=r.error_message)
            if r.elapsed_time:
                case.elapsed_sec = r.elapsed_time.int
            return case

        return TestSuite(pipeline, [make_test_case(r) for r in results])

    with fp.open() as f:
        suites = [
            make_test_suite(pipeline, results)
            for pipeline, results in results.grouped_by_pipeline.items()
            ]

        TestSuite.to_file(f, suites)
