import logging
from time import sleep

from tests_integration.lib.cluster_utils import add_pa_from_url, \
    set_kubelet_multipliers
from tests_integration.lib.load_testing_utils import gen_workload
from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.utils import assert_in, POD_STATUSES

LOG = logging.getLogger(__name__)


@pipeline('load_testing')
@pipeline('load_testing_aws')
def test_change_pod_kube_quantity_on_loaded_cluster(cluster):
    # type: (KDIntegrationTestAPI) -> None

    # Kube size: 0.25 CPU; 128 RAM
    # Node size without multipliers: 16 kubes by CPU; 64 kubes by RAM.

    # Test inputs
    cpu_mult = 30  # 480 kubes by CPU.
    ram_mult = 10  # 640 kubes by RAM.
    total_pods = 50  # 1 density WP pod takes 6 kubes. Total: 300 kubes.
    req_per_sec = 1
    loaded_pods = 0.20  # 20 % of pods are actively used at time
    loaded_pods_num = int(total_pods * loaded_pods)

    set_kubelet_multipliers(cluster, cpu_mult, ram_mult)

    # TODO change to stable when Density released on github
    pa_url = "https://raw.githubusercontent.com/cloudlinux/" \
             "kuberdock_predefined_apps/1.5.0-beta/wordpress.yaml"
    name = add_pa_from_url(cluster, pa_url)

    try:
        pods = [cluster.pods.create_pa(name,
                                       wait_for_status=POD_STATUSES.running,
                                       healthcheck=True)
                for _ in range(total_pods)]
        for p in pods:
            p.publish_post()  # each WP has at least 1 post
    finally:
        cluster.ssh_exec('node1', 'top -bn3 | head -20')

    # Selecting control pod from the middle of the batch.
    wp_pod = pods[len(pods) // 2]
    custom_cont = "Testing pod content after resize"
    custom_post_path = wp_pod.publish_post(content=custom_cont)
    LOG.debug("Pod '{}' is a Control WP pod with a custom content.".format(
        wp_pod.pod_id))

    with gen_workload(pods, loaded_pods_num, req_per_sec):
        LOG.debug("Waiting 5 min to get pods loaded enough.")
        sleep(5 * 60)
        cluster.ssh_exec('node1', 'top -bn3 | head -20')

        LOG.debug("Trying to increase number of kubes of a Control WP pod.")
        wp_pod.change_kubes(kubes=6, container_name='wordpress',
                            redeploy=False)
        wp_pod.change_kubes(kubes=10, container_name='mysql',
                            redeploy=True)
        wp_pod.wait_for_status(POD_STATUSES.running)
        wp_pod.wait_http_resp()
        assert_in(custom_cont, wp_pod.do_GET(path=custom_post_path))

    LOG.debug("Pod '{}' has been resized successfully.".format(wp_pod.pod_id))
