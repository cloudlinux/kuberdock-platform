#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Node backup script
"""

import sys
import datetime
import os
import argparse
import subprocess
import logging
import zipfile

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
            result = os.path.join(result_dir, "{0}.zip".format(volume_id))
            tmp_result = result + '.incomplete'
            logger.debug({"src": STORAGE_LOCATION, "user": user_id,
                          "volume_id": volume_id})
            logger.debug({"dst": result})

            with zipfile.ZipFile(tmp_result, 'w',
                                 zipfile.ZIP_DEFLATED) as zf:
                for fn in iterate_src(volume_dir):
                    try:
                        logger.debug([fn, os.path.relpath(fn, volume_dir)])
                        zf.write(fn, os.path.relpath(fn, volume_dir))
                    except (IOError, OSError) as err:
                        if not skip_errors:
                            if os.path.exists(tmp_result):
                                os.remove(tmp_result)
                            raise
                        logger.warning("File `{0}` backup skipped due to "
                                       "error `{1}`. Skipped".format(fn, err))
            os.rename(tmp_result, result)
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
