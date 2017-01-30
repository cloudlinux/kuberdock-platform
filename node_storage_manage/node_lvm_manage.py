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

"""The module provides commands to manage lvm volumes for localstorage backend.

It creates one volume group with specified block devices (may be extended
with additional devices later), creates one logical volume with all available
space in the volume group, formats it to XFS FS, mounts it to
/var/lib/kuberdock/storage
All created volumes will be simple subdirectories in this mounpoint,
limited in size by xfs quota.

Requires additional python module 'lvm' to be installed.

"""
from __future__ import absolute_import

import os
import re
import tempfile
import shutil

import lvm

from .common import (
    OK, ERROR, silent_call, LOCAL_STORAGE_MOUNT_POINT, get_subprocess_result,
    raise_cmd_error)

# Storage backend name, will be used in top wrapper (manage.py) messages.
VOLUME_MANAGE_NAME = 'LVM'


# Volume group name for kuberdock storage
KD_VG_NAME = 'kdstorage00'
# Logical volume name for KD storage
KD_LV_NAME = 'kdls00'

FSLIMIT_PATH = '/var/lib/kuberdock/scripts/fslimit.py'


def do_add_volume(call_args):
    devices = call_args.devices
    return add_devices_to_localstorage(devices)


def do_get_info(_):
    all_names = lvm.listVgNames()
    if KD_VG_NAME not in all_names:
        return ERROR, {'message': 'KD volume group not found on the host'}
    vg = lvm.vgOpen(KD_VG_NAME, 'r')
    try:
        pvs = {item.getName(): item for item in vg.listPVs()}
        pv_info = {
            key: {'size': item.getDevSize()}
            for key, item in pvs.iteritems()
        }
    finally:
        vg.close()

    return OK, {
        'lsUsage': get_fs_usage(LOCAL_STORAGE_MOUNT_POINT),
        'PV': pv_info
    }


def do_remove_storage(_):
    """Destroys logical volume and volume group created for local storage.
    Returns tuple of success flag and list of devices which were used in
    destroyed VG.
    Result of the function will be additionally processed, so it does not
    return readable statuses of performed operation.

    """
    all_names = lvm.listVgNames()
    if KD_VG_NAME not in all_names:
        return True, []
    vg = lvm.vgOpen(KD_VG_NAME, 'w')
    try:
        silent_call(['umount', '-f', LOCAL_STORAGE_MOUNT_POINT])
        pvs = [item.getName() for item in vg.listPVs()]
        for lv in vg.listLVs():
            lv.deactivate()
            lv.remove()
        vg.remove()
        remove_ls_mount()
        return True, pvs
    except Exception as err:
        return False, u'Exception: {}'.format(err)
    finally:
        vg.close()


def remove_ls_mount():
    save_file = '/etc/fstab.kdsave'
    fstab = '/etc/fstab'
    pattern = re.compile(r'^[^#].*' + LOCAL_STORAGE_MOUNT_POINT)

    temp_fd, temp_name = tempfile.mkstemp()
    with os.fdopen(temp_fd, 'w') as fout, open(fstab, 'r') as fin:
        for line in fin:
            if pattern.match(line):
                continue
            fout.write(line)
    if os.path.exists(save_file):
        os.remove(save_file)
    os.rename(fstab, save_file)
    os.rename(temp_name, fstab)


def add_devices_to_localstorage(devices):
    """Initializes KD volume group: Creates vg if it not exists, activates it
    if not active. Adds devices to VG.
    """
    all_names = lvm.listVgNames()
    if KD_VG_NAME not in all_names:
        vg = lvm.vgCreate(KD_VG_NAME)
    else:
        vg = lvm.vgOpen(KD_VG_NAME, 'w')
    try:
        pvs = {item.getName(): item for item in vg.listPVs()}
        lv = None
        for dev in devices:
            if dev in pvs:
                continue
            lvm.pvCreate(dev)
            vg.extend(dev)
            new_pv = [
                item for item in vg.listPVs() if item.getName() == dev
            ][0]
            pvs[dev] = new_pv
        for item in vg.listLVs():
            if item.getName() == KD_LV_NAME:
                lv = item
                break
        #dev = os.path.join('/dev', KD_VG_NAME, KD_LV_NAME)
        if not os.path.isdir(LOCAL_STORAGE_MOUNT_POINT):
            os.makedirs(LOCAL_STORAGE_MOUNT_POINT)

        if not lv:
            lv = vg.createLvLinear(KD_LV_NAME, vg.getFreeSize())
            dev = lv.getProperty('lv_path')[0]
            ok, message = make_fs(dev)
            if not ok:
                return ERROR, {'message': message}
        else:
            dev = lv.getProperty('lv_path')[0]
            if vg.getFreeSize():
                lv.resize(lv.getSize() + vg.getFreeSize())
        if not is_mounted(LOCAL_STORAGE_MOUNT_POINT):
            ok, message = mount(dev, LOCAL_STORAGE_MOUNT_POINT)
            if not ok:
                return ERROR, {'message': message}
        extend_fs_size(LOCAL_STORAGE_MOUNT_POINT)
        pv_info = {
            key: {'size': item.getDevSize()}
            for key, item in pvs.iteritems()
        }

    finally:
        vg.close()
    make_permanent_mount(dev, LOCAL_STORAGE_MOUNT_POINT)

    return OK, {
        'lsUsage': get_fs_usage(LOCAL_STORAGE_MOUNT_POINT),
        'PV': pv_info
    }


def get_fs_usage(mountpoint):
    st = os.statvfs(mountpoint)
    return {
        'size': st.f_frsize * st.f_blocks,
        'available': st.f_frsize * st.f_bavail
    }


def make_fs(device):
    """Creates filesystem (XFS) on given device
    Returns tuple of success flag and error message (if creation was failed)
    """
    res = silent_call(['mkfs.xfs', device])
    if res:
        return False, 'Failed to mkfs on {}, exit code: {}'.format(device, res)
    return True, None


def is_mounted(mountpoint):
    """Returns True if some volume is mounted to the mountpoint,
    otherwise returns False.
    """
    res = silent_call(['grep', '-q', mountpoint, '/proc/mounts'])
    return not res


def mount(device, mountpoint):
    """Mounts given device to mount point.
    """
    res = silent_call(['mount', '-o', 'prjquota', device, mountpoint])
    if res:
        return (
            False,
            'Failed to mount {} to {}. Exit code: {}'.format(
                device, mountpoint, res)
        )
    return True, None


def extend_fs_size(mountpoint):
    """Extends FS size to max available size."""

    res = silent_call(['xfs_growfs', mountpoint])
    if res:
        return False, 'Failed to extend {}. Exit code: {}'.format(
            mountpoint, res
        )
    return True, None


def make_permanent_mount(device, mountpoint):
    # Check it is not already in fstab
    fstab = '/etc/fstab'
    res = silent_call(['egrep', '-q', '^[^#].*{}'.format(mountpoint), fstab])
    if not res:
        return
    with open(fstab, 'a') as fout:
        fout.write('\n{} {}    xfs    defaults,prjquota 0 0\n'.format(
            device, mountpoint))


def do_create_volume(call_args):
    """Creates zfs filesystem on specified path and sets size quota to it.
    :param call_args.path: relative (from KD storage dir) path to volume
    :param call_args.quota: FS quota for the volume
    :return: full path to created volume
    """
    full_path = call_args.path
    quota_gb = call_args.quota

    err_code, output = get_subprocess_result(['mkdir', '-p', full_path])
    raise_cmd_error(err_code, output)

    err_code = silent_call(
        ['/usr/bin/env', 'python2', FSLIMIT_PATH, 'storage',
         '{0}={1}g'.format(full_path, quota_gb)]
    )
    if err_code:
        raise_cmd_error(err_code, 'Failed to set XFS quota')
    return OK, {'path': full_path}


def do_remove_volume(call_args):
    path = call_args.path
    shutil.rmtree(path, True)


def do_resize_volume(call_args):
    path = call_args.path
    quota_gb = call_args.new_quota
    err_code = silent_call(
        ['/usr/bin/env', 'python2', FSLIMIT_PATH, 'storage',
         '{0}={1}g'.format(path, quota_gb)]
    )
    if err_code:
        raise_cmd_error(err_code, 'Failed to set XFS quota')
    return OK, {'path': path}
