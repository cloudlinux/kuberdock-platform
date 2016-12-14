import json
import logging

from kubedock.constants import KUBERDOCK_INGRESS_POD_NAME

from tests_integration.lib.exceptions import StatusWaitException
from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.pod import KDPod
from tests_integration.lib.utils import assert_eq, escape_command_arg, \
    get_rnd_low_string, hooks, log_debug, retry

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


def _add_domain(cluster):
    with open("tests_integration/assets/cpanel_credentials.json") as f:
        creds = json.load(f)

    for k, v in creds.items():
        if k != "domain":
            cluster.set_system_setting(escape_command_arg(v), name=k)

    # Wait till DNS Pod is running
    # It's impossible to import KUBERDOCK_DNS_POD_NAME from kubedock/kapi/nodes
    # because nodes tries import from flask which isn't installed on the CI host
    dns_pod = KDPod.get_internal_pod(cluster, "kuberdock-dns")
    dns_pod.wait_for_status("running")

    cluster.domains.add(name=creds["domain"],
                        ignore_duplicates=True)
    # Make sure ingress controller has been created
    retry(KDPod.get_internal_pod, tries=6, interval=10,
          cluster=cluster, pod_name=KUBERDOCK_INGRESS_POD_NAME)
    ingress_pod = KDPod.get_internal_pod(cluster, KUBERDOCK_INGRESS_POD_NAME)
    ingress_pod.wait_for_status("running")


def _remove_domain(cluster):
    cluster.pods.clear()
    cluster.domains.delete_all()
    cluster.set_system_setting("'No provider'", name="dns_management_system")


@pipeline("shared_ip")
@pipeline("main_aws")
@hooks(setup=_add_domain, teardown=_remove_domain)
def test_pod_with_domain_name(cluster):
    suffix = get_rnd_low_string(length=5)
    pod_name = format(suffix)
    with open("tests_integration/assets/cpanel_credentials.json") as f:
        creds = json.load(f)
    log_debug("Start a pod with shared IP", LOG)
    pod = cluster.pods.create("nginx", pod_name, ports_to_open=[80],
                              wait_for_status="running", domain=creds["domain"],
                              healthcheck=True, wait_ports=True)
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
              format(suffix, creds["domain"]))
    pod.wait_for_ports([80])
    pod.healthcheck()

    log_debug("Start and stop the pod with shared IP", LOG)
    pod.stop()
    pod.wait_for_status("stopped")
    pod.start()
    pod.wait_for_status("running")
    pod.wait_for_ports([80])
    pod.healthcheck()

    log_debug("Change number of kubes in the pod with shared IP", LOG)
    pod.change_kubes(kubes=3, container_image="nginx")
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


@pipeline("shared_ip")
@hooks(setup=_add_domain, teardown=_remove_domain)
def test_pod_with_long_domain_name(cluster):
    """
     Tes that pod with domain name's length equaling 63 (kubernetes
     limitation) symbols can be created and accessed
    """
    with open("tests_integration/assets/cpanel_credentials.json") as f:
        creds = json.load(f)

    # Adjusting pod name's length to make domain name's length equal 63. 53
    # is 63 - 10 (length of "testuser-.")
    pod_name = get_rnd_low_string(length=53 - len(creds["domain"]))

    log_debug("Start the pod with shared IP, having domain name consisting "
              "of 63 symbols", LOG)
    pod = cluster.pods.create("nginx", pod_name, ports_to_open=[80],
                              wait_for_status="running", domain=creds["domain"],
                              healthcheck=True, wait_ports=True)
    assert_eq(pod.domain, "testuser-{}.{}".
              format(pod_name, creds["domain"]))

