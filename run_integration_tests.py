import fnmatch
import os
import random
import sys
import logging
import threading
import traceback
import imp
import time
import click
from collections import defaultdict
from contextlib import closing
from threading import Thread

from colorama import Fore, Style
from pygments import highlight
from pygments.formatters.terminal256 import Terminal256Formatter
from pygments.lexers.python import PythonLexer

from tests_integration.lib import multilogger
from tests_integration.lib.pipelines import pipelines as \
    registered_pipelines, Pipeline

CLUSTER_CREATION_MAX_DELAY = 30
INTEGRATION_TESTS_PATH = 'tests_integration/'
# Lock is needed for printing info thread-safely and it's done by two
# separate print calls
print_lock = threading.Lock()
# Not the best way of determining that any error occurred in tests
integration_tests_failed = False

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def print_msg(msg, color=Fore.MAGENTA):
    print('\n{}{}{}'.format(color, msg, Style.RESET_ALL))
    sys.stdout.flush()


def print_exception(exc_info):
    # TODO: Probably include the context/source code caused the exception
    trace = ''.join(traceback.format_exception(*exc_info))
    message = highlight_code(trace)
    print_msg(message, color='')


def highlight_code(code):
    """
    Returns highlighted via pygments version of a given source code

    :param code: string containing a source code
    :return: colorized string
    """
    return highlight(code, PythonLexer(), Terminal256Formatter(style='manni'))


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

    message = 'Discovered tests in:\n{}'.format('\n'.join(discovered))
    print_msg(message)


def run_tests_in_a_pipeline(name, tests):
    """
    :param name: pipeline name
    :param tests: list of callables
    """

    # Just a helper function to make code less verbose
    def pipe_log(msg, color=Fore.MAGENTA):
        print_msg('{} -> {}'.format(name, msg), color)

    pipe_log('CREATING CLUSTER', Fore.MAGENTA)

    try:
        pipeline = Pipeline.from_name(name)

        # AC-3914 prevent Nebula from being flooded with requests
        sleep_seconds = random.randint(0, CLUSTER_CREATION_MAX_DELAY)
        pipe_log('Sleeping for {} seconds'.format(sleep_seconds))
        time.sleep(sleep_seconds)

        pipeline.create()
        pipe_log('CLUSTER CREATED', Fore.GREEN)
    except:
        register_test_failure()
        with print_lock:
            pipe_log('CLUSTER CREATION FAILED', Fore.RED)
            exc_info = sys.exc_info()
            print_exception(exc_info)
        return

    results = defaultdict(list)
    for test in tests:
        test_name = '{}::{}'.format(test.__module__, test.__name__)
        pipe_log('{} -> STARTED'.format(test_name))
        try:
            pipeline.run_test(test)
            pipe_log('{} -> PASSED'.format(test_name), Fore.GREEN)
            results['passed'].append(test_name)
        except:
            register_test_failure()
            with print_lock:
                pipe_log('{} -> FAILED'.format(test_name), Fore.RED)
                exc_info = sys.exc_info()
                print_exception(exc_info)
            results['failed'].append(test_name)

    pipeline.destroy()
    print_tests_summary(name, results)


def print_tests_summary(name, results):
    # TODO: Maybe add some more sophisticated reporting
    failed, passed = len(results['failed']), len(results['passed'])
    print_msg('{} -> TEST RESULTS: {} failed, {} passed'.format(
        name, failed, passed))


def register_test_failure():
    global integration_tests_failed
    integration_tests_failed = True


def start_test(pipeline, tests):
    """
    Create a thread which creates a pipeline and starts executing tests in it
    :param pipeline: tuple (name, thread)
    :param tests: a list of callables
    :return: created Thread object
    """

    full_name = '{}_{}'.format(*pipeline)
    t = Thread(
        name=full_name, target=run_tests_in_a_pipeline,
        args=(full_name, tests))
    t.start()
    return t


def print_pipeline_logs(handler):
    """
    Prints logs generated by each pipeline
    :param handler: logger handler instance
    """
    with print_lock:
        print_msg('{:=^100}'.format(' PIPELINE DETAILED LOGS '))
        for name, fp in handler.files.items():
            fp.seek(0)
            print_msg('{:-^50}'.format(' ' + name + ' '))
            print(fp.read())


def _verify_paths(ctx, param, items):
    bad_paths = [i for i in items if not os.path.exists(i)]
    if bad_paths:
        message = 'could not find following paths:\n{}'.format('\n'.join(
            bad_paths))
        raise click.BadArgumentUsage(message)
    return items


def _verify_pipelines(ctx, param, items):
    if not items:
        return []
    return items.split(',')


@click.command()
@click.argument('paths', nargs=-1, callback=_verify_paths)
@click.option('--pipelines', callback=_verify_pipelines)
def main(paths, pipelines):
    with closing(multilogger.init_handler(logger)) as handler:
        discover_integration_tests(paths or [INTEGRATION_TESTS_PATH])

        if not pipelines:
            requested = registered_pipelines
        else:
            requested = {
                k: v
                for k, v in registered_pipelines.items() if k[0] in pipelines}

        threads = [
            start_test(pipe, tests) for pipe, tests in requested.items()
            ]

        for t in threads:
            t.join()

        print_pipeline_logs(handler)

        if integration_tests_failed:
            sys.exit(1)


if __name__ == "__main__":
    main()
