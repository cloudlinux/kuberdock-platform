"""AWS EBS management functions."""
from __future__ import absolute_import

import time
import subprocess

from .common import OK, ERROR, TimeoutError


def get_aws_instance_meta(utils):
    identity = utils.get_instance_identity()
    meta = utils.get_instance_metadata()
    return {
        'instance-id': meta['instance-id'],
        'region': identity['document']['region'],
        'av-zone': meta['placement']['availability-zone'],
    }


def get_aws_block_device_mapping(connection, instance_id):
    return connection.get_instance_attribute(
        instance_id=instance_id,
        attribute='blockDeviceMapping'
    )['blockDeviceMapping']


def detach_ebs(aws_access_key_id, aws_secret_access_key, devices):
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
    for key, bd in bd_mapping.iteritems():
        if key in devices:
            connection.detach_volume(bd.volume_id)


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
        try:
            volume = create_ebs_volume(
                connection, av_zone, name, call_args.size
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


def create_ebs_volume(connection, availability_zone, name, size):
    """Creates new EBS volume"""
    # timeout to wait until volume will be available (15 minutes)
    wait_time = 15 * 60
    volume = connection.create_volume(size, availability_zone)
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
