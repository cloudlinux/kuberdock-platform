import itertools
import pexpect
import logging

from time import sleep
from colorama import Style, Fore

from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.integration_test_utils import (
    assert_raises, local_exec)
from tests_integration.lib.pipelines import pipeline


LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

HTTP_PORT = 80
UDP_PORT = 2000


class Check:
    Passes = 'passes'
    Fails = 'fails'


def setup_pods(cluster):
    # test_user: iso1@node1 iso3@node2 iso4@node1
    # alt_test_user: iso2@node2
    pods = {
        'iso1': cluster.pods.create(
            'hub.kuberdock.com/nginx', 'iso1', owner='test_user',
            public_ports=[HTTP_PORT, UDP_PORT]),
        'iso2': cluster.pods.create(
            'hub.kuberdock.com/nginx', 'iso2', owner='alt_test_user',
            public_ports=[HTTP_PORT], kube_type='Tiny'),
        'iso3': cluster.pods.create(
            'hub.kuberdock.com/nginx', 'iso3', owner='test_user',
            kube_type='Tiny'),
        'iso4': cluster.pods.create(
            'hub.kuberdock.com/nginx', 'iso4', owner='test_user'),
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


def container_udp_server(pod, container_id):
    sleep(3)
    pod.docker_exec(
        container_id, 'netcat -lp 2000  -u -c \'/bin/echo PONG\'',
        detached=True)


# Unregistered host checks.
# NOTE: Jenkins will take a role of an unregistered host.
def unregistered_host_port_check(pod_ip, port=80):
    local_exec('curl -m 5 -k {}:{}'.format(pod_ip, port), shell=True)


def unregistered_host_udp_check(pod_ip, port=2000):
    cmd = 'echo PING | nc -u -w1 {} {}'.format(pod_ip, port)
    _, out, _ = local_exec(cmd, shell=True)

    if out.strip() != 'PONG':
        raise NonZeroRetCodeException('No PONG received')


def unregistered_host_http_check(pod_ip):
    local_exec('curl -m 5 -k http://{}'.format(pod_ip),
               shell=True)


def unregistered_host_https_check(pod_ip):
    local_exec('curl -m 5 -k https://{}'.format(pod_ip),
               shell=True)


def unregistered_host_ssh_check(host):
    """
    Test that an unregistered host has access through port 22, i.e. SSH.
    Note that the host's public key should be present on a remote server in
    test.

    We need to use `pexpect` module instead of `local_exec`, because
    there is a prompt to add a host to 'known_hosts', which causes test
    to fail, because there are no means to send 'yes' via `local_exec`.
    """
    cmd = 'ssh root@{} ls -d /usr'.format(host)
    LOG.debug('{0}Calling SSH: {1}{2}'.format(Style.DIM, cmd, Style.RESET_ALL))
    ssh_cli = pexpect.spawn(cmd)
    i = ssh_cli.expect(['\(yes/no\)\? ', '/usr'])
    if i == 0:
        ssh_cli.sendline('yes')
        ssh_cli.expect('/usr')
    out = ssh_cli.before + ssh_cli.after
    LOG.debug('\n{0}=== StdOut ===\n{1}{2}'.format(
        Fore.YELLOW, out, Style.RESET_ALL))
    if '/usr' not in out:
        raise NonZeroRetCodeException('ssh failed. "/usr" not found in output')


# Registered host/node checks
def host_icmp_check_pod(cluster, host, pod_ip):
    cluster.ssh_exec(host, 'ping -c 2 {}'.format(pod_ip))


def host_http_check_pod(cluster, host, pod_ip):
    cluster.ssh_exec(host, 'curl -m 5 -k http://{}'.format(pod_ip))


def host_udp_server(cluster, host):
    cluster.ssh_exec(host, 'netcat -lp 2000  -u -c \'/bin/echo PONG\' &')


def host_udp_check_pod(cluster, host, pod_ip, port=2000):
    cmd = 'echo PING | nc -u -w1 {} {}'.format(pod_ip, port)
    _, out, _ = cluster.ssh_exec(host, cmd)
    if out != 'PONG':
        raise NonZeroRetCodeException('No PONG received')


# Should be fixed in AC-4158
# @pipeline('networking_rhost_cent6')
@pipeline('networking')
@pipeline('networking_upgraded')
def test_network_isolation(cluster):
    # type: (KDIntegrationTestAPI) -> None
    user1_pods = ['iso1', 'iso3', 'iso4']
    # user2_pods = ['iso2']
    container_ids, container_ips, pods, specs = setup_pods(cluster)

    # ------ General tests -------
    # Docker container has access to the world
    for pod in pods.values():
        ping(pod, container_ids[pod.name], '8.8.8.8')

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
        # TCP check
        http_check(pods[src], container_ids[src], container_ips[dst])
        # UDP check
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

    # test_user: iso2 -> test_user: iso1
    # Containers of different users see each other via public/pod/service IP
    # through public ports
    src, dst = 'iso2', 'iso1'
    data = [(specs[dst]['public_ip'], True), (container_ips[dst], True),
            (specs[dst]['podIP'], False)]
    for host, do_ping in data:
        # ICMP check
        if do_ping:
            ping(pods[src], container_ids[src], host)
        else:
            with assert_raises(NonZeroRetCodeException):
                ping(pods[src], container_ids[src], host)
        # TCP check. port 80 is public
        http_check(pods[src], container_ids[src], host)
        # UDP check. port 2000 is public
        container_udp_server(pods[dst], container_ids[dst])
        udp_check(pods[src], container_ids[src], host)

    # test_user: iso1 -> alt_test_user: iso2
    # Containers of different users don't see each other through closed ports,
    # only through public ports (public/service/pod IP)
    src, dst = 'iso1', 'iso2'
    data = [(specs[dst]['public_ip'], True), (container_ips[dst], True),
            (specs[dst]['podIP'], False)]
    for host, do_ping in data:
        # ICMP check
        if do_ping:
            ping(pods[src], container_ids[src], host)
        else:
            with assert_raises(NonZeroRetCodeException):
                ping(pods[src], container_ids[src], host)
        # TCP check. port 80 is public
        http_check(pods[src], container_ids[src], host)
        # UDP check. port 2000 is closed
        container_udp_server(pods[dst], container_ids[dst])
        with assert_raises(NonZeroRetCodeException):
            udp_check(pods[src], container_ids[src], host)

    # alt_test_user: iso2 -> test_user: iso3
    # Different users' pods can't access each other via service/pod IP
    src, dst = 'iso2', 'iso3'
    for host in (container_ips[dst], specs[dst]['podIP']):
        # ICMP check
        # with assert_raises(NonZeroRetCodeException):
        #     ping(pods[src], container_ids[src], host)
        # TCP check. port 80 is closed
        with assert_raises(NonZeroRetCodeException):
            http_check(pods[src], container_ids[src], host)
        # UDP check. port 2000 is closed
        container_udp_server(pods[dst], container_ids[dst])
        with assert_raises(NonZeroRetCodeException):
            udp_check(pods[src], container_ids[src], host)

    # ----- Host isolation -----
    # Container can't access node's IP it's created on
    # ICMP check
    with assert_raises(NonZeroRetCodeException, '100% packet loss'):
        ping(pods['iso1'], container_ids['iso1'], specs['iso1']['hostIP'])

    # TCP check
    with assert_raises(NonZeroRetCodeException,
                       '(Connection refused|Connection timed out)'):
        http_check(
            pods['iso1'], container_ids['iso1'], specs['iso1']['hostIP'])
    # UDP check
    host_udp_server(cluster, pods['iso1'].info['host'])
    with assert_raises(NonZeroRetCodeException):
        udp_check(pods['iso1'], container_ids['iso1'], specs['iso1']['hostIP'])  # noqa

    # Container can't access node's IP it was not created on
    # We do not know which node the pod will land on, so we can't tell in
    # advance what the "other nodes" are. Should find this out
    nodes, pod_node = cluster.node_names, pods['iso1'].info['host']
    nodes.remove(pod_node)
    another_node = nodes[0]

    node_ip = cluster.get_host_ip(another_node)
    # TCP check
    with assert_raises(NonZeroRetCodeException, 'Connection refused'):
        http_check(pods['iso1'], container_ids['iso1'], node_ip)
    # UDP check
    host_udp_server(cluster, another_node)
    with assert_raises(NonZeroRetCodeException):
        udp_check(pods['iso1'], container_ids['iso1'], node_ip)

    # ------ Registered hosts tests ------
    # Pods with public IP
    pod_ip_list = [(pod, specs[name]['public_ip'], True)
                   for name, pod in pods.items() if pod.public_ip]
    # All Pod IPs
    pod_ip_list.extend([(pod, container_ips[name], True)
                        for name, pod in pods.items()])
    # All Service IPs. Don't respond to pings
    pod_ip_list.extend([(pod, specs[name]['podIP'], False)
                        for name, pod in pods.items()])

    # Registered hosts have acces through all ports via public/pod/service IP
    for pod, target_host, do_ping in pod_ip_list:
        # ICMP check
        if do_ping:
            host_icmp_check_pod(cluster, 'rhost1', target_host)
        else:
            with assert_raises(NonZeroRetCodeException):
                host_icmp_check_pod(cluster, 'rhost1', target_host)
        # TCP check
        host_http_check_pod(cluster, 'rhost1', target_host)
        # UDP check
        # TODO: doesn't work. AC-4783
        # container_udp_server(pod, container_ids[pod.name])
        # host_udp_check_pod(cluster, 'rhost1', target_host)

    # ---------- Master tests ---------
    for pod, target_host, do_ping in pod_ip_list:
        # ICMP check
        if do_ping:
            host_icmp_check_pod(cluster, 'master', target_host)
        else:
            with assert_raises(NonZeroRetCodeException):
                host_icmp_check_pod(cluster, 'master', target_host)
        # TCP check
        host_http_check_pod(cluster, 'master', target_host)
        # UDP check
        # TODO: doesn't work. AC-4783
        # container_udp_server(pod, container_ids[pod.name])
        # host_udp_check_pod(cluster, 'master', target_host)

    # ----------- Nodes tests ----------
    # Node has access to public/service/pod IP of the pods it's hosting
    # iso2: public ports: TCP:80 closed port: UDP:2000
    target_pod = 'iso2'
    host_node = specs[target_pod]['host']
    another_node = [n for n in cluster.node_names if n != host_node][0]
    iso2_ip_list = [
        (specs[target_pod]['public_ip'], True),
        (container_ips[target_pod], True),
        (specs[target_pod]['podIP'], False),
    ]
    for target_ip, do_ping in iso2_ip_list:
        # Host node ICMP check
        if do_ping:
            host_icmp_check_pod(cluster, host_node, target_ip)
        else:
            with assert_raises(NonZeroRetCodeException):
                host_icmp_check_pod(cluster, host_node, target_ip)
        # Host node TCP check
        host_http_check_pod(cluster, host_node, target_ip)
        # Host node UDP check
        # NOTE: doesn't work. AC-4783
        # container_udp_server(pods[target_pod], container_ids[target_pod])
        # host_udp_check_pod(cluster, host_node, target_ip)

        # Another node ICMP check
        if do_ping:
            host_icmp_check_pod(cluster, another_node, target_ip)
        else:
            with assert_raises(NonZeroRetCodeException):
                host_icmp_check_pod(cluster, another_node, target_ip)
        # Another node TCP check
        host_http_check_pod(cluster, another_node, target_ip)
        # Another node UDP check. port 2000 is not public
        container_udp_server(pods[target_pod], container_ids[target_pod])
        # NOTE: works now, need to be rechecked after AC-4783 is done.
        with assert_raises(NonZeroRetCodeException):
            host_udp_check_pod(cluster, another_node, target_ip)

    # ---------- Node has access to world -------------
    for node_name in cluster.node_names:
        cluster.ssh_exec(node_name, 'ping -c 2 cloudlinux.com')

    # ------ Unregistered hosts tests ------
    # Node isolation from world
    # NOTE: Needs rework
    for node_name in cluster.node_names:
        node_ip = cluster.get_host_ip(node_name)
        # Try port 22
        unregistered_host_ssh_check(node_ip)

        for rec in _get_node_ports(cluster, node_name):
            if rec[0] == 'udp' or rec[1] == 22:
                continue
            with assert_raises(NonZeroRetCodeException):
                unregistered_host_port_check(node_ip, rec[1])

    # Unregistered host can access public ports only
    # iso1
    # TCP http check
    unregistered_host_http_check(specs['iso1']['public_ip'])
    # UDP check
    # TODO: doesn't work. AC-4783
    # container_udp_server(pods['iso1'], container_ids['iso1'])
    # unregistered_host_udp_check(specs['iso1']['public_ip'])

    # iso2
    # TCP http check
    unregistered_host_http_check(specs['iso2']['public_ip'])
    # UDP check (port 2000 is closed)
    # NOTE: works for now, but should be revised after AC-4783
    container_udp_server(pods['iso2'], container_ids['iso2'])
    with assert_raises(NonZeroRetCodeException):
        unregistered_host_udp_check(specs['iso2']['public_ip'], port=2000)

    # Containers inside a single pod have access to each other through
    # localhost
    # wp_pa = cluster.pods.create_pa('wordpress.yaml', wait_ports=True,
    #                                wait_for_status='running',
    #                                healthcheck=False)
    # containers = wp_pa.containers
    # mysql = [c for c in containers if c['name'] == 'mysql'][0]
    # wordpress = [c for c in containers if c['name'] == 'wordpress'][0]
    #
    # mysql_port = mysql['ports'][0]['containerPort']
    # NOTE: doesn't work, because of non utf8 characters in the output.
    # Need a better way to communicate with mysql container
    # http_check(wp_pa, wordpress['containerID'],
    #            'localhost:{}'.format(mysql_port))


def _get_node_ports(cluster, node_name):
    _, out, _ = cluster.ssh_exec(node_name, 'netstat -ltunp')
    out_lines = out.strip().split('\n')
    # Match strings are 'tcp ' and 'udp ' in order to exclude ipv6 addresses
    tcp_udp_only = [rec for rec in out_lines if 'tcp ' in rec or 'udp ' in rec]

    def _make_port_rec(rec):
        cols = [c for c in rec.strip().split() if len(c) > 0]
        return (
            cols[0],
            int(cols[3].strip().split(':')[-1])
        )

    return {_make_port_rec(rec) for rec in tcp_udp_only}
