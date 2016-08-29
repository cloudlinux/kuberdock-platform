#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import logging
import argparse
import datetime
import glob

from distutils import dir_util
from itertools import tee

logger = logging.getLogger("kd_node_backup_merge")
logger.setLevel(logging.INFO)

stdout_handler = logging.StreamHandler()
logger.addHandler(stdout_handler)

formatter = logging.Formatter(
    "[%(asctime)-15s - %(name)-6s - %(levelname)-8s]"
    " %(message)s")
stdout_handler.setFormatter(formatter)


class MergeError(Exception):
    pass


def get_timestamp(item):
    try:
        return datetime.datetime.strptime(
            item, "local_pv_backup_%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        raise MergeError(
            "File `{0}` has unrecognized name format.".format(item))


def group_by_timestamp(data, precision, skip_errors=False):

    # Sanitize group
    timestamps = []
    for item in data:
        try:
            timestamps.append([item, get_timestamp(item)])
        except MergeError as err:
            if skip_errors:
                logger.warning("File `{0}` backup skipped due to "
                               "error `{1}`. Skipped".format(item, err))
                continue
            raise

    head, t0 = timestamps.pop(0)
    group = [head, ]
    for item, timestamp in timestamps:
        gap = timestamp - t0
        logger.debug('{1} | {0} | {2}'.format(item, group[0], gap))
        if gap.total_seconds() <= precision:
            group.append(item)
        else:
            yield group
            group = [item]
    yield group


def will_override(src, group):
    base = []
    for item in group:
        path = os.path.join(src, item)
        for root, _, files in os.walk(path):
            for f in files:
                foo = os.path.relpath(os.path.join(root, f), path)
                if foo in base:
                    return True
                base.append(foo)
    return False


def do_merge(backups, precision, dry_run, include_latest, skip_errors,
             **kwargs):
    data = sorted(os.listdir(backups))
    if not data:
        raise MergeError("Nothing found.")

    groups, helper = tee(group_by_timestamp(data, precision * 60 * 60,
                                            skip_errors))
    next(helper, None)

    for group in groups:
        try:
            next(helper)
        except StopIteration:
            if not include_latest:
                logger.info("Folders `{0}` were excluded from merge because "
                            "they can be not "
                            "complete.".format(', '.join(group)))
                continue
        logger.info("GROUP: {0}".format(group))
        if will_override(backups, group):
            raise MergeError("Group `{0}` contains overlapping files. May be "
                             "precision was bigger then backup "
                             "periodicity.".format(group))
        dst = os.path.join(backups, group.pop(0))
        for item in group:
            src = os.path.join(backups, item)
            dir_util.copy_tree(src, dst, verbose=True, dry_run=dry_run)
            dir_util.remove_tree(src, verbose=True, dry_run=dry_run)


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
    parser.add_argument("-d", '--dry-run', action='store_true',
                        dest='dry_run',
                        help="Do not touch any files")
    parser.add_argument("-p", '--precision', help="Maximum time gap to group "
                        "in hours. Default: 1hr.", default=1, type=int)
    parser.add_argument("-i", '--include-latest', action='store_true',
                        dest='include_latest', help="Set to also include "
                        "latest (possible incomplete) backup folder")

    parser.add_argument(
        'backups', help="Target git which contains all backups")
    parser.set_defaults(func=do_merge)

    return parser.parse_args(args)


def main():
    if os.getuid() != 0:
        raise Exception('Root permissions are required to run this script')

    args = parse_args(sys.argv[1:])
    logger.setLevel(args.loglevel or logging.INFO)

    try:
        args.func(**vars(args))
    except MergeError as err:
        logger.error("Merge failed: {0}".format(err))
        exit(1)

if __name__ == '__main__':
    main()
