#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
STEP #0. Loading `rbd` kernel module.
STEP #1. Extracting secret key from keyring via `ceph-authtool`
STEP #2. Gathering all images for specified pool. It uses `rdb ls` for
that. All steps below would be applied for each of them.
STEP #3. Cloning image for the glory of consistency. It would be done
through snapshots mechanism: create snapshot -> protect it -> clone it
to temporary image.
STEP #4. Adding rbd block devices. Required `rbd` kernel module. This
step adds /dev/rdbN devices.
STEP #5. FS check. Block device added above would be checked for
structure errors. This step added because of snapshoting not stopped
images. Since it used xfs for images fsck tool replaced with
`xfs_repair`.
STEP #6. Mounting device as ordinary storage.
STEP #7. Archiving all files from mountpoint.
STEP #8. Cleanup. All temporary created during backup images, snapshots,
mounted devices will be removed.


NOTE#1 All images from specified pool will be proceed. There is no
options to to apply any filters for now.
NOTE#2 There are some additional external dependencies. (e.g. ceph-common)
NOTE#3 Step 3 would be fail for images in old format.
NOTE#4 Client == namespace == pool
NOTE#5 Ceph user should have 'class-read object_prefix rbd_children` right

"""

import argparse
import datetime
import logging
import os
import random
import string
import subprocess
import sys
import zipfile
from contextlib import contextmanager

LOCKFILE = '/var/lock/kd-ceph-backup.lock'

logger = logging.getLogger("kd_master_backup")
logger.setLevel(logging.INFO)

stdout_handler = logging.StreamHandler()
logger.addHandler(stdout_handler)

formatter = logging.Formatter(
    "[%(asctime)-15s - %(name)-6s - %(levelname)-8s]"
    " %(message)s")
stdout_handler.setFormatter(formatter)


class BackupError(Exception):
    pass


def zipdir(path, ziph):
    for root, dirs, files in os.walk(path):
        for fn in files:
            full_fn = os.path.join(root, fn)
            ziph.write(full_fn, os.path.relpath(full_fn, path))


def lock(lockfile):
    def decorator(clbl):
        def wrapper(*args, **kwargs):
            try:
                # Create or fail
                os.open(lockfile, os.O_CREAT | os.O_EXCL)
            except OSError:
                raise BackupError(
                    "Another backup/restore process already running."
                    " If it is not, try to remove `{0}` and "
                    "try again.".format(lockfile))
            try:
                result = clbl(*args, **kwargs)
            finally:
                os.unlink(lockfile)
            return result

        return wrapper

    return decorator


def get_local_keyring_path(keyring):
    # Don't blame me for this hardcode. There 26 more of them scattered
    # all over the project. So
    # TODO: Pick out all these cases to one place.
    CONF_PATH = '/var/lib/kuberdock/conf'
    basename = os.path.basename(keyring)
    return os.path.join(CONF_PATH, basename)


def do_ceph_backup(backup_dir, pool, monitors, keyring, auth_user, skip_errors,
                   callback, **kwargs):
    """ Backup all CEPH drives for pool
    """
    try:
        from kubedock import ceph_settings, settings
        if any([pool, monitors, keyring, auth_user]):
            logger.warning('Ceph settings found. Some of passed parameters'
                           ' may be overriten.')
        auth_user = getattr(ceph_settings, 'CEPH_CLIENT_USER', auth_user)
        monitors = getattr(ceph_settings, 'MONITORS', monitors)
        keyring_path = getattr(ceph_settings, 'CEPH_KEYRING_PATH', None)
        if keyring_path is not None:
            keyring = get_local_keyring_path(keyring_path)
        pool = getattr(settings, 'CEPH_POOL_NAME', pool)
    except ImportError:
        logger.warning("CEPH settings for kuberdock was not found.")

    logger.debug({'pool': pool, 'monitors': monitors, 'keyring': keyring,
                 'auth_user': auth_user})

    mountpoint = os.environ.get('KD_CEPH_BACKUP_MOUNTPOINT', '/mnt')
    if not os.path.exists(mountpoint):
        os.makedirs(mountpoint)
    if os.path.ismount(mountpoint):
        raise BackupError("Mountpoint `{0}` already mounted. Please, "
                          "release it or specify free mount point via"
                          " KD_CEPH_BACKUP_MOUNTPOINT".format(mountpoint))

    if not all([pool, monitors, keyring, auth_user]):
        raise BackupError("Insufficient ceph parameters")

    rbd_with_creds = ['rbd', '-n', 'client.{0}'.format(auth_user),
                      '--keyring={0}'.format(keyring), '-m', monitors]

    def get_image_format(image_name):
        info_info_raw = subprocess.check_output(
            rbd_with_creds + ['info', '{0}/{1}'.format(pool, drive)])
        return int(info_info_raw.split('\n')[4].split(":")[1])

    @contextmanager
    def clone(drive):
        if get_image_format(drive) < 2:
            raise BackupError(
                "Looks like your Ceph cluster uses images format 1. We "
                "require image format 2 to do a backup. Please migrate "
                "cluster to image format 2 yourself (http://ceph.com/planet/"
                "convert-rbd-to-format-v2/), or contact support to get help.")

        snap_id = ''.join(random.sample(string.ascii_letters + string.digits, 9))
        snap = '{0}/{1}@snap-{2}'.format(pool, drive, snap_id)
        child = '{0}/{1}_child'.format(pool, drive)
        logger.debug("Snapshot `{0}` creating".format(snap))
        subprocess.check_call(rbd_with_creds + ['snap', 'create', snap])
        logger.debug("Snapshot `{0}` protecting".format(snap))
        subprocess.check_call(rbd_with_creds + ['snap', 'protect', snap])
        logger.debug("Snapshot `{0}` cloning to {1}".format(snap, child))
        subprocess.check_call(rbd_with_creds + ['clone', snap, child])
        try:
            yield drive + '_child'
        finally:
            logger.debug("Child image `{0}` removing".format(child))
            subprocess.check_call(rbd_with_creds + ['rm', child])
            logger.debug("Snapshot `{0}` unprotecting".format(snap))
            subprocess.check_call(rbd_with_creds + ['snap', 'unprotect',
                                                    snap])
            logger.debug("Snapshot `{0}` removing".format(snap))
            subprocess.check_call(rbd_with_creds + ['snap', 'rm', snap])

    def find_device_by_name(name):
        devices = '/sys/bus/rbd/devices/'
        for device in os.listdir(devices):
            with open(os.path.join(devices, device, 'name'), 'r') as fd_name:
                if fd_name.read().strip() == name:
                    return device

    @contextmanager
    def rbd_device_context(drive):
        with open('/sys/bus/rbd/add', 'wb') as fd:
            connection_str = "{0} name={1},secret={2} {3} {4}".format(
                monitors, auth_user, secret, pool, drive)
            logger.debug("RDB device connection string: '{0}'".format(
                connection_str))
            fd.write(connection_str)

        device_index = find_device_by_name(drive)
        if device_index is None:
            raise Exception("No such device")
        try:
            yield '/dev/rbd{0}'.format(device_index)
        finally:
            # remove rbd device
            with open('/sys/bus/rbd/remove', 'wb') as fd:
                fd.write(device_index)

    @contextmanager
    def mount_context(device):
        subprocess.check_call(['mount', device, mountpoint])
        try:
            yield mountpoint
        finally:
            subprocess.check_call(['umount', mountpoint])

    def fsck(device):
        # mount/unmount needs to replay journal
        logger.debug('File system `{0}` check.'.format(device))
        subprocess.check_call(['mount', device, mountpoint])
        subprocess.check_call(['umount', mountpoint])
        with open(os.devnull, 'wb') as devnull:
            subprocess.check_call(['xfs_repair', device], stdout=devnull,
                                  stderr=devnull)

    def handle(handler, result):
        try:
            subprocess.check_call("{0} {1}".format(callback, result),
                                  shell=True)
        except subprocess.CalledProcessError as err:
            raise BackupError(
                "Callback handler has failed with `{0}`".format(err))

    @lock(LOCKFILE)
    def run_backup(drive):
        with clone(drive) as drive:
            with rbd_device_context(drive) as device:
                fsck(device)
                with mount_context(device) as src:
                    timestamp = datetime.datetime.today().isoformat()
                    result = os.path.join(backup_dir, "{0}-{1}.zip".format(
                        drive, timestamp))
                    tmp_result = os.path.join(backup_dir, "{0}-{1}.zip".format(
                        drive, timestamp))
                    try:
                        with zipfile.ZipFile(tmp_result, 'w',
                                             zipfile.ZIP_DEFLATED) as zf:
                            zipdir(src, zf)
                    except IOError:
                        if os.path.exists(tmp_result):
                            os.remove(tmp_result)
                        raise
                    os.rename(tmp_result, result)
                    logger.info('Backup created: {0}'.format(result))
                    if callback:
                        handle(callback, result)

    logger.info('Gathering images list')
    drives = subprocess.check_output(rbd_with_creds + ['ls', pool]).split()
    logger.info('Found drives: {0}'.format(drives))

    # up kernel modules
    subprocess.check_call(['modprobe', 'rbd'])

    secret = subprocess.check_output(['ceph-authtool', '--print-key', keyring,
                                      '-n', 'client.{0}'.format(auth_user)])
    logger.debug("Extractred secret key: '{0}'".format(secret))

    for drive in drives:
        logger.info('Proceed drive {0}'.format(drive))
        try:
            run_backup(drive)
        except BackupError as err:
            if not skip_errors:
                raise
            logger.warning("Drive `{0}` not backuped due error '{1}'. "
                           "Skipped".format(drive, err))


def parse_args(args):
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-v', '--verbose', help='Verbose (debug) logging',
                       action='store_const', const=logging.DEBUG,
                       dest='loglevel')
    group.add_argument('-q', '--quiet', help='Silent mode, only log warnings',
                       action='store_const', const=logging.WARN,
                       dest='loglevel')
    parser.add_argument("-s", '--skip', action='store_true',
                        dest='skip_errors',
                        help="Do not stop if one steps is failed")

    parser.add_argument(
        'backup_dir', help="Destination for all created files")
    parser.add_argument('-p', '--pool', help="source pool name")
    parser.add_argument('-m', '--monitors', help="monitors to connect")
    parser.add_argument('-k', '--keyring')
    parser.add_argument('-n', '--id', dest='auth_user', help="auth user")
    parser.add_argument("-e", '--callback',
                        help='Callback for each backup file (backup path '
                        'passed as a 1st arg)')
    parser.set_defaults(func=do_ceph_backup)

    return parser.parse_args(args)


def main():
    if os.getuid() != 0:
        raise Exception('Root permissions are required to run this script')

    args = parse_args(sys.argv[1:])
    logger.setLevel(args.loglevel or logging.INFO)

    try:
        args.func(**vars(args))
    except BackupError as err:
        logger.error(err)
        exit(1)


if __name__ == '__main__':
    main()
