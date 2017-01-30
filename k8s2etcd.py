#!/usr/bin/env python2

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


import json
import time
import logging
import requests
from datetime import datetime
from websocket import create_connection

logger = logging.getLogger()

attempts = 3
attempt_timeout = 1
index_file = '/var/lib/kuberdock/k8s2etcd_resourceVersion'
loop_timeout = 0.2

watch_url = 'ws://127.0.0.1:8080/api/v1/pods?watch=true&resourceVersion={}'
list_url = 'http://127.0.0.1:8080/api/v1/pods'
etcd_url = 'http://127.0.0.1:4001/v2/keys/kuberdock/pod_states'


def store(resource_version):
    with open(index_file, 'w') as f:
        f.write('{0:d}'.format(int(resource_version)))


def get():
    try:
        with open(index_file) as f:
            rv = int(f.read())
            return rv
    except:
        logger.debug("Can't get saved resourceVersion")


def prelist():
    """ Just get resourceVersion from list """
    res = requests.get(list_url)
    if res.ok:
        return int(res.json()['metadata']['resourceVersion'])
    else:
        raise Exception("Error during pre list resource version")


def process(content):
    """ Put content to etcd with timestamp as key """
    ts = str((datetime.utcnow() - datetime.fromtimestamp(0)).total_seconds())
    for i in range(attempts):
        try:
            requests.put('/'.join([etcd_url, ts]), data={'value': content})
            break
        except:
            logger.exception("{}: Can't process event {}".format(i, content))
            time.sleep(attempt_timeout)
    else:
        logger.error("Can't process event {}, skipping...".format(content))


resourceVersion = get()
while True:
    try:
        if resourceVersion is None:
            resourceVersion = prelist()
        else:
            resourceVersion = min(resourceVersion, prelist())
        logger.info("start watch from {}".format(resourceVersion))
        ws = create_connection(watch_url.format(resourceVersion))
        while True:
            content = ws.recv()
            data = json.loads(content)
            if (data['type'].lower() == 'error' and
                    '401' in data['object']['message']):
                resourceVersion = None
                break
            process(content)
            resourceVersion = data['object']['metadata']['resourceVersion']
            logger.debug("new resourceVersion {}".format(resourceVersion))
            store(resourceVersion)
    except KeyboardInterrupt:
        break
    except Exception as e:
        logger.exception('restarting')
        time.sleep(loop_timeout)
