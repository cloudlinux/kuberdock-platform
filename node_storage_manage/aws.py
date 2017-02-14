
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

"""AWS EBS management functions."""
from __future__ import absolute_import

import time
import subprocess

from .common import OK, ERROR, TimeoutError

# Available EBS volume types
VOL_TYPE_ST = 'standard'
VOL_TYPE_IO = 'io1'
VOL_TYPE_GP = 'gp2'
DEFAULT_EBS_VOLUME_TYPE = VOL_TYPE_ST
# Acceptable range for iops value
# http://docs.aws.amazon.com/cli/latest/reference/ec2/create-volume.html
VOL_IOPS_RANGE = (100, 20000)

ALL_EBS_TYPES = (VOL_TYPE_ST, VOL_TYPE_IO, VOL_TYPE_GP)


def get_aws_instance_meta(utils):
    """Returns some metadata for the instance."""
    identity = utils.get_instance_identity()
    meta = utils.get_instance_metadata()
    return {
        'instance-id': meta['instance-id'],
        'region': identity['document']['region'],
        'av-zone': meta['placement']['availability-zone'],
    }


def get_aws_block_device_mapping(connection, instance_id):
    """Returns dict of {
        <device name>: <block device type>
    }
    where device name is string in form of '/dev/xvdX'
    block device type is an object of class
        boto.ec2.blockdevicemapping.BlockDeviceType
        (we need only volume_id from it)
    """
    return connection.get_instance_attribute(
        instance_id=instance_id,
        attribute='blockDeviceMapping'
    )['blockDeviceMapping']


def detach_ebs(aws_access_key_id, aws_secret_access_key, devices):
    """Detaches volumes for given devices if they are attached to the instance.
    Will wait some time until all detached volumes become 'detached'.
    Returns true if all devices was successfully detached.
    False - otherwise.
    """
    import boto
    import boto.ec2
    meta = get_aws_instance_meta(boto.utils)
    connection = boto.ec2.connect_to_region(
        meta['region'],
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )
    bd_mapping = get_aws_block_device_mapping(
        connection, meta['instance-id']
    )
    volume_ids = [bd.volume_id for key, bd in bd_mapping.iteritems()
                  if key in devices]
    return _detach_ebs_volumes(connection, volume_ids, force=False)


def _detach_ebs_volumes(connection, volume_ids, force=False):
    for volume_id in volume_ids:
        connection.detach_volume(volume_id, force=force)
    if not wait_for_detached_state(connection, volume_ids):
        return False
    return True


def _volumes_are_available(connection, volume_ids):
    volumes = connection.get_all_volumes(volume_ids)
    # In AWS documentation there are the following states:
    # (attaching | attached | detaching | detached)
    # But actually boto returns None for detached volume, so check it
    # both here.
    return all(
        (
            item.attachment_state() == 'detached' or
            item.attachment_state() is None
        ) and
        item.status == 'available' for item in volumes
    )


def wait_for_detached_state(connection, volume_ids):
    """Will wait until volumes with given ids become detached.
    It will check volumes states 180 times with 1 second pause, so max
    wait time will be approximately 3 minutes.
    Returns True if all volumes become detached. False if one or more volumes
    will not become detached.
    """
    retry_count = 60 * 3
    pause = 1
    for _ in xrange(retry_count):
        if _volumes_are_available(connection, volume_ids):
            return True
        time.sleep(pause)
    return False


def attach_existing_volumes(call_args):
    """Attaches volumes to the instance. Volumes names must be passed via
    call_args.ebs_volumes list.
    Returns tuple of success flag and list of dicts described attached volumes.
    Each element of this list will include fields:
            'name': <volume 'Name' tag value>,
            'instance_id': <ec2 instance identifier>,
            'device': <name of device in form of /dev/xvdX>
    """
    import boto
    import boto.ec2
    meta = get_aws_instance_meta(boto.utils)
    region = meta['region']
    instance_id = meta['instance-id']
    connection = boto.ec2.connect_to_region(
        region,
        aws_access_key_id=call_args.aws_access_key_id,
        aws_secret_access_key=call_args.aws_secret_access_key
    )
    names_to_attach = call_args.ebs_volumes
    force_detach = call_args.force_detach

    existing_volumes = connection.get_all_volumes()
    volumes = []
    for item in existing_volumes:
        if item.tags.get('Name', 'Nameless') in names_to_attach:
            volumes.append(item)
            break
    if len(volumes) != len(names_to_attach):
        return False, 'Not all EBS volumes were found'

    volume_ids = [vol.id for vol in volumes]
    if not _volumes_are_available(connection, volume_ids):
        if force_detach:
            _detach_ebs_volumes(connection, volume_ids, force=True)
        # update volumes, because it's state may be changed
        volumes = connection.get_all_volumes(volume_ids)

    dev_list = []
    for volume in volumes:
        try:
            ok, result = attach_ebs_volume(connection, instance_id, volume)
            if ok != OK:
                return False, result
            dev_list.append(result)
        except (boto.exception.BotoClientError,
                boto.exception.BotoServerError) as err:
            return False, 'Failed to attach volume: {}'.format(err)
    return True, dev_list


def do_ebs_attach(call_args):
    import boto
    import boto.ec2
    meta = get_aws_instance_meta(boto.utils)
    region = meta['region']
    av_zone = meta['av-zone']
    instance_id = meta['instance-id']
    connection = boto.ec2.connect_to_region(
        region,
        aws_access_key_id=call_args.aws_access_key_id,
        aws_secret_access_key=call_args.aws_secret_access_key
    )
    existing_volumes = connection.get_all_volumes()
    volume = None
    name = call_args.name
    for item in existing_volumes:
        if item.tags.get('Name', 'Nameless') == name:
            volume = item
            break
    if not volume:
        err_msg = 'Failed to create EBS volume: {}'
        volume_type = call_args.volume_type
        iops = None
        if volume_type == VOL_TYPE_IO:
            iops = call_args.iops
            if not iops:
                return (
                    ERROR,
                    {
                        'message': err_msg.format(
                            'iops should be specified for volume type "{}"'\
                            .format(volume_type)
                        )
                    }
                )
        elif not volume_type:
            volume_type = DEFAULT_EBS_VOLUME_TYPE

        try:
            volume = create_ebs_volume(
                connection, av_zone, name, call_args.size,
                volume_type=volume_type, iops=iops
            )
        except (boto.exception.BotoClientError,
                boto.exception.BotoServerError,
                TimeoutError) as err:
            return ERROR, {'message': err_msg.format(err)}
        if not volume:
            return ERROR, {'message': err_msg.format('Unknown error')}

    try:
        return attach_ebs_volume(connection, instance_id, volume)
    except (boto.exception.BotoClientError,
            boto.exception.BotoServerError) as err:
        return ERROR, {'message': 'Failed to attach volume: {}'.format(err)}


def create_ebs_volume(connection, availability_zone, name, size,
                      volume_type, iops):
    """Creates new EBS volume"""
    # timeout to wait until volume will be available (15 minutes)
    wait_time = 15 * 60
    volume = connection.create_volume(size, availability_zone,
                                      volume_type=volume_type, iops=iops)
    start_time = time.time()
    if volume:
        volume.add_tag('Name', name)
        while volume.status != 'available':
            if (time.time() - start_time) > wait_time:
                raise TimeoutError(
                    'Timeout ({} m) of waiting volume availability'.format(
                        wait_time / 60
                    )
                )
            time.sleep(1)
            volume.update()
        return volume
    return None


def attach_ebs_volume(connection, instance_id, volume):
    # Raise exception if drive is attached
    result = {
        'name': volume.tags.get('Name', 'Nameless'),
        'instance_id': instance_id,
    }

    if volume.attachment_state() == 'attached':
        if volume.attach_data.instance_id != instance_id:
            return ERROR, {
                'message': 'Volume already attached to another instance '
                           '({})'.format(volume.attach_data.instance_id)
            }
        result['device'] = volume.attach_data.device
        return OK, result

    device = _get_aws_instance_next_drive()
    if device is None:
        return ERROR, {'message': 'Failed to get free device name'}

    connection.attach_volume(volume.id, instance_id, device)
    _wait_until_device_ready(device)
    result['device'] = device
    return OK, result


def _wait_until_device_ready(device, timeout=90):
    """Sends to node command to loop until
    state of /proc/partitions is changed
    :param device: string -> a block device, e.g. /dev/xvda
    :param to_be_attached: bool -> toggles checks to be taken: attached or
        detached
    :param timeout: int -> number of seconds to wait for state change
    """
    command = (
        'KDWAIT=0 && while [ "$KDWAIT" -lt {0} ];'
        'do OUT=$(cat /proc/partitions|grep {1});'
        'if [ -n "$OUT" ];then break;'
        'else KDWAIT=$(($KDWAIT+1)) && $(sleep 1 && exit 1);'
        'fi;done'.format(
            timeout, device.replace('/dev/', '')
        )
    )
    wait_process = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    wait_process.communicate()


def _get_aws_instance_next_drive():
    """
    Gets current node xvdX devices, sorts'em and gets the last device
        letter.
    Then returns next letter device name
    :return: string -> device (/dev/xvdX)
    """
    cmd = "ls -1 /dev/xvd*|awk -F '' '/xvd/ {print $9}'|sort"
    ls = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    res, err = ls.communicate()
    if ls.returncode or err or not res:
        return None

    last = res.splitlines()[-1]
    try:
        last_num = ord(last)
    except TypeError:
        return None
    if last_num >= ord('z'):
        return None
    return '/dev/xvd{0}'.format(chr(last_num+1))
