import functools

from multiprocessing import pool, TimeoutError

from tests_integration.lib.exceptions import KDIsNotSane

NORMAL_API_RESPONCE_TIMEOUT = 2
REQUESTS_ACCEPTABLE_FAILURES = 0.05  # 5% of requests can be slower than timeout
REQUESTS_BATCH_SIZE = 100


def run_with_timeout(timeout):
    """ Raises a TimeoutError if execution exceeds timeout
    """
    def decorator(clbl):

        stat = {'name': clbl.__name__, 'overall': 0, 'failed': 0}

        @functools.wraps(clbl)
        def wrapper(*args, **kwargs):
            stat['overall'] += 1
            p = pool.ThreadPool(processes=1)
            async_result = p.apply_async(clbl, args, kwargs)
            try:
                return async_result.get(timeout)
            except TimeoutError as err:
                stat['failed'] += 1
                if stat['overall'] > REQUESTS_BATCH_SIZE:
                    request_failures = float(stat['failed']) / stat['overall']
                    if request_failures > REQUESTS_ACCEPTABLE_FAILURES:
                        raise KDIsNotSane(
                            "Callable {0} overcome acceptable requests failure"
                            " limit.\nStats:\n{1}. Reasons of request"
                            " failures:\n{2}".format(
                                stat['name'], stat, repr(err)))
                    stat['overall'], stat['fails'] = 0, 0
        return wrapper
    return decorator


@run_with_timeout(NORMAL_API_RESPONCE_TIMEOUT)
def check_nodes(cluster):
    cluster.kdctl("nodes list")


@run_with_timeout(NORMAL_API_RESPONCE_TIMEOUT)
def check_pod(pod):
    pod.healthcheck()


@run_with_timeout(NORMAL_API_RESPONCE_TIMEOUT)
def check_pod_stats(pod):
    pod.get_stat()
    for container in pod.containers:
        pod.get_container_stat(container['name'])


@run_with_timeout(NORMAL_API_RESPONCE_TIMEOUT)
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
