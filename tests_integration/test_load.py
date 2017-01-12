import logging
from time import sleep

from tests_integration.lib.cluster_utils import add_pa_from_url, \
    set_kubelet_multipliers
from tests_integration.lib.exceptions import NoSpaceLeftOnPersistentVolume
from tests_integration.lib.load_testing_utils import gen_workload
from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.utils import assert_in, assert_raises, POD_STATUSES

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

    pods = _load_cluster_with_density_wp_pods(cluster, cpu_mult, ram_mult,
                                              total_pods)
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


# TODO change pipelines to load_testing load_testing_aws when AC-5648 is
# implemented
@pipeline('load_testing_2')
@pipeline('load_testing_aws_2')
def test_increasing_pv_size_on_loaded_cluster(cluster):
    """
    1. Load cluster by wp pod, which receive GET requests.
    2. Overuse space of PV of control pod, make sure that no more data can
    be written.
    3. Increase size of PV.
    4. Make sure that new data can be written.
    5. Overuse increased PV, make sure that no more data can be written.
    """
    # test_increasing_pv_size_on_loaded_cluster
    # type: (KDIntegrationTestAPI) -> None

    # Test inputs
    cpu_mult = 30  # 480 kubes by CPU.
    ram_mult = 10  # 640 kubes by RAM.
    total_pods = 50  # 1 density WP pod takes 6 kubes. Total: 300 kubes.
    req_per_sec = 1
    loaded_pods = 0.20  # 20 % of pods are actively used at time
    loaded_pods_num = int(total_pods * loaded_pods)

    container_name = "wordpress"
    file_size_1 = 800  # Can be written to 1G disk
    file_size_2 = 500  # 800 + 500 will overuse 1G disk, but can be fit on 2G
    file_size_3 = 800  # 800 + 500 + 800 will overuse 2G disk
    increased_volume_size = 2  # Currently default size is 1G

    pods = _load_cluster_with_density_wp_pods(cluster, cpu_mult, ram_mult,
                                              total_pods)

    # Selecting control pod from the middle of the batch.
    ctrl_pod = pods[len(pods)/2]
    custom_cont = "Testing pod content after increasing PV size"
    custom_post_path = ctrl_pod.publish_post(content=custom_cont)
    LOG.debug("Pod '{}' is a Control WP pod for PV size increasing.".
              format(ctrl_pod.pod_id))

    tested_pv = next(pv for pv in ctrl_pod.get_persistent_volumes()
                     if "www" in pv.name)
    LOG.debug("PV '{}' is a control PV for size increasing.".
              format(tested_pv.name))
    with gen_workload(pods, loaded_pods_num, req_per_sec):
        LOG.debug("Waiting 5 min to get pods loaded enough.")
        sleep(5 * 60)
        LOG.debug("Staring to fill PV of control WP pod.")
        LOG.debug("Creating file with size {}MB.".format(file_size_1))
        path = "{}/{}".format(tested_pv.mount_path, "f1")
        ctrl_pod.fill_volume_space(path, file_size_1,
                                   container_name=container_name)
        LOG.debug("Trying to create file with size {}MB.".format(file_size_2))
        path = "{}/{}".format(tested_pv.mount_path, "f2")
        with assert_raises(NoSpaceLeftOnPersistentVolume):
            ctrl_pod.fill_volume_space(path, file_size_2,
                                       container_name=container_name)
        LOG.debug("Increasing disk size")
        tested_pv.change_size(increased_volume_size)

        LOG.debug("Creating file with size {}MB.".format(file_size_2))
        path = "{}/{}".format(tested_pv.mount_path, "f2")
        ctrl_pod.fill_volume_space(path, file_size_2,
                                   container_name=container_name)
        LOG.debug("Trying to create file with size {}MB.".format(file_size_3))
        path = "{}/{}".format(tested_pv.mount_path, "f3")
        with assert_raises(NoSpaceLeftOnPersistentVolume):
            ctrl_pod.fill_volume_space(path, file_size_3,
                                       container_name=container_name)
        LOG.debug("Check that pod is still accessible.".format(file_size_3))
        assert_in(custom_cont, ctrl_pod.do_GET(path=custom_post_path))


def _load_cluster_with_density_wp_pods(cluster, cpu_mult,
                                       ram_mult, total_pods):
    """
    Create specified amount of density Wordpress pods and create single post
    for each of them

    :param cpu_mult: value of KD cpu multiplier
    :param ram_mult: value of KD memory multiplier
    :param total_pods: number of Wordpress pods to create
    :return: list of created pods
    """

    set_kubelet_multipliers(cluster, cpu_mult, ram_mult)

    # TODO change to stable when Density released on github
    pa_url = "https://raw.githubusercontent.com/cloudlinux/" \
             "kuberdock_predefined_apps/1.5.0-beta/wordpress.yaml"
    name = add_pa_from_url(cluster, pa_url)

    try:
        pods = [cluster.pods.create_pa(name,
                                       wait_for_status="running",
                                       healthcheck=True)
                for _ in range(total_pods)]
        for p in pods:
            p.publish_post()  # each WP has at least 1 post
    finally:
        cluster.ssh_exec('node1', 'top -bn3 | head -20')
    return pods
