import logging
import functools
import random
import itertools

from multiprocessing import pool, TimeoutError
from threading import current_thread, Thread
from time import sleep
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from tests_integration.lib.exceptions import KDIsNotSane
from tests_integration.lib.utils import loglevel
from tests_integration.lib.exceptions import StatusWaitException

LOG = logging.getLogger(__name__)
NORMAL_API_RESPONCE_TIMEOUT = 2
REQUESTS_ACCEPTABLE_FAILURES = 0.05  # 5% of requests can be slower than timeout
REQUESTS_BATCH_SIZE = 100


def mild(batch_size=REQUESTS_BATCH_SIZE,
         acceptable=REQUESTS_ACCEPTABLE_FAILURES):
    """ This decorator passes timeout errors until `acceptable`
    portion of calls (batch_size) not exceeded.
    """

    def decorator(clbl):

        stat = {'name': clbl.__name__, 'overall': 0, 'failed': 0}

        @functools.wraps(clbl)
        def wrapper(*args, **kwargs):
            stat['overall'] += 1
            try:
                clbl(*args, **kwargs)
            except (TimeoutError, KDIsNotSane) as err:
                stat['failed'] += 1
                if stat['overall'] > batch_size:
                    request_failures = float(stat['failed']) / stat['overall']
                    if request_failures > acceptable:
                        raise KDIsNotSane(
                            "Callable {0} overcome acceptable requests failure"
                            " limit.\nStats:\n{1}. Reasons of request"
                            " failures:\n{2}".format(
                                stat['name'], stat, repr(err)))
                    stat['overall'], stat['fails'] = 0, 0
        return wrapper
    return decorator


def run_with_timeout(timeout=NORMAL_API_RESPONCE_TIMEOUT):
    """ Raises a TimeoutError if execution exceeds timeout
    """
    def decorator(clbl):

        @functools.wraps(clbl)
        def wrapper(*args, **kwargs):
            p = pool.ThreadPool(processes=1)
            async_result = p.apply_async(clbl, args, kwargs)
            try:
                return async_result.get(timeout)
            finally:
                p.terminate()

        return wrapper
    return decorator


@mild()
@run_with_timeout()
def check_nodes(cluster):
    cluster.kdctl("nodes list")


@mild()
@run_with_timeout()
def check_pod(pod):
    pod.healthcheck()


@mild()
@run_with_timeout()
def check_pod_stats(pod):
    pod.get_stat()


@mild()
@run_with_timeout()
def check_pod_container_stats(pod):
    for container in pod.containers:
        pod.get_container_stat(container['name'])


@mild()
@run_with_timeout()
def check_node_stats(cluster):
    for node_data in cluster.nodes.get_list():
        node = cluster.nodes.get_node(node_data['hostname'])
        node.get_stat()


def check_sanity(cluster, pods):
    """ Check that KD is responce in appropriate time
    """
    check_nodes(cluster)
    cluster.login_to_kcli2("admin")
    check_node_stats(cluster)
    cluster.login_to_kcli2("test_user")
    for pod in pods:
        check_pod(pod)
        check_pod_stats(pod)
        check_pod_container_stats(pod)


def _gen_one_request(delay, _pod):
    current_thread().name = "load_testing_pods_workload"
    sleep(delay)
    try:
        _pod.do_GET(exp_retcodes=[200], fetch_subres=True, verbose=False)
    except Exception as e:
        LOG.debug("Pod '{}' GET error: {}".format(_pod.pod_id, repr(e)))


@contextmanager
def gen_workload(pods, loaded_pods_num, req_per_sec):
    # can be optimized through subprocess.Popen load.py + gevent inside
    executor = ThreadPoolExecutor(max_workers=50)

    def _gen_requests():
        while True:
            # Choose N random pods to be loaded this second.
            pods_to_load = random.sample(pods, loaded_pods_num)
            # Schedule this second requests. Each of them starts at random
            # point of this second.
            for pod in pods_to_load:
                for _ in range(req_per_sec):
                    try:
                        executor.submit(_gen_one_request,
                                        random.uniform(0, 1.0), pod)
                    except RuntimeError:
                        return  # shutdown
            # Wait for the next second
            sleep(1)

    Thread(target=_gen_requests).start()
    try:
        yield
    finally:
        executor.shutdown()


def fill_with_pa(cluster, pa_name, with_healthcheck=True):
    """ Creates pods until it fits to resource restrictions.
    Returns all created pods plus one which does not fit and fails.
    """
    no_res_msg = "Node didn't have enough resource"
    pods = []
    with loglevel(logging.INFO):
        for pod_n in itertools.count():
            LOG.info("Launching pod #{}".format(pod_n))
            last_pod = cluster.pods.create_pa(
                pa_name, wait_ports=False, healthcheck=False)
            pods.append(last_pod)
            try:
                last_pod.wait_for_status('running')
                last_pod.healthcheck()
            except StatusWaitException as err:
                LOG.info("Pod isn't started: {}".format(repr(err)))
                events = (no_res_msg in e['message'] for e in last_pod.events(
                    event_type='warning',
                    event_source='component:default-scheduler',
                    event_reason='FailedScheduling'
                ))
                if any(events):
                    break
                raise
    return pods
