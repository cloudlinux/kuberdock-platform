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
Node backup script
"""

import sys
import datetime
import os
import argparse
import subprocess
import logging
import tarfile
import random
import string
from contextlib import contextmanager

logger = logging.getLogger("kd_master_backup")
logger.setLevel(logging.INFO)

stdout_handler = logging.StreamHandler()
logger.addHandler(stdout_handler)

formatter = logging.Formatter(
    "[%(asctime)-15s - %(name)-6s - %(levelname)-8s]"
    " %(message)s")
stdout_handler.setFormatter(formatter)


STORAGE_LOCATION = '/var/lib/kuberdock/storage/'
LOCKFILE = '/var/lock/kd-node-backup.lock'


def lock(lockfile):
    def decorator(clbl):
        def wrapper(*args, **kwargs):
            try:
                # Create or fail
                os.open(lockfile, os.O_CREAT | os.O_EXCL)
            except OSError:
                raise BackupError("Another backup process already running."
                                  " If it is not, try to remove `{0}` and "
                                  "try again.".format(lockfile))
            try:
                result = clbl(*args, **kwargs)
            finally:
                os.unlink(lockfile)
            return result

        return wrapper

    return decorator


def iterate_src(src):
    cmd = ['find', src, '-printf', '%T@ %p\n']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out = subprocess.Popen(['sort', '-nr'], stdin=proc.stdout,
                           stdout=subprocess.PIPE)
    for line in iter(out.stdout.readline, ''):
        ts, fn = line.split(' ', 1)
        logger.debug([ts, fn])
        yield fn.strip()


class BackupError(Exception):
    pass


class NonZFSException(Exception):
    pass


def get_zfs_mountpoints():
    result_raw = subprocess.check_output(["zfs", "list", "-H",
                                          "-o", "mountpoint,name"])
    return dict(a.split('\t') for a in result_raw.split('\n') if a)


def make_tar_backup(name, src, dst, skip_errors=False):
    """ Make a backup by archiving all files in src
    to tar.gz  located in dst
    """
    result = os.path.join(dst, "{0}.tar.gz".format(name))
    tmp_result = result + '.incomplete'
    logger.debug({"dst": result})

    with tarfile.open(tmp_result, "w:gz") as tgzf:
        for fn in iterate_src(src):
            try:
                logger.debug([fn, os.path.relpath(fn, src)])
                tgzf.add(fn, arcname=os.path.relpath(fn, src))
            except (IOError, OSError) as err:
                if not skip_errors:
                    if os.path.exists(tmp_result):
                        os.remove(tmp_result)
                    raise
                logger.warning("File `{0}` backup skipped due to "
                               "error `{1}`. Skipped".format(fn, err))
    os.rename(tmp_result, result)
    return result


@contextmanager
def mount_context(device):
    if device is None:
        yield None
        return
    mountpoint = os.environ.get('KD_CEPH_BACKUP_MOUNTPOINT', '/mnt')
    if not os.path.exists(mountpoint):
        os.makedirs(mountpoint)
    if os.path.ismount(mountpoint):
        raise BackupError("Mountpoint `{0}` already mounted. Please, "
                          "release it or specify free mount point via"
                          " KD_CEPH_BACKUP_MOUNTPOINT".format(mountpoint))
    subprocess.check_call(['mount', '-t', 'zfs', device, mountpoint])
    try:
        yield mountpoint
    finally:
        subprocess.check_call(['umount', mountpoint])


@contextmanager
def zfs_snapshot(src):
    try:
        zfs_map = get_zfs_mountpoints()
    except OSError:
        raise NonZFSException("ZFS not installed")

    logger.debug("zfs map: {}".format(zfs_map))
    if src not in zfs_map:
        raise NonZFSException("`src` is not ZFS volume")

    name = zfs_map[src]
    snap_id = ''.join(random.sample(string.ascii_letters + string.digits, 9))
    snap_name = '@'.join([name, snap_id])
    subprocess.check_call(["zfs", "snap", snap_name])
    subprocess.check_call(["zfs", "hold", "-r", "keep", snap_name])
    try:
        yield snap_name
    finally:
        subprocess.check_call(["zfs", "release", "-r", "keep", snap_name])
        subprocess.check_call(["zfs", "destroy", snap_name])


@lock(LOCKFILE)
def do_node_backup(backup_dir, callback, skip_errors, **kwargs):

    def handle(handler, result):
        try:
            subprocess.check_call("{0} {1}".format(handler, result),
                                  shell=True)
        except subprocess.CalledProcessError as err:
            raise BackupError(
                "Callback handler has failed with `{0}`".format(err))

    timestamp = datetime.datetime.today().isoformat()
    dst = os.path.join(backup_dir, "local_pv_backup_{0}".format(timestamp))
    for user_id in os.listdir(STORAGE_LOCATION):
        user_dir = os.path.join(STORAGE_LOCATION, user_id)
        for volume_id in os.listdir(user_dir):
            volume_dir = os.path.join(user_dir, volume_id)
            result_dir = os.path.join(dst, user_id)
            if not os.path.exists(result_dir):
                os.makedirs(result_dir)
            logger.debug({"src": STORAGE_LOCATION, "user": user_id,
                          "volume_id": volume_id})
            try:
                with zfs_snapshot(volume_dir) as snap_name:
                    with mount_context(snap_name) as mountpoint:
                        result = make_tar_backup(volume_id, mountpoint,
                                                 result_dir, skip_errors)
            except NonZFSException as err:
                logging.warning("Possible inconsistent backup "
                                "creation: {}".format(err))
                result = make_tar_backup(volume_id, volume_dir,
                                         result_dir, skip_errors)
            logger.info('Backup created: {0}'.format(result))
    if callback:
        handle(callback, dst)


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
    parser.add_argument("-e", '--callback',
                        help='Callback for backup file (backup path '
                        'passed as a 1st arg)')
    parser.add_argument(
        'backup_dir', help="Destination for all created files")
    parser.set_defaults(func=do_node_backup)

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
