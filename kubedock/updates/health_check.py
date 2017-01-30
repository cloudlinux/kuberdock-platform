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
from kubedock.updates.helpers import setup_fabric
from kubedock.settings import KUBERDOCK_INTERNAL_USER
from kubedock.utils import POD_STATUSES


SSH_TIMEOUT = 15
MAX_DISK_PERCENTAGE = 90
MESSAGES = {
    'disk': "\tLow disk space: {}",
    'services': "\tSome services in wrong state: {}",
    'ntp': "\tTime not synced. Please either synchronize it manually or wait several minutes (up to 20) and repeat",
    NODE_STATUSES.running: "\tNode not running in kubernetes",
    'ssh': "\tCan't access node from master through ssh",
    'pods': "Some internal pods in wrong state: {}",
    NODE_STATUSES.pending: "\tThe node is under installation. Please wait for its completion to upgrade"
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
    try:
        status['ntp'] = False
        status['services'] = False
        # AC-3105 Fix. Check if master can connect to node via ssh.
        if can_ssh_to_host(hostname):
            rv = run('ntpstat', quiet=True, timeout=SSH_TIMEOUT)
            if rv.succeeded:
                status['ntp'] = True
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
    nodes_status = {
        node['hostname']: get_node_state(node) for node in nodes}
    return nodes_status


def get_internal_pods_state():
    ki = User.filter_by(username=KUBERDOCK_INTERNAL_USER).first()
    pod_statuses = {}
    for pod in PodCollection(ki).get(as_json=False):
        pod_statuses[pod['name']] = pod['status'] == POD_STATUSES.running
    return pod_statuses


def get_disk_usage(local=True):
    if local:
        rv = subprocess.check_output(['df', '--output=source,pcent,target'])
    else:
        rv = run("df --output=source,pcent,target", quiet=True,
                 timeout=SSH_TIMEOUT)
    lines = rv.splitlines()[1:]
    r = re.compile('((?!tmpfs|cdrom|SEPID).)*$')
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
    pendings = [get_kuberdock_logs_pod_name(node)
                for node, state in states.items() if
                NODE_STATUSES.pending in state]
    if states and len(pendings) != len(states):
        try:
            pod_states = get_internal_pods_state()
            stopped = [pod for pod, status in pod_states.items()
                       if pod not in pendings and not status]
            if stopped:
                msg.append(MESSAGES['pods'].format(', '.join(stopped)))
        except (SystemExit, Exception) as e:
            msg.append("Can't get internal pods states because of {}".format(
                e.message))
    return os.linesep.join(msg)


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
