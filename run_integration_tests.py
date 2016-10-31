import logging
import os
import re
import sys
import threading
import traceback
from contextlib import closing
from datetime import timedelta
from threading import Thread

import click
import requests
from colorama import Fore

from tests_integration.lib import multilogger
from tests_integration.lib.integration_test_runner import \
    TestResultCollection, discover_integration_tests, write_junit_xml
from tests_integration.lib.integration_test_utils import get_func_fqn, \
    center_text_message, force_unicode
from tests_integration.lib.pipelines import pipelines as \
    registered_pipelines
from tests_integration.lib.pipelines_base import Pipeline
from tests_integration.lib.timing import timing_ctx, stopwatch

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

INTEGRATION_TESTS_PATH = 'tests_integration/'
JENKINS_GC_TIME_INTERVAL = 2  # hours
# Lock is needed for printing info thread-safely and it's done by two
# separate print calls
print_lock = threading.Lock()
test_results = TestResultCollection()
debug_messages = []


def print_msg(msg=u'', color=Fore.MAGENTA):
    """:type msg: basestring"""
    with print_lock:
        click.echo(u'{}{}{}'.format(color, force_unicode(msg), Fore.RESET),
                   color=True)
        sys.stdout.flush()


def run_tests_in_a_pipeline(pipeline_name, tests, cluster_debug=False):
    """
    :param cluster_debug: if True cluster isn't destroyed on any test
        failure
    :param pipeline_name: pipeline name
    :param tests: list of callables
    """

    # Helper function to make code less verbose
    def pipe_log(msg, color=Fore.MAGENTA):
        msg = force_unicode(msg)
        print_msg(u'{} -> {}\n'.format(pipeline_name, msg), color)

    def pass_test(t):
        test_name = get_func_fqn(t)
        test_results.register_success(t, test_time, pipeline_name)
        pipe_log(u'{} -> PASSED ({})'.format(test_name, test_time),
                 Fore.GREEN)

    def skip_test(t, reason=""):
        test_name = get_func_fqn(t)
        reason = t.meta.get('skip_reason', reason)
        test_results.register_skip(t, pipeline_name, reason)
        pipe_log(u'{} -> SKIPPED ({})'.format(test_name, reason),
                 Fore.YELLOW)

    def fail_test(t, error):
        test_name = get_func_fqn(t)
        test_results.register_failure(t, test_time, pipeline_name, error)
        pipe_log(u'{} -> FAILED ({})\n{}'.format(test_name, test_time, error),
                 Fore.RED)

    pipeline = Pipeline.from_name(pipeline_name)
    if pipeline.skip_reason:
        pipe_log('SKIPPING CLUSTER ({})'.format(pipeline.skip_reason),
                 Fore.YELLOW)
        for test in tests:
            skip_test(test, pipeline.skip_reason)
        return

    if all(t.meta.get('skip_reason') for t in tests):
        pipe_log('SKIPPING CLUSTER (has no active tests)', Fore.YELLOW)
        for test in tests:
            skip_test(test)
        return

    pipe_log('CREATING CLUSTER', Fore.MAGENTA)
    try:
        with timing_ctx() as cluster_time:
            pipeline.create()
        pipe_log('CLUSTER CREATED ({})'.format(cluster_time), Fore.GREEN)
    except Exception as e:
        msg = prettify_exception(e)
        test_results.register_pipeline_error(pipeline_name, tests, msg)
        pipe_log(u'CLUSTER CREATION FAILED ({})\n{}'.format(cluster_time, msg),
                 Fore.RED)
        return

    with timing_ctx() as all_tests_time:
        for test in tests:
            if "skip_reason" in test.meta:
                skip_test(test)
                continue
            pipe_log(u'{} -> STARTED'.format(get_func_fqn(test)))
            try:
                with timing_ctx() as test_time:
                    pipeline.run_test(test)
                pass_test(test)
            except Exception as e:
                fail_test(test, prettify_exception(e))

    if cluster_debug and test_results.has_any_failures(pipeline_name):
        add_debug_info(pipeline)
    else:
        pipeline.destroy()

    print_msg(test_results.pipeline_test_summary(pipeline_name))
    print_msg("{} Cluster time: {}; Tests time: {};".format(pipeline_name,
                                                            cluster_time,
                                                            all_tests_time))


def prettify_exception(exc):
    msg = force_unicode(str(exc))
    return u'{}: {}'.format(exc.__class__.__name__, msg)


def add_debug_info(pipeline):
    """
    Save information about when cluster is going to be destroyed by Jenkins GC
    """
    if not pipeline.build_cluster:
        return
    master_ip = pipeline.cluster.get_host_ip('master')
    msg = u'Pipeline {} has failed tests, it remains alive until about ' \
          u'{} so that you can debug it. Master IP: {}'
    destroy_time = pipeline.cluster.created_at + timedelta(
        hours=JENKINS_GC_TIME_INTERVAL)
    debug_messages.append(
        msg.format(pipeline.name, destroy_time.isoformat(' '), master_ip))


def start_test(pipeline, tests, cluster_debug):
    """
    Create a thread which creates a pipeline and starts executing tests in it
    :param pipeline: tuple (name, thread)
    :param tests: a list of callables
    :return: created Thread object
    """

    full_name = u'{}_{}'.format(*pipeline)
    t = Thread(
        name=full_name, target=run_tests_in_a_pipeline,
        args=(full_name, tests, cluster_debug))
    t.start()
    return t


def get_pipeline_logs(multilog):
    """Gets logs generated by each pipeline.

    :param multilog: logger handler instance
    """

    def _format_log(name, log):
        name, log = force_unicode(name), force_unicode(log)
        return center_text_message(name, color=Fore.MAGENTA) + '\n' + log

    entries = {
        name: _format_log(name, log)
        for name, log in multilog.grouped_by_thread.items()
        }

    try:
        url = os.environ['KD_PASTEBIN_URL']
        user = os.environ['KD_PASTEBIN_USER']
        password = os.environ['KD_PASTEBIN_PASS']

        with PastebinClient(url, user, password) as c:
            urls = (u'{}: {}'.format(n, c.post(e)) for n, e in entries.items())
            msg = '\n' + '\n'.join(urls)
    except Exception as e:
        # Fallback if pastebin isn't accessible
        msg = u'\n!!! Could not upload logs to pastebin, ' \
              u'falling back to console. Reason:\n{}\n\n{}'.format(
                    u''.join(traceback.format_exception(*sys.exc_info())),
                    u'\n'.join(entries.values())
                )

    msg = center_text_message(
        'PIPELINE DETAILED LOGS', fill_char='=', color=Fore.MAGENTA) + msg
    return msg.encode('utf-8')


class PastebinClient(object):
    def __init__(self, url, username, password):
        self.ses = requests.Session()
        self.ses.auth = (username, password)
        self.base_url = url

    def post(self, log):
        log = self._prepare_log(log)
        response = self.ses.post(self.base_url, data=log)
        return response.json()['uri'] + '/ansi'

    def _prepare_log(self, data):
        return data.encode(encoding="utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.ses.close()


def _print_logs(handler, live_log):
    # If live log was enabled all the logs were already printed
    if not live_log:
        click.echo(get_pipeline_logs(handler), color=True)
    click.echo(test_results.get_test_report(), color=True)
    if debug_messages:
        click.echo(center_text_message('Debug messages'), color=True)
        click.echo('\n'.join(debug_messages), color=True)


def _filter_test_by_name(name, pipelines):
    for pipe, tests in pipelines.items():
        for test in tests:
            if test.__name__ == name:
                return {pipe: [test]}

    raise click.BadArgumentUsage('Test "{}" was not found'.format(name))


def _filter_pipelines(include, exclude):
    """
    Filters a global list of pipelines to use given include/exclude masks
    If both arguments aren't specified - all pipelines are used
    By design can't be specify both at the same time.
    :param include: a list of pipeline names to include
    :param exclude: a list of pipeline names to exclude
    :return: dictionary of pipelines
    """
    if not include and not exclude:
        return registered_pipelines

    # If include is empty - we are in "exclude" mode
    if not include:
        include = [p for (p, _) in registered_pipelines]

    return {k: v
            for k, v in registered_pipelines.items()
            if k[0] in include and k[0] not in exclude}


def _verify_paths(ctx, param, items):
    bad_paths = [i for i in items if not os.path.exists(i)]
    if bad_paths:
        message = u'could not find following paths:\n{}'.format('\n'.join(
            bad_paths))
        raise click.BadArgumentUsage(message)
    return items


def _verify_pipelines(ctx, param, items):
    if not items:
        return []
    return [i.strip() for i in items.split(',')]


@click.command(context_settings={'help_option_names': ['-h', '--help']})
@click.argument('paths', nargs=-1, callback=_verify_paths)
@click.option('--pipelines', callback=_verify_pipelines,
              help='Comma separated pipeline names to use')
@click.option('--pipelines-skip', callback=_verify_pipelines,
              help='Comma separated pipeline names to skip')
@click.option('--live-log', is_flag=True,
              help='Instantly print test logs to the console')
@click.option('--all-tests', is_flag=True, help='Grab all available tests')
@click.option('--cluster-debug', is_flag=True, default=False,
              help='Enable debug mode. Currently this does not destroy a '
                   'cluster if any of its tests failed.')
@click.option('--junit-xml', type=click.File(mode='w'))
@click.option('--test', type=str, help='A name of a test to run')
def main(paths, pipelines, pipelines_skip, live_log, all_tests, cluster_debug,
         junit_xml, test):
    if bool(all_tests) == bool(test):
        raise click.BadOptionUsage(
            'You should specify either --test NAME or --all-tests')

    if bool(pipelines) and bool(pipelines_skip):
        raise click.BadOptionUsage(
            'You can not use both --pipelines and --pipelines-skip')

    with closing(multilogger.init_handler(logger, live_log)) as multilog:
        discovered = discover_integration_tests(
            paths or [INTEGRATION_TESTS_PATH])

        message = u'Discovered tests in:\n{}\n'.format('\n'.join(discovered))
        print_msg(message)

        requested_pipelines = _filter_pipelines(pipelines, pipelines_skip)

        if test:
            requested_pipelines = _filter_test_by_name(
                test, requested_pipelines)

        if not os.environ.get('BUILD_CLUSTER') and len(
                requested_pipelines) > 1:
            sys.exit('Can not run multiple pipelines with unset BUILD_CLUSTER')

        threads = [
            start_test(pipe, tests, cluster_debug)
            for pipe, tests in requested_pipelines.items()]

        for t in threads:
            t.join()

        _print_logs(multilog, live_log)

        if junit_xml:
            write_junit_xml(junit_xml, test_results)

        if test_results.has_any_failures():
            sys.exit(1)


if __name__ == "__main__":
    main()
