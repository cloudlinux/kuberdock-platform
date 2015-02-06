import socket; socket.setdefaulttimeout(2)
import re

from .api import APIError

container_image_name = re.compile(r"^[a-zA-Z0-9]+[a-zA-Z0-9/:_!.\-]*$")
ipv4_addr = re.compile(r"((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)")
hostname = re.compile(r"^[a-zA-Z0-9]+[a-zA-Z0-9.\-]*$")
pod_name = re.compile(r"^[a-zA-Z0-9]+[a-zA-Z0-9._\- ]*$")


def check_int_id(id):
    try:
        int(id)
    except ValueError:
        raise APIError('Invalid id')


def check_container_image_name(searchkey):
    if len(searchkey) > 128:
        raise APIError('Image name is longer than 128 symbols')
    if not container_image_name.match(searchkey):
        raise APIError('Invalid container image name')


def check_minion_data(data):
    if not ('ip' in data and ipv4_addr.match(data['ip'])):
        raise APIError('Invalid ip address')
    if not ('hostname' in data and hostname.match(data['hostname'])):
        raise APIError('Invalid hostname')
    if len(data['hostname']) > 255:
        raise APIError('Hostname is longer than 255 symbols')
    try:
        ip = socket.gethostbyname(data['hostname'])
    except socket.error:
        raise APIError("Hostname can't be resolved")
    if data['ip'] != ip:
        raise APIError("Hostname ip don't match given ip")
    # annotations - any
    # labels - any


def check_pod_data(data):
    if 'name' not in data:
        raise APIError('Pod name is not provided')
    if len(data['name']) > 255:
        raise APIError('Pod name is longer than 255 symbols')
    if not pod_name.match(data['name']):
        raise APIError('Invalid pod name')