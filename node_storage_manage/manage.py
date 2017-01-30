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

"""The module provides commands to manage localstorage backend.
The whole directory must be placed to /var/lib/kuberdock directory
on a node.

This manage module is a wrapper to parse command line parameters and
to format output.
It imports actual backend commands from .storage module. So to activate
particular storage backend there must be symbolic link to the module, for
example:
  ln -s node_zfs_manage.py storage.py  # this activates ZFS storage backend.

Each storage backend must provide functions:

    do_get_info
    do_add_volume
    do_remove_storage
    do_create_volume
    do_remove_volume

Each function must accept one parameter which is a result of
argparse.ArgumentParser(...).parse_args() and contains command-specific
parameters.

Each function must return tuple of execution status and some payload data
(dict or None). Predefined execution statuses are `common.OK`, `common.ERROR`
Also a function could raise common.CmdError exception.

The module will convert execution result to json string:
    {
        "status": <returned status from backend command>,
        "data": <returned payload from backend command>
    }

One exception: result of function do_remove_storage will be further processed,
to do some additioal actions on AWS backend. It must return tuple of
success flag and list of freed block devices. These devices will be used to
identify attached EBS volumes.


Also a storage module must provide VOLUME_MANAGE_NAME string constant to
use it in output messages as storage backend name.


Commands:
1. Add volume to storage backend:
    manage.py add-volume --devices <list of block devices>
  This commands takes given list of block devices and adds it to current
  local storage backend.
2. Extends current storage with Amazon EBS volume:
    manage.py ebs-attach <options>
  Attaches EBS volume to the node. If no name of EBS volume is specified,
  then first creates new volume with specified size.
3. Get info about current storage:
    manage.py get-info
  Returns usage information of the storage (output depends on current backend)
4. Remove storage
    manage.py remove-storage
  Destroys current storage, also detaches EBS volumes in case of AWS.
5. Create volume
    manage.py create-volume <options>
  Creates volume for persistent disk in storage with specified size quota.
6. Remove volume
    manage.py remove-volume <options>
  Deletes specified volume for persistent disk in storage.

For full list of args for each command call 'manage.py <command name> -h'

"""
from __future__ import absolute_import

import os
import argparse
import json

from . import aws
from .common import OK, ERROR, CmdError, volume_can_be_resized_to

from .storage import (
    do_get_info, do_add_volume, do_remove_storage, VOLUME_MANAGE_NAME,
    do_create_volume, do_remove_volume, do_resize_volume
)


def _do_remove_storage(call_args):
    """Calls storage destroy for current storage.
    Also if specified detach_ebs option, then calls detaching for AWS EBS
    volumes which were used for deleted storage.

    """
    ok, result = do_remove_storage(call_args)
    if not ok:
        return ERROR, {'message': u'Remove storage failed: {}'.format(result)}
    # we expect device list in result in case of successful storage removing
    devices = result
    if result and call_args.detach_ebs:
        aws.detach_ebs(
            call_args.aws_access_key_id,
            call_args.aws_secret_access_key,
            devices
        )
    return OK, {
        'message': 'Localstorage ({}) has been deleted'
                   .format(VOLUME_MANAGE_NAME)
    }

def _do_resize_volume(call_args):
    """Calls do_resize_volume of current storage.
    Before calling the method of current storage checks if path exists, and
    that the volume can be resized (it is forbidden to reduce volume quota
    less than already used space).
    If the path does not exist, the method does nothing and returns no errors.
    """
    path = call_args.path
    quota_gb = int(call_args.new_quota)
    if not os.path.exists(path):
        return OK, {}
    ok, error_message = volume_can_be_resized_to(path, quota_gb * (1024 ** 3))
    if not ok:
        return ERROR, {'message': error_message}
    return do_resize_volume(call_args)


COMMANDS = {
    'ebs-attach': aws.do_ebs_attach,
    'add-volume': do_add_volume,
    'get-info': do_get_info,
    'remove-storage': _do_remove_storage,
    'create-volume': do_create_volume,
    'remove-volume': do_remove_volume,
    'resize-volume': _do_resize_volume,
}


def validate_int_range(minvalue, maxvalue):
    def inner_checker(value):
        ivalue = int(value)
        if ivalue < minvalue or ivalue > maxvalue:
            raise argparse.ArgumentTypeError(
                'The value should be in range {} - {}'.format(
                    minvalue, maxvalue)
            )
        return ivalue
    return inner_checker


def process_args():
    parser = argparse.ArgumentParser("Kuberdock local storage manager")
    subparsers = parser.add_subparsers(
        help="Commands",
        title="Commands",
        description="Available commands",
        dest="cmd"
    )

    attach_ebs = subparsers.add_parser(
        'ebs-attach',
        help='Attach EBS volume to the node (and optionally create)'
    )
    attach_ebs.add_argument('--size',
                            help='Size of new EBS volume in GB',
                            type=int)
    attach_ebs.add_argument('--aws-access-key-id',
                            dest='aws_access_key_id',
                            help='AWS access key ID')
    attach_ebs.add_argument('--aws-secret-access-key',
                            dest='aws_secret_access_key',
                            help='AWS secret access key')
    attach_ebs.add_argument('--name',
                            help='Name of EBS volume to attach')
    attach_ebs.add_argument('--volume-type',
                            dest='volume_type',
                            help='EBS volume type',
                            choices=aws.ALL_EBS_TYPES)
    attach_ebs.add_argument(
        '--iops',
        dest='iops',
        help='IOPS for provisioned iops volume types ({}).'.format(
            aws.VOL_TYPE_IO),
        type=validate_int_range(*aws.VOL_IOPS_RANGE))

    add_volume = subparsers.add_parser(
        'add-volume',
        help='Add existing physical volume to KD storage space'
    )
    add_volume.add_argument(
        '--devices', nargs='+',
        help='Device name to add to volume group and extend KD storage space'
    )

    subparsers.add_parser(
        'get-info',
        help='Collect and return info about Kuberdock LVM storage'
    )

    remove_storage = subparsers.add_parser(
        'remove-storage',
        help='Unmount and remove localstorage volume group from node.'
    )
    remove_storage.add_argument(
        '--detach-ebs', dest='detach_ebs',
        default=False, action='store_true',
        help='Detach EBS volumes that were in LS volume group'
    )
    remove_storage.add_argument(
        '--aws-access-key-id',
        dest='aws_access_key_id', required=False,
        help='AWS access key ID'
    )
    remove_storage.add_argument(
        '--aws-secret-access-key',
        dest='aws_secret_access_key', required=False,
        help='AWS secret access key'
    )
    create_volume = subparsers.add_parser(
        'create-volume',
        help='Create persistent volume with current localstorage backend'
    )
    create_volume.add_argument(
        '--path', dest='path', required=True, help='Path to volume'
    )
    create_volume.add_argument(
        '--quota', dest='quota', required=True, help='Volume size quota (GB)',
        type=int
    )

    remove_volume = subparsers.add_parser(
        'remove-volume',
        help='Remove persistent volume'
    )
    remove_volume.add_argument(
        '--path', dest='path', required=True, help='Path to volume'
    )

    resize_volume = subparsers.add_parser(
        'resize-volume',
        help='Resize persistent volume',
    )
    resize_volume.add_argument(
        '--path', dest='path', required=True, help='Path to persistent volume'
    )
    resize_volume.add_argument(
        '--new-quota', dest='new_quota', required=True, type=int,
        help='New size quota (GB) of the volume'
    )

    return parser.parse_args()


if __name__ == '__main__':
    args = process_args()
    try:
        status, data = COMMANDS[args.cmd](args)
    except CmdError as err:
        print json.dumps({'status': ERROR, 'data': err.to_dict()})
    else:
        print json.dumps({'status': status, 'data': data})
