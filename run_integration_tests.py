
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import logging
import os
import sys
import math
import threading
import traceback
from contextlib import closing
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import current_thread

import click
import requests
from colorama import Fore

from tests_integration.lib import multilogger
from tests_integration.lib.test_runner import \
    TestResultCollection, discover_integration_tests, write_junit_xml
from tests_integration.lib.utils import get_func_fqn, center_text_message, \
    force_unicode
from tests_integration.lib.pipelines import pipelines as registered_pipelines
from tests_integration.lib.pipelines import infra_provider_slots
from tests_integration.lib.pipelines_base import Pipeline
from tests_integration.lib.timing import timing_ctx

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
    current_thread().name = pipeline_name  # required for multilog

    # Helper functions to make code less verbose
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
    try:
        pipeline = Pipeline.from_name(pipeline_name)
    except Exception as e:
        pipe_log("Failed to run Pipeline.from_name({})".format(
            pipeline_name))
        pipe_log('{}'.format(
            ''.join(traceback.format_exception(*sys.exc_info()))
        ))
        raise
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


def _filter_by_infra_provider(pipelines, infra_provider):
    """
    Filters out pipelines which do not match a given infra provider.

    :param pipelines: a dict of pipelines to filter
    :param infra_provider: str - name of the infra provider
    :return: dictionary of pipelines
    """
    return {
        k: v
        for k, v in pipelines.items() if
        Pipeline.class_from_name("{}_{}".format(*k)
                                 ).INFRA_PROVIDER == infra_provider
        }


def _filter_by_pipeline_tags(pipelines, tags):
    """
    Filters out pipelines that do not have tags intersected with
    requested tags.

    :param pipelines: a dict of pipelines to filter
    :param tags: list of str - requested tags
    :return: dictionary of pipelines
    """
    tags = set(tags)
    return {
        k: v
        for k, v in pipelines.items() if
        set(Pipeline.class_from_name("{}_{}".format(*k)).tags) & tags
        }


def _filter_by_include_exclude(pipelines, include, exclude):
    """
    Filters basing on given include/exclude lists.

    :param pipelines: a dict of pipelines to filter
    :param include: a list of pipeline names to include
    :param exclude: a list of pipeline names to exclude
    :return: dictionary of pipelines
    """
    if not include and not exclude:
        return pipelines

    if not include:
        # If include is empty - we are in "exclude" mode. Include all.
        include = [p for (p, _) in pipelines]

    return {k: v
            for k, v in pipelines.items() if
            k[0] in include and
            k[0] not in exclude}


def _filter_by_test_name(pipelines, test_name):
    """
    Shrinks given pipelines so that they have only a single test inside.

    :param pipelines: a dict of pipelines to filter
    :param test_name: name of the test to remain in pipelines
    :return: dictionary of pipelines
    """
    if not test_name:
        # --all-tests
        return pipelines

    filtered = {}
    for pipe, tests in pipelines.items():
        for test in tests:
            if test.__name__ == test_name:
                filtered[pipe] = [test]
    if not filtered:
        raise click.BadArgumentUsage('Test "{}" not found'.format(test_name))
    return filtered


def _verify_paths(ctx, param, items):
    bad_paths = [i for i in items if not os.path.exists(i)]
    if bad_paths:
        message = u'could not find following paths:\n{}'.format('\n'.join(
            bad_paths))
        raise click.BadArgumentUsage(message)
    return items


def _comma_sep_str_to_list(ctx, param, items):
    if not items:
        return []
    return [i.strip() for i in items.split(',')]


@click.command(context_settings={'help_option_names': ['-h', '--help']})
@click.argument('paths', nargs=-1, callback=_verify_paths)
@click.option('--pipelines', callback=_comma_sep_str_to_list,
              help='Comma separated pipeline names to run.')
@click.option('--pipelines-skip', callback=_comma_sep_str_to_list,
              help='Comma separated pipeline names to skip. Cannot be used '
                   'with --pipelines.')
@click.option('--pipeline-tags', callback=_comma_sep_str_to_list,
              help='Comma separated pipeline tags to run. Takes effect only '
                   'if pipelines are not specified explicitly via --pipelines',
              default='general')
@click.option('--infra-provider', type=str, default='opennebula',
              help='Which infra provider to use. Options are: '
                   '"opennebula" (default); "aws"')
@click.option('--live-log', is_flag=True,
              help='Instantly print test logs to the console')
@click.option('--all-tests', is_flag=True, help='Grab all available tests')
@click.option('--cluster-debug', is_flag=True, default=False,
              help='Enable debug mode. Currently this does not destroy a '
                   'cluster if any of its tests failed.')
@click.option('--junit-xml', type=click.File(mode='w'))
@click.option('--test', type=str, help='A name of a test to run')
def main(paths, pipelines, pipelines_skip, pipeline_tags, infra_provider,
         live_log, all_tests, cluster_debug, junit_xml, test):
    if bool(all_tests) == bool(test):
        raise click.BadOptionUsage(
            'Should specify either --test NAME or --all-tests')

    if bool(pipelines) and bool(pipelines_skip):
        raise click.BadOptionUsage(
            'Can not use both --pipelines and --pipelines-skip')

    if cluster_debug and (infra_provider == 'aws'):
        # FIXME in AC-5210
        raise click.BadOptionUsage(
            'AWS does not have an automatic cleaner thus debug is forbidden.'
        )

    with closing(multilogger.init_handler(logger, live_log)) as multilog:
        discovered = discover_integration_tests(
            paths or [INTEGRATION_TESTS_PATH])

        print_msg(u'Discovered tests in:\n{}\n'.format('\n'.join(discovered)))

        filtered = _filter_by_infra_provider(registered_pipelines,
                                             infra_provider)
        if not pipelines:
            # Take effect only if pipelines to run are not set explicitly.
            filtered = _filter_by_pipeline_tags(filtered, pipeline_tags)
        filtered = _filter_by_include_exclude(filtered, pipelines,
                                              pipelines_skip)
        filtered = _filter_by_test_name(filtered, test)

        if os.environ.get('BUILD_CLUSTER') != '1' and len(filtered) > 1:
            sys.exit('Can not run multiple pipelines without BUILD_CLUSTER')

        slots = infra_provider_slots[infra_provider]
        print_msg(u'Requested pipelines: {}'.format(len(filtered)))
        print_msg(u'Infra provider "{}" slots: {}'.format(infra_provider,
                                                          slots))
        q_len = int(math.ceil(len(filtered) / float(slots)))
        if q_len > 1:
            print_msg(u'Pipelines will be queued into slots.')
            print_msg(u'Estimated longest queue: {} pipelines'.format(q_len))

        with ThreadPoolExecutor(max_workers=slots) as executor:
            for pipe, tests in filtered.items():
                full_name = u'{}_{}'.format(*pipe)
                executor.submit(run_tests_in_a_pipeline,
                                full_name, tests, cluster_debug)

        _print_logs(multilog, live_log)

        if junit_xml:
            write_junit_xml(junit_xml, test_results)

        if test_results.has_any_failures():
            sys.exit(1)


if __name__ == "__main__":
    main()
