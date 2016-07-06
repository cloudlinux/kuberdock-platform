#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

import sys
import datetime
import os
import argparse
import subprocess
import logging
import zipfile

from contextlib import contextmanager

logger = logging.getLogger("kd_master_backup")
logger.setLevel(logging.INFO)

stdout_handler = logging.StreamHandler()
logger.addHandler(stdout_handler)

formatter = logging.Formatter(
    "[%(asctime)-15s - %(name)-6s - %(levelname)-8s]"
    " %(message)s")
stdout_handler.setFormatter(formatter)


class BackupException(Exception):
    pass


def zipdir(path, ziph):
    for root, dirs, files in os.walk(path):
        for fn in files:
            full_fn = os.path.join(root, fn)
            ziph.write(full_fn, os.path.relpath(full_fn, path))


def mountpoint_is_busy(mountpoint):
    try:
        subprocess.check_call(['mountpoint', '-q', mountpoint])
    except subprocess.CalledProcessError:
        return False
    return True


def do_ceph_backup(backup_dir, pool, monitors, keyring, auth_user, skip_errors,
                   **kwargs):
    """ Backup all CEPH drives for pool
    """
    try:
        from kubedock import ceph_settings, settings
        auth_user = getattr(ceph_settings, 'CEPH_CLIENT_USER', auth_user)
        monitors = getattr(ceph_settings, 'MONITORS', monitors)
        keyring = getattr(ceph_settings, 'CEPH_KEYRING_PATH', keyring)
        pool = getattr(settings, 'CEPH_POOL_NAME', pool)
    except ImportError:
        logger.warning("CEPH settings for kuberdock was not found.")

    mountpoint = os.environ.get('KD_CEPH_BACKUP_MOUNTPOINT', '/mnt')
    if not os.path.exists(mountpoint):
        raise BackupException("Mountpoint `{0}` not exists. Please, "
                              "create it or specify free mount point via"
                              " KD_CEPH_BACKUP_MOUNTPOINT".format(mountpoint))
    if mountpoint_is_busy(mountpoint):
        raise BackupException("Mountpoint `{0}` already mounted. Please, "
                              "release it or specify free mount point via"
                              " KD_CEPH_BACKUP_MOUNTPOINT".format(mountpoint))

    logger.info([pool, monitors, keyring, auth_user])
    if not all([pool, monitors, keyring, auth_user]):
        raise BackupException("Insufficient ceph parameters")

    rbd_with_creds = ['rbd', '-n', 'client.{0}'.format(auth_user),
                      '--keyring={0}'.format(keyring), '-m', monitors]

    def get_image_format(image_name):
        info_info_raw = subprocess.check_output(
            rbd_with_creds + ['info', '{0}/{1}'.format(pool, drive)])
        return int(info_info_raw.split('\n')[4].split(":")[1])

    @contextmanager
    def clone(drive):
        if get_image_format(drive) < 2:
            raise BackupException(
                "Looks like your Ceph cluster uses images format 1. We "
                "require image format 2 to do a backup. Please migrate "
                "cluster to image format 2 yourself (http://ceph.com/planet/"
                "convert-rbd-to-format-v2/), or contact support to get help.")

        snap = '{0}/{1}@snap4'.format(pool, drive)
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
        except BackupException as err:
            if not skip_errors:
                raise
            logger.warning("Drive `{0}` not backuped due error '{1}'. Skipped".format(
                drive, err))


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
    parser.set_defaults(func=do_ceph_backup)

    return parser.parse_args(args)


def main():
    if os.getuid() != 0:
        raise Exception('Root permissions are required to run this script')

    args = parse_args(sys.argv[1:])
    logger.setLevel(args.loglevel or logging.INFO)

    try:
        args.func(**vars(args))
    except BackupException as err:
        logger.error(err)
        exit(1)


if __name__ == '__main__':
    main()
