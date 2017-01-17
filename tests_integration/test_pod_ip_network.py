import logging
from time import sleep

from tests_integration.lib.constants import POD_IP_NETWORK
from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.utils import assert_eq, ip_belongs_to_network, \
    POD_STATUSES


LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


@pipeline('pod_ip_network')
def test_defined_pod_ip_network(cluster):
    # TODO remove this function and it's usages after fix of 5403
    def _avoid_NoSuitableNode_error(f, arg):
        try:
            return f(arg)
        except NonZeroRetCodeException as e:
            if "NoSuitableNode" in e.stderr:
                sleep(5)
                nodes_info = cluster.nodes.get_list()
                LOG.debug("Nodes info:\n{}".format(nodes_info))
                return f(arg)

    def _create_nginx_pod(name):
        LOG.debug("Creating custom {}".format(name))
        return cluster.pods.create("nginx", name, start=True, wait_ports=True,
                                   open_all_ports=True,
                                   wait_for_status=POD_STATUSES.running,
                                   healthcheck=True)

    def _create_pa_pod(template):
        LOG.debug("Creating pod from {} template".format(template))
        return cluster.pods.create_pa(template, wait_ports=True,
                                      wait_for_status=POD_STATUSES.running,
                                      healthcheck=True)

    def _check_k8s_pod_ips(ip):
        LOG.debug("Checking IP {}".format(ip))
        error_message = "K8S pod IP should have belonged to {} network. But " \
                        "it's {} instead".format(POD_IP_NETWORK, ip)
        assert_eq(ip_belongs_to_network(ip, POD_IP_NETWORK), True, error_message)

    pod_names = ["pod1", "pod2"]
    pods = [_avoid_NoSuitableNode_error(_create_nginx_pod, name)
            for name in pod_names]
    pods.append(_avoid_NoSuitableNode_error(_create_pa_pod, 'wordpress.yaml'))
    k8s_pod_ips = [pod.k8s_pod_ip for pod in pods]
    for ip in k8s_pod_ips:
        _check_k8s_pod_ips(ip)
