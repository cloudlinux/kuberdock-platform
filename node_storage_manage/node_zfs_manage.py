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

"""The module provides commands to manage zfs volumes for localstorage backend.

It creates one zpool on top of specified block devices. Poll may be extended
with additional devices later.
This pool will be mounted to /var/lib/kuberdock/storage mountpoint.
Each created volume (do_add_volume) will be ZFS FS in this zpool with
specified size quota.

Requires working zfs commands on the host.

"""
from __future__ import absolute_import

import os
import re

from .common import (
    OK, ERROR, LOCAL_STORAGE_MOUNT_POINT, get_fs_usage, silent_call,
    get_subprocess_result, raise_cmd_error, get_path_relative_to_localstorage)

# Storage backend name, will be used in top wrapper (manage.py) messages.
VOLUME_MANAGE_NAME = 'ZFS'

# Volume group name for kuberdock storage
KD_ZPOOL_NAME = 'kdstorage00'


def do_add_volume(call_args):
    devices = call_args.devices
    return add_devices_to_localstorage(devices)


def _list_zpools():
    err_code, output = get_subprocess_result(
        ['zpool', 'list', '-H', '-o', 'name']
    )
    raise_cmd_error(err_code, output)
    return [name for name in output.split('\n') if name]


def init_kd_zpool(devices):
    """Creates and mounts Kuberdock zpool."""
    err_code, output = get_subprocess_result(
        ['zpool', 'create', '-f', KD_ZPOOL_NAME] + devices
    )
    raise_cmd_error(err_code, output)
    err_code, output = get_subprocess_result(
        ['zfs', 'set', 'mountpoint={}'.format(LOCAL_STORAGE_MOUNT_POINT),
         KD_ZPOOL_NAME]
    )
    raise_cmd_error(err_code, output)
    # Default recordsize is 128k. It is too large for supposed load type.
    # We want provide best performance for DB engines. Most of the apps use
    # mysql with Innodb engine which have 16k page size. MyIsam and Postgresql
    # have 8k page size which is also closer to 16k, than to 128k.
    # Above DB page sizes (16k, 8k) are default values.
    # More flexible (but more complicated) way - set recordsize for each PV,
    # depending of particular application.
    err_code, output = get_subprocess_result(
        ['zfs', 'set', 'recordsize=16k', KD_ZPOOL_NAME]
    )
    raise_cmd_error(err_code, output)


def extend_kd_zpool(devices):
    err_code, output = get_subprocess_result(
        ['zpool', 'add', '-f', KD_ZPOOL_NAME] + devices
    )
    raise_cmd_error(err_code, output)


def _get_zpool_properties(zpool_name):
    """Returns list of devices used in KD zpool with size.
    :return: dict {'device name': {'size': <size of device>}, ...}
    """
    devices = get_device_list(zpool_name)
    result = {}
    for dev in devices:
        err, output = get_subprocess_result(['blockdev', '--getsize64', dev])
        size = 0
        try:
            if not err:
                size = int(output.replace('\n', ''))
        except:
            pass
        result[dev] = {'size': size}
    return result


def get_device_list(zpool_name):
    """Returns list of devices used in KD storage zpool.
    """
    # This command will return simething like
    #   pool: kdstorage00
    # state: ONLINE
    # scan: none requested
    # config:
    #
    #   NAME        STATE     READ WRITE CKSUM
    #       kdstorage00  ONLINE       0     0     0
    #       sdc       ONLINE       0     0     0
    #       sdd       ONLINE       0     0     0
    #
    # We have to parse it output to extract devices
    err_code, output = get_subprocess_result(
        ['zpool', 'status', KD_ZPOOL_NAME]
    )
    raise_cmd_error(err_code, output)
    header_pattern = re.compile(r'^\s+' + zpool_name + r'\s+')
    device_string_pattern = re.compile(r'^\s+([\w\d\-_]+)\s+')
    # Parser states:
    #   initial parsing, no header had met
    state_init = 1
    #   header already passed, now expect strings with device names
    state_parse = 2
    state = state_init
    devices = []
    for line in output.split('\n'):
        if state == state_init:
            if header_pattern.match(line):
                state = state_parse
            continue
        if state == state_parse:
            m = device_string_pattern.match(line)
            if not m:
                continue
            dev = '/dev/' + m.group(1)
            if not os.path.exists(dev):
                continue
            devices.append(dev)
    return devices


def do_get_info(_):
    all_names = _list_zpools()
    if KD_ZPOOL_NAME not in all_names:
        return ERROR, {'message': 'KD zpool not found on the host'}

    dev_info = _get_zpool_properties(KD_ZPOOL_NAME)
    return OK, {
        'lsUsage': get_fs_usage(LOCAL_STORAGE_MOUNT_POINT),
        'zpoolDevs': dev_info
    }


def do_remove_storage(_):
    """Destroys zpool created for local storage.
    Returns tuple of success flag and list of devices which were used in
    destroyed zpool.
    Result of the function will be additionally processed, so it does not
    return readable statuses of performed operation.

    """
    return _perform_zpool_stop_operation('destroy')


def do_export_storage(_):
    """Prepares storage to be used in another host.
    Runs 'zpool export' command.
    Returns success flag and list of devices used in zpool, or error message
    in case of an error.
    """
    return _perform_zpool_stop_operation('export')


def do_import_storage(_):
    """Prepares imports a storage detached from another node.
    Executes 'zpool import' operation.
    """
    try:
        all_names = _list_zpools()
    except:
        return False, ('Unable to list ZFS pools. Maybe ZFS is not properly '
                       'installed yet, '
                       'skip this if this is during node cleanup process')
    if KD_ZPOOL_NAME in all_names:
        return False, 'Zpool {} already exists.'.format(KD_ZPOOL_NAME)
    try:
        silent_call(['zpool', 'import', '-f', KD_ZPOOL_NAME])
    except:
        return False, 'Failed to import zpool'

    try:
        silent_call(['zfs', 'mount', '-a'])
    except:
        return False, 'Failed to mount zfs volumes'

    try:
        devices = get_device_list(KD_ZPOOL_NAME)
    except:
        return (
            False,
            'Failed to get device list in zpool "{}"'.format(KD_ZPOOL_NAME)
        )
    return True, devices


def _perform_zpool_stop_operation(operation):
    """Performs one of operations on existing zpool:
    ('destroy', 'export'). Returns list of device names which was used by the
    zpool.
    """
    allowed_operations = ('destroy', 'export')
    if operation not in allowed_operations:
        return False, u'Invalid operation name: {}'.format(operation)

    try:
        all_names = _list_zpools()
    except Exception:
        return False, ('Unable to list ZFS pools. Maybe ZFS is not properly '
                       'installed yet, '
                       'skip this if this is during node cleanup process')
    if KD_ZPOOL_NAME not in all_names:
        return True, []
    try:
        devices = get_device_list(KD_ZPOOL_NAME)
    except:
        return (
            False,
            'Failed to get device list in zpool "{}"'.format(KD_ZPOOL_NAME)
        )
    try:
        silent_call(['zpool', operation, '-f', KD_ZPOOL_NAME])
        return True, devices
    except:
        return False, 'Failed to {} zpool {}'.format(operation, KD_ZPOOL_NAME)


def add_devices_to_localstorage(devices):
    """Initializes KD zpool: Creates it if it not exists. Adds devices to
    zpool.
    """
    all_names = _list_zpools()
    if KD_ZPOOL_NAME not in all_names:
        init_kd_zpool(devices)
    else:
        err_code, output = get_subprocess_result(
            ['zpool', 'add', '-f', KD_ZPOOL_NAME] + devices
        )
        raise_cmd_error(err_code, output)
    dev_info = _get_zpool_properties(KD_ZPOOL_NAME)
    return OK, {
        'lsUsage': get_fs_usage(LOCAL_STORAGE_MOUNT_POINT),
        'zpoolDevs': dev_info
    }


def full_volume_path_to_zfs_path(path):
    """Converts volume path in form '/var/lib/kuberdock/storage/123/pvname'
    to path that may used in zfs commands:
        'kdstorage00/123/pvname'
    It is assumed that incoming path is a subdirectory of
    /var/lib/kuberdock/storage - mountpoint of kuberdock zpool.

    """
    relative_path = get_path_relative_to_localstorage(path)
    zfs_path = '{}/{}'.format(KD_ZPOOL_NAME, relative_path)
    return zfs_path


def do_create_volume(call_args):
    """Creates zfs filesystem on specified path and sets size quota to it.
    :param call_args.path: relative (from KD storage dir) path to volume
    :param call_args.quota: FS quota for the volume
    :return: full path to created volume
    """
    path = call_args.path
    quota_gb = call_args.quota
    zfs_path = full_volume_path_to_zfs_path(path)
    err_code, output = get_subprocess_result(['zfs', 'create', '-p', zfs_path])
    raise_cmd_error(err_code, output)
    err_code, output = get_subprocess_result(
        ['zfs', 'set', 'quota={}G'.format(quota_gb), zfs_path]
    )
    raise_cmd_error(err_code, output)
    return OK, {'path': path}


def do_remove_volume(call_args):
    path = call_args.path
    zfs_path = full_volume_path_to_zfs_path(path)

    err_code, output = get_subprocess_result([
        'zfs', 'destroy', '-r', '-f', zfs_path
    ])
    raise_cmd_error(err_code, output)


def do_resize_volume(call_args):
    path = call_args.path
    quota_gb = call_args.new_quota
    zfs_path = full_volume_path_to_zfs_path(path)
    err_code, output = get_subprocess_result(
        ['zfs', 'set', 'quota={}G'.format(quota_gb), zfs_path]
    )
    raise_cmd_error(err_code, output)
    return OK, {'path': path}
