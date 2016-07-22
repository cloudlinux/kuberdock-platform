import itertools

from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.integration_test_utils import assert_raises
from tests_integration.lib.pipelines import pipeline


def ping(pod, container_id, host):
    """
    Run ping command on container of a given pod. Basically this executes:
    ssh node_of_pod docker exec <container_id> <host>

    :param pod: KDPod object
    :param container_id: docker container ID of a pod
    :param host: ip/domain/hostname whatever you want to ping
    """
    pod.docker_exec(container_id, 'ping -c 2 {}'.format(host))


def http_check(pod, container_id, host):
    pod.docker_exec(container_id, 'curl -k http://{}'.format(host))


@pipeline('networking')
def test_network_isolation_from_user_container(cluster):
    # type: (KDIntegrationTestAPI) -> None
    user1_pods = ['iso1', 'iso3', 'iso4']
    user2_pods = ['iso2']
    pods = {
        'iso1': cluster.create_pod(
            'sysradium/cloudlinux', 'iso1', owner='test_user',
            open_all_ports=True),
        'iso2': cluster.create_pod(
            'sysradium/cloudlinux', 'iso2', owner='alt_test_user',
            open_all_ports=True),
        'iso3': cluster.create_pod(
            'sysradium/cloudlinux', 'iso3', owner='test_user',
            open_all_ports=False),
        'iso4': cluster.create_pod(
            'sysradium/cloudlinux', 'iso4', owner='test_user',
            open_all_ports=False),
    }

    for pod in pods.values():
        pod.wait_for_status('running')

    specs = {
        name: pods[name].get_spec()
        for name in pods.keys()
        }

    container_ids = {
        name: specs[name]['containers'][0]['containerID']
        for name in pods.keys()
        }

    container_ips = {
        name: pods[name].get_container_ip(container_ids[name])
        for name in pods.keys()
        }

    # ------ General tests -------
    # Docker container can have access to the world
    ping(pods['iso1'], container_ids['iso1'], '8.8.8.8')

    # Docker container can't access node's IP it's created on
    with assert_raises(NonZeroRetCodeException, '100% packet loss'):
        ping(pods['iso1'], container_ids['iso1'], specs['iso1']['hostIP'])

    # TODO: Verify why DNS does not work inside CI cluster
    # Docker container has a working DNS server
    # for name in (user1_pods[0], user2_pods[0]):
    #     ping(pods[name], container_ids[name], 'cloudlinux.com')

    # Check that 10.254.0.10 DNS POD is reachable from container
    # for name, pod in pods.items():
    #     pod.docker_exec(
    #         container_ids[name], 'dig +short cloudlinux.com @10.254.0.10')

    # Test containers of different users do not see each other
    with assert_raises(NonZeroRetCodeException, '100% packet loss'):
        ping(pods['iso1'], container_ids['iso1'], container_ips['iso2'])
    with assert_raises(NonZeroRetCodeException, '100% packet loss'):
        ping(pods['iso2'], container_ids['iso2'], container_ips['iso1'])

    # Docker container can ping itself
    for pod in pods.keys():
        ping(pods[pod], container_ids[pod], container_ips[pod])

    # Different user's containers can ping each other's pod IP
    for src, dst in itertools.product(user1_pods, user1_pods):
        http_check(pods[src], container_ids[src], container_ips[dst])

    # Containers of the same user see each other via service IP AC-1530
    # Within KuberDock it's called podIP for historical reasons
    for src, dst in itertools.product(user1_pods, user1_pods):
        http_check(pods[src], container_ids[src], specs[dst]['podIP'])

    # Docker container can reach it's public IP
    http_check(pods['iso1'], container_ids['iso1'], specs['iso1']['public_ip'])

    # Different users can't access service IPs of each other PODs AC-1530
    for src, dst in itertools.product(user1_pods, user2_pods):
        with assert_raises(NonZeroRetCodeException):
            http_check(pods[src], container_ids[src], specs[dst]['podIP'])

    # Docker container can reach other user's pod's public IP
    for src, dst in itertools.product(user1_pods, user1_pods):
        if 'public_ip' in specs[dst]:
            http_check(pods[src], container_ids[src], specs[dst]['public_ip'])

    # Docker container can't access another node's IP
    # We do not know which node the pod will land one, so we can't tell in
    # advance what the "other nodes" are. Should find this out
    # nodes, pod_node = cluster.node_names, pods['iso1'].info['host']
    # nodes.remove(pod_node)
    # another_node = nodes[0]
    #
    # node_ip = cluster.get_host_ip(another_node)
    # with assert_raises(NonZeroRetCodeException, '100% packet loss'):
    #     ping(pods['iso1'], container_ids['iso1'], node_ip)

    # TODO: Maybe remove this setting. It actually works
    # Docker container can't access master IP
    # master_ip = cluster.get_host_ip('master')
    # with assert_raises(NonZeroRetCodeException, '100% packet loss'):
    #     ping(pods['iso1'], container_ids['iso1'], master_ip)

    # Docker container should have access to kubernetes over flannel
    for name, pod in pods.items():
        http_check(pod, container_ids[name], 'curl -kv https://10.254.0.1')

    # ------ Registered hosts tests ------

    # Registered host has access to flannel network. Test that by
    # trying to access container IP and service IP
    for name, pod in pods.items():
        cluster.ssh_exec('rhost1', 'ping -c 2 {}'.format(container_ips[name]))
        cluster.ssh_exec(
            'rhost1', 'curl -v http://{}'.format(container_ips[name]))
        cluster.ssh_exec(
            'rhost1', 'curl -v http://{}'.format(specs[name]['podIP']))
