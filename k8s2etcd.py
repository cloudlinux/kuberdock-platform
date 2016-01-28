#!/usr/bin/env python2

from __future__ import print_function
import json
import gevent
import logging
import logging.handlers
import requests
from datetime import datetime
from websocket import create_connection

logger = logging.getLogger('')
logger.setLevel(logging.DEBUG)
handler = logging.handlers.RotatingFileHandler(
    "/var/log/k8s2etcd.log", maxBytes=1048576, backupCount=10)
form = logging.Formatter('%(asctime)s %(name)-12s %(levelname)s:%(message)s')
handler.setFormatter(form)
logger.addHandler(handler)

watch_url = 'ws://127.0.0.1:8080/api/v1/pods?watch=true&resourceVersion={}'
list_url = 'http://127.0.0.1:8080/api/v1/pods'
etcd_url = 'http://127.0.0.1:4001/v2/keys/kuberdock/pod_states'


def prelist():
    """ Just get resourceVersion from list """
    res = requests.get(list_url)
    if res.ok:
        return res.json()['metadata']['resourceVersion']
    else:
        raise Exception("Error during pre list resource version")


def process(content):
    """ Put content to etcd with timestamp as key """
    ts = str((datetime.utcnow() - datetime.fromtimestamp(0)).total_seconds())
    requests.put('/'.join([etcd_url, ts]), data={'value': content})


resourceVersion = None
while True:
    try:
        if not resourceVersion:
            resourceVersion = prelist()
        logger.debug("start watch from {}".format(resourceVersion))
        ws = create_connection(watch_url.format(resourceVersion))
        while True:
            content = ws.recv()
            data = json.loads(content)
            if (data['type'].lower() == 'error' and
                    '401' in data['object']['message']):
                resourceVersion = None
                break
            resourceVersion = data['object']['metadata']['resourceVersion']
            logger.debug("new resourceVersion {}".format(resourceVersion))
            process(content)
    except KeyboardInterrupt:
        break
    except Exception as e:
        logger.exception('restarting')
        gevent.sleep(0.2)
