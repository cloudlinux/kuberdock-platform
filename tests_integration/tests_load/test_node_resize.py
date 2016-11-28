import time
import logging

from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.infra_providers import InstanceSize
from tests_integration.lib.exceptions import StatusWaitException
from tests_integration.lib.utils import log_debug, log_info, assert_eq


LOG = logging.getLogger(__name__)


@pipeline('load_testing_node_resize')
@pipeline('load_testing_node_resize_aws')
def test_fill_node_and_resize(cluster):

    node1 = cluster.nodes.get_node('node1')
    node1.wait_for_status("running", tries=24, interval=5)
    time.sleep(20)  # Workaround for AC-5403
    pods = _try_fill_node(cluster, 'nginx', prefix="before_resize_")
    log_info("Created {} pods".format(len(pods)))
    log_info("Resizing {} node to Large instance".format(node1.name))
    log_debug(node1.info)
    node1.resize(InstanceSize.Large)
    log_info(node1.info)
    _wait_pods_status(pods, status='running')
    pods2 = _try_fill_node(cluster, 'nginx', prefix="after_resize_")
    log_info("Created {} pods".format(len(pods2)))
    _wait_pods_status(pods2, status='running')
    log_debug("Pods before resize - {}".format([p.name for p in pods]))
    log_debug("Pods after resize - {}".format([p.name for p in pods2]))
    assert_eq(len(pods2) >= len(pods), True)


def _wait_pods_status(pods, status, timeout=300, interval=5, delay=0):
    _pods = pods[:]
    time.sleep(delay)
    end = time.time() + timeout
    while time.time() < end:
        for obj in _pods:
            st = obj.status
            log_debug(
                "Status: '{}', waiting for status: '{}'".format(
                    st, status), LOG)

            if st == status:
                _pods.remove(obj)
                log_debug("Pods '{}' still are not in {} state".format(
                    sorted([p.name for p in _pods]), status))
            time.sleep(interval)
        if len(_pods) == 0:
            return True
    raise StatusWaitException(expected=status, actual=st,
                              timeout=delay + timeout)


def _try_fill_node(cluster, name, prefix=None, max_pods=500):
    pods = []
    for _ in range(max_pods):
        log_debug("Trying to create Pod {} #{} ".format(name, _))
        pod = cluster.pods.create(image=name, kubes=4, name="{}{}_{}".format(
            prefix or '', name, _))
        try:
            pod.wait_for_status(status='running', tries=36)
            pods.append(pod)
        except StatusWaitException as ex:
            log_debug("Pod isn't started - {}".format(ex))
            events = pod.events(event_type='warning',
                                event_source='component:default-scheduler',
                                event_reason='FailedScheduling')
            no_res_msg = "Node didn't have enough resource"
            no_res_events = [e for e in events if no_res_msg in e['message']]
            assert_eq(len(no_res_events) > 0, True)
            return pods

    raise ValueError("max_pods '{}' was not enough to load node.".format(
                     len(pods)))
