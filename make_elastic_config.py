#!/usr/bin/env python3

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


"""
Print out elasticsearch config lines for clustering.
Requests ip addresses of kuberdock pods from master,
set that ips for elastic zen.unicast cluster discovery.
Set host's IP as publish_host for elastic node.
The script uses following environment variables:
  MASTER - IP of kuberdock master host to retrieve list of nodes
  TOKEN - token for internal kuberdock user to get access to api server
  NODENAME - name of the current node to extract it's pod IP from unicast list

IMPORTANT: This script is for Python 3
"""
from __future__ import print_function

import os
import sys
import time

import requests


MASTER = os.environ.get('MASTER', 'master')
TOKEN = os.environ.get('TOKEN', '')
NODENAME = os.environ.get('NODENAME', '')

# Number of maximum retries to fetch own clusterIP address
# If it's not possible, then script will fail and the pod won't start.
MAX_RETRY_COUNT = 200
# Time in seconds to wait between retries
RETRY_PAUSE = 1


LOGS_POD_PREFIX = 'kuberdock-logs-'


def eprint(msg):
    print(msg, file=sys.stderr)


def discover_cluster(url, ips):
    """Function retrieves all existing logs pods from Kuberdock master,
    fills its service IP array, and finds service IP for the current pod.
    :param url: Full URL to send request for pods
    :param ips: list wich will be extended with found service IPs of logs pods
    :return: own service IP address, or None if self service IP is not found.
    """
    self_ip = None
    try:
        pods = requests.get(url, verify=False).json()['data']
    except Exception as err:
        eprint('Failed to get pods from: {}\n{}'.format(url, err))
        return self_ip

    for pod in pods:
        name = pod['name']
        if not name.startswith(LOGS_POD_PREFIX):
            continue
        if pod['status'] != 'running':
            continue

        _, hostname = name.split(LOGS_POD_PREFIX, 1)
        ip = pod.get('podIP', None)
        if not ip:
            continue
        if hostname == NODENAME:
            self_ip = ip
            # skip self in unicast.hosts
            continue
        ips.append(ip)
    return self_ip


node_ip = None
master_url = 'https://{}/api/podapi?token={}'.format(MASTER, TOKEN)

for i in range(MAX_RETRY_COUNT):
    cluster_ips = []
    eprint('Trying to get pods config. Iteration: {}'.format(i))
    node_ip = discover_cluster(master_url, cluster_ips)
    if node_ip is not None:
        break
    eprint('Failed to fetch own clusterIP on {} iteration'.format(i))
    time.sleep(RETRY_PAUSE)

if not node_ip:
    sys.exit('Failed to fetch own cluster IP. Exit.')

print('network.publish_host: {}'.format(node_ip))
print('network.bind_host: 0.0.0.0')

print('discovery.zen.ping.multicast.enabled: false')
print('discovery.zen.ping.unicast.hosts: [{}]'.format(
    ', '.join('"{}"'.format(ip) for ip in cluster_ips))
)
