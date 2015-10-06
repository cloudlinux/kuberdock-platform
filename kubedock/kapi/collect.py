"""
Module collect to gather and send usage case info back to developers
"""

import requests
import re
import subprocess
import json
from flask import current_app

from kubedock.settings import AWS, ID_PATH, STAT_URL, CEPH
from kubedock.api.users import get_users_collection
from kubedock.kapi.podcollection import PodCollection
from kubedock.updates.models import Updates
from kubedock.nodes.models import Node


def get_users_number():
    return len([u for u in get_users_collection()
                if u.get('rolename') == 'User'
                    and u.get('username') != 'kuberdock-internal'])

def get_pods():
    data = {}
    pods = PodCollection().get(False)
    data['total'] = len(pods)
    data['running'] = len([p for p in pods
        if p.get('status') != 'stopped'])
    return data


def get_updates():
    return [{u.fname: u.status} for u in Updates.query.all()]

def fetch_nodes():
    """
    Gets basic nodes data: IP address, cpu cores and memory
    """
    nodes = []
    for node in Node.query.all():
        nodes.append({'_ip': node.ip})
    return nodes


def extend_nodes(nodes):
    """
    For every node in list make cadvisor request to get additional info
    :param nodes: list --> list of nodes
    """
    fmt = 'http://{0}:4194/api/v1.3/machine'
    keys = ['filesystems', 'num_cores', 'memory_capacity', 'cpu_frequency_khz']

    for node in nodes:
        try:
            _ip = node.pop('_ip')
            r = requests.get(fmt.format(_ip))
            if r.status_code != 200:
                continue
            data = r.json()
            (node['disks'], node['cores'], node['memory'],
                node['clock']) = map(data.get, keys)
            node['nics'] = len(data.get('network_devices', []))
        except (requests.exceptions.ConnectionError, AttributeError):
            continue
    return nodes


def get_version(package, patt=re.compile(r"""(\d[\d\.\-]+\d)(?=\.?\D)""")):
    """
    Get RPM package version
    :param package: string -> RPM package name
    :param patt: object -> compiled regexp
    :return: string -> version of the given package or None if missing
    """
    try:
        rv = subprocess.check_output(['rpm', '-q', package])
        return patt.search(rv).group(1)
    except (subprocess.CalledProcessError, AttributeError):
        return 'unknown'


def read_or_write_id(data=None):
    """
    Read system ID from file or write it to file
    :param path: string -> path to file
    :param data: string -> new system ID to write
    :return: string -> retrieved id or None if
    """
    try:
        with open(ID_PATH, 'w' if data is None else 'r') as f:
            if data is None:
                return f.read().rstrip()
            f.write(data)
    except IOError:
        return

def get_installation_id():
    inst_id = read_or_write_id()
    if inst_id:
        return inst_id
    try:
        inst_id = subprocess.check_output(['dbus-uuidgen', '--get'])
        inst_id = inst_id.rstrip()
        read_or_write_id(inst_id)
        return inst_id
    except (subprocess.CalledProcessError, OSError):
        return


def collect(patt=re.compile(r"""-.*$""")):
    data = {}
    data['nodes'] = extend_nodes(fetch_nodes())
    for pkg in 'kubernetes-master', 'kuberdock':
        data[patt.sub('', pkg)] = get_version(pkg)
    data['installation-id'] = get_installation_id()
    data['aws'] = AWS
    data['ceph'] = CEPH
    data['users'] = get_users_number()
    data['pods'] = get_pods()
    data['updates'] = get_updates()
    return data

def send(data):
    r = requests.post(STAT_URL, json=json.dumps(data))
    if r.status_code != 200:
        current_app.logger.warn('could not upload stat')