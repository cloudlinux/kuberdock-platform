import socket
import re

from .api import APIError

container_image_name = re.compile(r"^[a-zA-Z0-9]+[a-zA-Z0-9/:_!.\-]*$")
ipv4_addr = re.compile(r"((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)")

# http://stackoverflow.com/questions/1418423/the-hostname-regex
hostname = re.compile(r"^(?=.{1,255}$)[0-9A-Za-z](?:(?:[0-9A-Za-z]|-){0,61}[0-9A-Za-z])?(?:\.[0-9A-Za-z](?:(?:[0-9A-Za-z]|-){0,61}[0-9A-Za-z])?)*\.?$")

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
    if 'hostname' not in data:
        raise APIError('Hostname not provided')
    if len(data['hostname']) > 255:
        raise APIError('Hostname is longer than 255 symbols')
    if not hostname.match(data['hostname']):
        raise APIError('Invalid hostname')
    try:
        socket.gethostbyname(data['hostname'])
    except socket.error:
        raise APIError("Hostname can't be resolved. Check /etc/hosts file for correct minion records")
    # annotations - any
    # labels - any


def check_pod_data(data):
    if 'name' not in data:
        raise APIError('Pod name is not provided')
    if len(data['name']) > 255:
        raise APIError('Pod name is longer than 255 symbols')
    if not pod_name.match(data['name']):
        raise APIError('Invalid pod name')