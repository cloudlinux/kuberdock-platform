#!/usr/bin/env python3

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

import os

import requests


MASTER = os.environ.get('MASTER', 'master')
TOKEN = os.environ.get('TOKEN', '')
NODENAME = os.environ.get('NODENAME', '')

pods = requests.get('https://{}/api/podapi?token={}'.format(MASTER, TOKEN),
                    verify=False).json()['data']

node_ip = None
cluster_ips = []

for pod in pods:
    name = pod['name']
    if not name.startswith('kuberdock-logs-'):
        continue
    if pod['status'] != 'running':
        continue

    _, hostname = name.split('kuberdock-logs-', 1)
    ip = pod['podIP']
    if hostname == NODENAME:
        node_ip = ip
        # skip self in unicast.hosts
        continue
    if ip:
        cluster_ips.append(ip)
    else:
        cluster_ips.append(hostname)

if node_ip:
    print('network.publish_host: {}'.format(node_ip))
print('network.bind_host: 0.0.0.0')

print('discovery.zen.ping.multicast.enabled: false')
print('discovery.zen.ping.unicast.hosts: [{}]'.format(
    ', '.join('"{}"'.format(ip) for ip in cluster_ips))
)
