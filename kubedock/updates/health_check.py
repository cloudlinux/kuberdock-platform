#!/usr/bin/env python

# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.


import os
import re
import sys
import subprocess
import elasticsearch
from fabric.api import env, run, output
from fabric.network import disconnect_all
from fabric.exceptions import NetworkError, CommandTimeout
from kubedock.core import ssh_connect
from kubedock.utils import NODE_STATUSES

if __name__ == '__main__' and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.realpath(__file__)))))

from kubedock.api import create_app
from kubedock.users.models import User
from kubedock.kapi.node_utils import get_nodes_collection
from kubedock.kapi.podcollection import PodCollection
from kubedock.kapi.nodes import get_kuberdock_logs_pod_name
from kubedock.kapi.helpers import LocalService
from kubedock.kapi import pstorage
from kubedock.pods.models import Pod
from kubedock.updates.helpers import setup_fabric
from kubedock.settings import KUBERDOCK_INTERNAL_USER, ELASTICSEARCH_REST_PORT
from kubedock.settings import CEPH, CEPH_POOL_NAME, NODE_LOCAL_STORAGE_PREFIX
from kubedock.utils import POD_STATUSES


SSH_TIMEOUT = 15
MAX_DISK_PERCENTAGE = 90
MESSAGES = {
    'disk': "\tLow disk space: {}",
    'services': "\tSome services in wrong state: {}",
    'ntp': ("\tTime not synced. Please either synchronize it manually "
            "or wait several minutes (up to 20) and repeat"),
    NODE_STATUSES.running: "\tNode not running in kubernetes",
    'ssh': "\tCan't access node from master through ssh",
    'pods': "Some internal pods in wrong state: {}",
    NODE_STATUSES.pending: ("\tThe node is under installation."
                            "Please wait for its completion to upgrade"),
    'calico-node': "\tcalico-node container is not running",
    'tunl': "\tError while get tunl0 IP: {}",
    'bird': "\t{}",
    'elastic': "\t{}",
    'ceph': "\tCan't access CEPH storage: {}",
    'error': "\tCan't get node state: {}"
}

master_services = ['etcd', 'influxdb', 'kube-apiserver', 'docker',
                   'kube-controller-manager', 'kube-scheduler', 'nginx',
                   'kuberdock-k8s2etcd', 'ntpd', 'postgresql', 'redis',
                   'emperor.uwsgi', 'heapster']

node_services = ['ntpd', 'docker', 'kube-proxy', 'kubelet']


def get_service_state(service):
    try:
        with open(os.devnull, 'w') as f:
            subprocess.check_call(
                ['systemctl', 'is-active', service], stdout=f)
            return True
    except Exception:
        return False


def get_services_state(services, local=True):
    if local:
        try:
            rv = subprocess.check_output(['systemctl', 'is-active'] + services)
        except subprocess.CalledProcessError as e:
            rv = e.output
    else:
        rv = run('systemctl is-active ' + ' '.join(services),
                 quiet=True, timeout=SSH_TIMEOUT)
    status = [status == 'active' for status in rv.splitlines()]
    return dict(zip(services, status))


def can_ssh_to_host(hostname):
    ssh, err = ssh_connect(hostname)
    if err:
        return False
    else:
        ssh.close()
        return True


def get_node_state(node):
    status = {}
    if node.get('status') == NODE_STATUSES.pending:
        status[NODE_STATUSES.pending] = False
        return status
    hostname = node['hostname']
    status[NODE_STATUSES.running] = node.get('status') == NODE_STATUSES.running
    env.host_string = hostname
    status['bird'] = check_node_bird_route(node)
    status['elastic'] = check_elastic_access(node)
    try:
        status['ntp'] = False
        status['services'] = False
        # AC-3105 Fix. Check if master can connect to node via ssh.
        if can_ssh_to_host(hostname):
            rv = run('timedatectl status', quiet=True, timeout=SSH_TIMEOUT)
            status['ntp'] = all([line.split()[-1] == 'yes'
                                 for line in rv.splitlines() if 'NTP' in line])
            status['ssh'] = True
            stopped = get_stopped_services(node_services, local=False)
            status['services'] = stopped if stopped else True
            status['disk'] = check_disk_space(local=False)
        else:
            status['ssh'] = False
    except (NetworkError, CommandTimeout):
        status['ssh'] = False
    return status


def get_nodes_state():
    setup_fabric()
    nodes = get_nodes_collection()
    nodes_status = {}
    for node in nodes:
        try:
            nodes_status[node['hostname']] = get_node_state(node)
        except Exception as e:
            nodes_status[node['hostname']] = {'error': e}
    return nodes_status


def get_internal_pods_state():
    ki = User.filter_by(username=KUBERDOCK_INTERNAL_USER).first()
    pod_statuses = {}
    for pod in PodCollection(ki).get(as_json=False):
        pod_statuses[pod['name']] = (pod['status'] == POD_STATUSES.running and
                                     pod['ready'])
    return pod_statuses


def get_disk_usage(local=True):
    if local:
        rv = subprocess.check_output(['df', '--output=source,pcent,target'])
    else:
        rv = run("df --output=source,pcent,target", quiet=True,
                 timeout=SSH_TIMEOUT)
    lines = rv.splitlines()[1:]
    path = NODE_LOCAL_STORAGE_PREFIX + os.path.sep
    r = re.compile('((?!tmpfs|cdrom|{}|SEPID).)*$'.format(path))
    lines = filter(r.match, lines)
    usage = [line.split()[:-1] for line in lines]
    return usage


def check_disk_space(local=True):
    usage = get_disk_usage(local)
    warn = [disk for disk in usage if int(disk[1][:-1]) > MAX_DISK_PERCENTAGE]
    return ', '.join([' - '.join(disk) for disk in warn]) if warn else True


def get_stopped_services(services, local=True):
    services = get_services_state(services, local)
    stopped = [service for service, status in services.items() if not status]
    return stopped


def check_master():
    msg = []
    disk_state = check_disk_space()
    if isinstance(disk_state, str):
        msg.append(MESSAGES['disk'].format(disk_state))
    stopped = get_stopped_services(master_services)
    if stopped:
        msg.append(MESSAGES['services'].format(', '.join(stopped)))
    if not check_calico_node():
        msg.append(MESSAGES['calico-node'])
    tunl_status = check_tunl()
    if isinstance(tunl_status, str):
        msg.append(MESSAGES['tunl'].format(tunl_status))
    return os.linesep.join(msg)


def check_nodes():
    msg = []
    states = {}
    try:
        states = get_nodes_state()
        for node, state in states.items():
            node_msg = []
            for key, state in state.items():
                if not state or not isinstance(state, bool):
                    node_msg.append(MESSAGES[key].format(state))
            if node_msg:
                msg.append("Node {} errors:".format(node))
                msg.extend(node_msg)
    except (SystemExit, Exception) as e:
        msg.append("Can't get nodes list because of {}".format(e.message))
    # list of pending nodes, so log pod for this nodes can be not healthy
    pendings = [get_kuberdock_logs_pod_name(node)
                for node, state in states.items() if
                NODE_STATUSES.pending in state]
    # we check that there are some nodes and not all of them in pending states,
    # so dns pod and policy agent pod shoud be running
    if states and len(pendings) != len(states):
        ceph_status = check_ceph()
        if isinstance(ceph_status, str):
            msg.append(MESSAGES['ceph'].format(ceph_status))
        try:
            pod_states = get_internal_pods_state()
            # list of stopped internal pods. we don't count log pods of pending
            # nodes
            stopped = [pod for pod, status in pod_states.items()
                       if pod not in pendings and not status]
            if stopped:
                msg.append(MESSAGES['pods'].format(', '.join(stopped)))
        except (SystemExit, Exception) as e:
            msg.append("Can't get internal pods states because of {}".format(
                e.message))
    return os.linesep.join(msg)


def check_calico_node():
    try:
        subprocess.check_output(
            'docker ps --format "{{.Names}}" | grep "^calico-node$"',
            shell=True)
        return True
    except subprocess.CalledProcessError:
        return False


def check_tunl():
    try:
        subprocess.check_output('ip addr show dev tunl0 | grep inet',
                                shell=True, stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError as e:
        return e.output.strip()


def check_node_bird_route(node):
    try:
        rv = subprocess.check_output(['ip', 'route', 'show', 'dev', 'tunl0',
                                      'via', node['ip'], 'proto', 'bird'],
                                     stderr=subprocess.STDOUT)
        return True if rv else "There is no bird route to node from master"
    except subprocess.CalledProcessError as e:
        msg = "Error while try to find bird route to node from master: {}"
        return msg.format(e.output.strip())


def check_elastic_access(node):
    internal_user = User.get_internal()
    pod_name = get_kuberdock_logs_pod_name(node['hostname'])
    db_pod = Pod.query.filter(Pod.status != POD_STATUSES.deleted,
                              Pod.name == pod_name,
                              Pod.owner_id == internal_user.id).first()
    pod = PodCollection(internal_user).get(db_pod.id, as_json=False)
    if not pod or pod['status'] != POD_STATUSES.running:
        return True
    services = LocalService()
    clusterIP = services.get_clusterIP_by_pods(pod['id'])
    if not clusterIP:
        return "Can't find elasticsearch service with clusterIP"
    try:
        ip = clusterIP[pod['id']]
        es = elasticsearch.Elasticsearch(ip, port=ELASTICSEARCH_REST_PORT)
        return es.ping()
    except Exception:
        return "Can't access elasticsearch on node"


def check_ceph():
    if not CEPH:
        return True
    try:
        pstorage.STORAGE_CLASS().run_on_first_node('rbd {} ls {}'.format(
            pstorage.get_ceph_credentials(), CEPH_POOL_NAME), timeout=10)
        return True
    except pstorage.NodeCommandError as e:
        return str(e)


def check_cluster():
    msg = []
    master = check_master()
    if master:
        msg.append("Master errors:")
        msg.append(master)
    nodes = check_nodes()
    if nodes:
        msg.append("Nodes errors:")
        msg.append(nodes)
    store = output.status
    output.status = False
    disconnect_all()
    output.status = store
    return os.linesep.join(msg)


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        print check_cluster() or "All OK"
