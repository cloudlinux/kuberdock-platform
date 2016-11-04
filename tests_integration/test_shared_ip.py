import json

from kubedock.constants import KUBERDOCK_INGRESS_POD_NAME

from tests_integration.lib.exceptions import StatusWaitException
from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.pod import KDPod
from tests_integration.lib.utils import assert_eq, hooks, retry,\
    get_rnd_low_string


def _add_domain(cluster):
    with open("tests_integration/assets/cpanel_credentials.json") as f:
        creds = json.load(f)

    for k, v in creds.items():
        if k != "domain":
            cluster.set_system_setting(v, name=k)

    # Wait till DNS Pod is running
    # It's impossible to import KUBERDOCK_DNS_POD_NAME from kubedock/kapi/nodes
    # because nodes tries import from flask which isn't installed on the CI host
    dns_pod = KDPod.get_internal_pod(cluster, "kuberdock-dns")
    dns_pod.wait_for_status("running")

    # TODO: remove retry when fix for AC-5096 is merged
    retry(cluster.domains.add, name=creds["domain"], tries=30, interval=10)
    ingress_pod = KDPod.get_internal_pod(cluster, KUBERDOCK_INGRESS_POD_NAME)
    ingress_pod.wait_for_status("running")


def _remove_domain(cluster):
    cluster.pods.clear()
    cluster.domains.delete_all()
    cluster.set_system_setting("'No provider'", name="dns_management_system")


@pipeline("main")
@hooks(setup=_add_domain, teardown=_remove_domain)
def test_pod_with_domain_name(cluster):
    suffix = get_rnd_low_string(length=5)
    pod_name = format(suffix)
    with open("tests_integration/assets/cpanel_credentials.json") as f:
        creds = json.load(f)
    pod = cluster.pods.create("nginx", pod_name, ports_to_open=[80],
                              wait_for_status="running", domain=creds["domain"],
                              healthcheck=True, wait_ports=True)
    # Restart the pod
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

    # Stop and start the pod
    pod.stop()
    pod.wait_for_status("stopped")
    pod.start()
    pod.wait_for_status("running")
    pod.wait_for_ports([80])
    pod.healthcheck()

    # TODO: uncommend following section when fix for AC-4970 is merged
    """
    # Change number of kubes:
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
    """
