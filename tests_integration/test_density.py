import logging
from time import sleep
from tests_integration.lib.cluster_utils import (set_kubelet_multipliers,
                                                 add_pa_from_url)
from tests_integration.lib.load_testing_utils import (gen_workload,
                                                      fill_with_pa)

from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.utils import assert_eq

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


CPU_MULT = 10
MEMORY_MULT = 10
REQUESTS_NUMBER = 1
REQUESTED_PODS = 0.1
PODS_NUMBER_EXPECTED = 50


@pipeline("density")
@pipeline("density_aws")
def test_density_with_increased_multipliers(cluster):
    LOG.debug("Modifying multipliers.")
    set_kubelet_multipliers(cluster, CPU_MULT, MEMORY_MULT)
    LOG.debug("Create, start and install density wordpress pods till it "
              "is possible.")
    # TODO change to stable when Density released on github
    pa_url = "https://raw.githubusercontent.com/cloudlinux/" \
             "kuberdock_predefined_apps/1.5.0-beta/wordpress.yaml"
    pa_name = add_pa_from_url(cluster, pa_url)
    pods = fill_with_pa(cluster, pa_name)
    not_stated_pod = pods.pop()
    LOG.info("With multipliers ({} cpu {} memory) {} wordpress"
             " pods was deployed".format(
                 CPU_MULT, MEMORY_MULT, len(pods)))
    pods_count = len(pods)
    assert pods_count < PODS_NUMBER_EXPECTED, ("Actually created pods count "
                                               "is less then expected")
    sample_size = int(pods_count * REQUESTED_PODS)
    with gen_workload(pods, sample_size, REQUESTS_NUMBER):
        LOG.debug("Waiting 5 min to get pods loaded enough.")
        sleep(5 * 60)
        cluster.ssh_exec('node1', 'top -bn3 | head -20')
        LOG.debug("Increase multipliers.")
        set_kubelet_multipliers(cluster, CPU_MULT * 2, MEMORY_MULT)
        LOG.debug("Start and install pod, which start has failed at step one.")
        not_stated_pod.start()
        not_stated_pod.wait_for_status('running')
        second_pods = fill_with_pa(cluster, pa_name, with_healthcheck=False)

    second_pods_count = len(second_pods) - 1
    LOG.info("With increased multipliers ({} cpu {} memory) {} wordpress"
             " pods was deployed".format(CPU_MULT * 2, MEMORY_MULT,
                                         second_pods_count))
    # It should be able to fit twice more pods.
    assert_eq(pods_count, second_pods_count)
