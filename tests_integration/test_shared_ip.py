import logging

from urllib2 import HTTPError

from tests_integration.lib.exceptions import StatusWaitException, \
    PublicPortWaitTimeoutException
from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.pod import Port
from tests_integration.lib.utils import assert_eq, assert_in, assert_raises, \
    get_rnd_low_string, hooks, kube_type_to_int, log_debug


LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


def _add_domain(cluster):
    cluster.domains.configure_cpanel_integration()


def _remove_domain(cluster):
    cluster.domains.stop_sharing_ip()


@pipeline("shared_ip")
@pipeline("shared_ip_aws")
@hooks(setup=_add_domain, teardown=_remove_domain)
def test_pod_with_domain_name(cluster):
    suffix = get_rnd_low_string(length=5)
    pod_name = format(suffix)
    log_debug("Start a pod with shared IP", LOG)
    ports = [Port(80, public=True),
             Port(443, public=True)]
    domain = cluster.domains.get_first_domain()
    image = "quay.io/aptible/nginx"
    pod = cluster.pods.create(
        image, pod_name, wait_for_status="running",
        domain=domain, healthcheck=True,
        wait_ports=True, ports=ports)

    log_debug("Restart the pod with shared IP", LOG)
    pod.redeploy()
    try:
        pod.wait_for_status("pending", tries=5, interval=3)
    except StatusWaitException:
        # When is rebooted pod often gets "pending" status for short time,
        # so this status isn't guaranteed to be catched by pod.wait_for_status
        pass
    pod.wait_for_status("running")
    assert_eq(pod.domain, "testuser-{}.{}".
              format(suffix, domain))
    pod.wait_for_ports([80])
    pod.healthcheck()

    log_debug("Stop and start the pod with shared IP", LOG)
    pod.stop()
    pod.wait_for_status("stopped")
    pod.start()
    pod.wait_for_status("running")
    pod.wait_for_ports([80])
    pod.healthcheck()

    log_debug("Change number of kubes in the pod with shared IP", LOG)
    pod.change_kubes(kubes=3, container_image=image)
    try:
        # right after starting changing number of kubes pod is still running
        # for several seconds
        pod.wait_for_status("pending", tries=12)
    except StatusWaitException:
        # "pending" status lasts for very short time and may be not detected
        pass
    pod.wait_for_status("running")
    pod.wait_for_ports([80])
    pod.healthcheck()

    # TODO: uncomment following block when fix for AC-5545 is merged
    """
    log_debug("Close public ports ports", LOG)
    ports = [Port(80, public=False),
             Port(443, public=False)]
    pod.change_pod_ports(ports)
    try:
        pod.wait_for_status("pending", tries=12)
    except StatusWaitException:
        pass
    pod.wait_for_status("running")
    with assert_raises(HTTPError, "Not Found"):
        pod.do_GET()

    log_debug("Open public ports ports", LOG)
    ports = [Port(80, public=True),
             Port(443, public=True)]
    pod.change_pod_ports(ports)
    try:
        pod.wait_for_status("pending", tries=12)
    except StatusWaitException:
        pass
    pod.wait_for_status("running")
    pod.wait_for_ports([80])
    pod.healthcheck()
    """

    log_debug("Cahnge kube type (and moving pod to another node)", LOG)
    pod.change_kubetype(kube_type=kube_type_to_int('High memory'))
    try:
        pod.wait_for_status("pending", tries=12)
    except StatusWaitException:
        pass
    pod.wait_for_status("running")
    pod.wait_for_status("running")
    pod.wait_for_ports([80])
    pod.healthcheck()


@pipeline("shared_ip")
@hooks(setup=_add_domain, teardown=_remove_domain)
def test_pod_with_long_domain_name(cluster):
    """
     Tes that pod with domain name's length equaling 63 (kubernetes
     limitation) symbols can be created and accessed
    """
    domain = cluster.domains.get_first_domain()
    # Adjusting pod name's length to make domain name's length equal 63. 53
    # is 63 - 10 (length of "testuser-.")
    pod_name = get_rnd_low_string(length=53 - len(domain))

    log_debug("Start the pod with shared IP, having domain name consisting "
              "of 63 symbols", LOG)
    pod = cluster.pods.create(
        "nginx", pod_name, open_all_ports=True, wait_for_status="running",
        domain=domain, healthcheck=True, wait_ports=True)
    assert_eq(pod.domain, "testuser-{}.{}".
              format(pod_name, domain))
