import itertools
from time import sleep

from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.integration_test_api import KDIntegrationTestAPI
from tests_integration.lib.integration_test_utils import assert_raises
from tests_integration.lib.pipelines import pipeline


def setup_pods(cluster):
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

    return container_ids, container_ips, pods, specs


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
    pod.docker_exec(container_id, 'curl -m 5 -k http://{}'.format(host))


def https_check(pod, container_id, host):
    pod.docker_exec(container_id, 'curl -m 5 -k https://{}'.format(host))


def udp_check(pod, container_id, host, port=2000):
    cmd = 'echo PING | nc -u -w1 {} {}'.format(host, port)
    _, out, _ = pod.docker_exec(container_id, cmd)
    if out != 'PONG':
        raise NonZeroRetCodeException('No PONG received')


def host_udp_server(cluster, host):
    cluster.ssh_exec(host, 'netcat -lp 2000  -u -c \'/bin/echo PONG\' &')


def container_udp_server(pod, container_id):
    # TODO: Remove when AC-3307 merged
    sleep(3)
    pod.docker_exec(
        container_id, 'netcat -lp 2000  -u -c \'/bin/echo PONG\'',
        detached=True)


@pipeline('networking')
def test_network_isolation_from_user_container(cluster):
    # type: (KDIntegrationTestAPI) -> None
    user1_pods = ['iso1', 'iso3', 'iso4']
    user2_pods = ['iso2']
    container_ids, container_ips, pods, specs = setup_pods(cluster)

    # ------ General tests -------
    # Docker container has access to the world
    for pod in pods.values():
        ping(pod, container_ids[pod.name], '8.8.8.8')

    with assert_raises(NonZeroRetCodeException):
        host = pods['iso1'].info['host']
        host_udp_server(cluster, host)
        udp_check(pods['iso1'], container_ids['iso1'], host)

    # Docker container has a working DNS server
    for pod in pods.values():
        ping(pod, container_ids[pod.name], 'cloudlinux.com')

    for name, pod in pods.items():
        # Check that 10.254.0.10 DNS POD is reachable from container
        pod.docker_exec(
            container_ids[name], 'dig +short cloudlinux.com @10.254.0.10')
        pod.docker_exec(
            container_ids[name], 'dig +short +tcp cloudlinux.com @10.254.0.10')
        # Check that external DNS also works
        pod.docker_exec(
            container_ids[name], 'dig +short cloudlinux.com @8.8.8.8')
        pod.docker_exec(
            container_ids[name], 'dig +short +tcp cloudlinux.com @8.8.8.8')

    # Container can access itself by container IP
    for pod in pods.keys():
        # ICMP check
        ping(pods[pod], container_ids[pod], container_ips[pod])
        # TCP check
        http_check(pods[pod], container_ids[pod], container_ips[pod])
        # UDP check
        container_udp_server(pods[pod], container_ids[pod])
        udp_check(pods[pod], container_ids[pod], container_ips[pod])

    # Container can reach it's public IP
    for pod in (p for p in pods.values() if p.public_ip):
        # TCP check
        http_check(pod, container_ids[pod.name], specs[pod.name]['public_ip'])
        # UDP check
        container_udp_server(pods[pod.name], container_ids[pod.name])
        udp_check(pod, container_ids[pod.name], specs[pod.name]['podIP'])

    # Docker container should have access to kubernetes over flannel
    for name, pod in pods.items():
        https_check(pod, container_ids[name], '10.254.0.1')

    # ----- User -> User isolation tests -----
    # Containers of the same user can reach each other via pod IP
    for src, dst in itertools.product(user1_pods, user1_pods):
        http_check(pods[src], container_ids[src], container_ips[dst])
        container_udp_server(pods[dst], container_ids[dst])
        udp_check(pods[src], container_ids[src], container_ips[dst])

    # Containers of the same user see each other via service IP AC-1530
    # NB! Within KuberDock it's called podIP for historical reasons
    for src, dst in itertools.product(user1_pods, user1_pods):
        # TCP check
        http_check(pods[src], container_ids[src], specs[dst]['podIP'])
        # UDP check
        container_udp_server(pods[dst], container_ids[dst])
        udp_check(pods[src], container_ids[src], specs[dst]['podIP'])

    # Containers of the same user can reach each other via public IP
    for src, dst in itertools.product(user1_pods, user1_pods):
        if 'public_ip' not in specs[dst]:
            continue
        # TCP check
        http_check(pods[src], container_ids[src], specs[dst]['public_ip'])
        # UDP check
        container_udp_server(pods[dst], container_ids[dst])
        udp_check(pods[src], container_ids[src], specs[dst]['public_ip'])

    # Containers of different users can't access each other via service IP
    # pod IP AC-1530
    for src, dst in itertools.product(user1_pods, user2_pods):
        # ICMP check
        with assert_raises(NonZeroRetCodeException, '100% packet loss'):
            ping(pods[src], container_ids[src], specs[dst]['podIP'])
        # TCP check
        with assert_raises(NonZeroRetCodeException, 'Connection refused'):
            http_check(pods[src], container_ids[src], specs[dst]['podIP'])
        # UDP check
        container_udp_server(pods[dst], container_ids[dst])
        with assert_raises(NonZeroRetCodeException):
            udp_check(pods[src], container_ids[src], specs[dst]['podIP'])

    # Containers of different users do not see each other via container IP
    for src, dst in itertools.product(user1_pods, user2_pods):
        # ICMP check
        with assert_raises(NonZeroRetCodeException, '100% packet loss'):
            ping(pods[src], container_ids[src], container_ips[dst])
        # TCP check
        with assert_raises(NonZeroRetCodeException, 'Connection refused'):
            http_check(pods[src], container_ids[src], container_ips[dst])
        # UDP check
        container_udp_server(pods[dst], container_ids[dst])
        with assert_raises(NonZeroRetCodeException):
            udp_check(pods[src], container_ids[src], container_ips[dst])

    # ----- Host isolation -----
    # Container can't access node's IP it's created on
    # ICMP check
    with assert_raises(NonZeroRetCodeException, '100% packet loss'):
        ping(pods['iso1'], container_ids['iso1'], specs['iso1']['hostIP'])
    # TCP check
    with assert_raises(NonZeroRetCodeException, 'Connection timed out'):
        http_check(
            pods['iso1'], container_ids['iso1'], specs['iso1']['hostIP'])
    # UDP check
    host_udp_server(cluster, pods['iso1'].info['host'])
    with assert_raises(NonZeroRetCodeException):
        udp_check(pods['iso1'], container_ids['iso1'], specs['iso1']['hostIP'])

    # Container can't access node's IP it was not created on
    # We do not know which node the pod will land on, so we can't tell in
    # advance what the "other nodes" are. Should find this out
    nodes, pod_node = cluster.node_names, pods['iso1'].info['host']
    nodes.remove(pod_node)
    another_node = nodes[0]

    node_ip = cluster.get_host_ip(another_node)
    # ICMP check
    with assert_raises(NonZeroRetCodeException, '100% packet loss'):
        ping(pods['iso1'], container_ids['iso1'], node_ip)
    # TCP check
    with assert_raises(NonZeroRetCodeException, 'Connection refused'):
        http_check(pods['iso1'], container_ids['iso1'], node_ip)
    # UDP check
    host_udp_server(cluster, another_node)
    with assert_raises(NonZeroRetCodeException):
        udp_check(pods['iso1'], container_ids['iso1'], another_node)

    # ------ Registered hosts tests ------
    # Registered host has access to flannel network. Test that by
    # trying to access container IP and service IP
    for name, pod in pods.items():
        # ICMP
        cluster.ssh_exec('rhost1', 'ping -c 2 {}'.format(container_ips[name]))
        # TCP container IP
        cluster.ssh_exec(
            'rhost1', 'curl -v http://{}'.format(container_ips[name]))
        # TCP service IP
        cluster.ssh_exec(
            'rhost1', 'curl -v http://{}'.format(specs[name]['podIP']))
