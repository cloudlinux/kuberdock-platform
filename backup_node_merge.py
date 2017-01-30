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


import os
import sys
import logging
import argparse
import datetime

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
    """
    Grouping timestamps by precision.

    List of timestamps `data` should contain strings.
    Integer `precision` represents time gap in seconds.
    If any item has formatting issues it raises MergeError. This
    behaviour can be disabled with skip_errors flag.
    """

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
            t0 = timestamp
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
                logger.info("Folders `{0}` were skipped because "
                            "they can be still in backup process "
                            "and not consistant.".format(', '.join(group)))
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
