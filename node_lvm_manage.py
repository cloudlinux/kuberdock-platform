#!/usr/bin/env python2
"""The module provides commands to manage lvm volumes for localstorage backend.
It must be placed to node host to directory /var/lib/kuberdock/

Commands:
1. Initialize KD volume group
2. Create and attach EBS volume to the node
3. Add existing physical volume to KD volume group

"""
import os
import sys
import subprocess
import argparse
import time
import re
import tempfile

import json

import lvm


# Volume group name for kuberdock storage
KD_VG_NAME = 'kdstorage00'
# Logical volume name for KD storage
KD_LV_NAME = 'kdls00'
# Mount point to logical volume
LOCAL_STORAGE_MOUNT_POINT = '/var/lib/kuberdock/storage'

OK = 'OK'
ERROR = 'ERROR'


class TimeoutError(Exception):
    """Helper exception for timeouts handling"""
    pass

def do_add_volume(call_args):
    devices = call_args.devices
    return add_devices_to_localstorage(devices)


def get_aws_instance_meta(utils):
    identity = utils.get_instance_identity()
    meta = utils.get_instance_metadata()
    return {
        'instance-id': meta['instance-id'],
        'region': identity['document']['region'],
        'av-zone': meta['placement']['availability-zone'],
    }


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


def do_get_info(call_args):
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


def do_remove_ls_vg(call_args):
    all_names = lvm.listVgNames()
    if KD_VG_NAME not in all_names:
        return OK, {'message': 'Localstorage volume group was already deleted'}
    vg = lvm.vgOpen(KD_VG_NAME, 'w')
    try:
        _silent_call(['umount', '-f', LOCAL_STORAGE_MOUNT_POINT])
        pvs = [item.getName() for item in vg.listPVs()]
        for lv in vg.listLVs():
            lv.deactivate()
            lv.remove()
        vg.remove()
        remove_ls_mount()
        if call_args.detach_ebs:
            import boto
            import boto.ec2
            meta = get_aws_instance_meta(boto.utils)
            connection = boto.ec2.connect_to_region(
                meta['region'],
                aws_access_key_id=call_args.aws_access_key_id,
                aws_secret_access_key=call_args.aws_secret_access_key
            )
            bd_mapping = get_aws_block_device_mapping(
                connection, meta['instance-id']
            )
            for key, bd in bd_mapping.iteritems():
                if key in pvs:
                    connection.detach_volume(bd.volume_id)
        return OK, {'message': 'Localstorage volume group has been deleted'}
    finally:
        vg.close()


COMMANDS = {
    'ebs-attach': do_ebs_attach,
    'add-volume': do_add_volume,
    'get-info': do_get_info,
    'remove-ls-vg': do_remove_ls_vg,
}


def process_args():
    parser = argparse.ArgumentParser("Kuberdock LVM wrapper")
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

    remove_ls_vg = subparsers.add_parser(
        'remove-ls-vg',
        help='Unmount and remove localstorage volume group from node.'
    )
    remove_ls_vg.add_argument('--detach-ebs', dest='detach_ebs',
        default=False, action='store_true',
        help='Detach EBS volumes that were in LS volume group'
    )
    remove_ls_vg.add_argument('--aws-access-key-id',
                            dest='aws_access_key_id', required=False,
                            help='AWS access key ID')
    remove_ls_vg.add_argument('--aws-secret-access-key',
                            dest='aws_secret_access_key', required=False,
                            help='AWS secret access key')
    return parser.parse_args()


def get_aws_block_device_mapping(connection, instance_id):
    return connection.get_instance_attribute(
        instance_id=instance_id,
        attribute='blockDeviceMapping'
    )['blockDeviceMapping']


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
                'message': 'Volume already attached to another instance '\
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
            new_pv = [item for item in vg.listPVs() if item.getName() == dev][0]
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
        extend_fs_size(dev, LOCAL_STORAGE_MOUNT_POINT)
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


def _silent_call(commands):
    """Calls subprocess and returns it's exitcode. Hides stdout and stderr of
    called subprocess.
    """
    p = subprocess.Popen(commands, stdout=sys.stderr)
    p.communicate()
    retcode = p.returncode
    return retcode


def make_fs(device):
    """Creates filesystem (XFS) on given device
    Returns tuple of success flag and error message (if creation was failed)
    """
    res = _silent_call(['mkfs.xfs', device])
    if res:
        return False, 'Failed to mkfs on {}, exit code: {}'.format(device, res)
    return True, None


def is_mounted(mountpoint):
    """Returns True if some volume is mounted to the mountpoint,
    otherwise returns False.
    """
    res = _silent_call(['grep', '-q', mountpoint, '/proc/mounts'])
    return not res


def mount(device, mountpoint):
    """Mounts given device to mount point.
    """
    res = _silent_call(['mount', '-o', 'prjquota', device, mountpoint])
    if res:
        return False, 'Failed to mount {} to {}. Exit code: {}'.format(
                device, mountpoint, res)
    return True, None


def extend_fs_size(device, mountpoint):
    """Extends FS size to max available size."""

    res = _silent_call(['xfs_growfs', mountpoint])
    if res:
        return False, 'Failed to extend {}. Exit code: {}'.format(
            mountpoint, res
        )
    return True, None


def make_permanent_mount(device, mountpoint):
    # Check it is not already in fstab
    fstab = '/etc/fstab'
    res = _silent_call(['egrep', '-q', '^[^#].*{}'.format(mountpoint), fstab])
    if not res:
        return
    with open(fstab, 'a') as fout:
        fout.write('\n{} {}    xfs    defaults,prjquota 0 0\n'.format(
            device, mountpoint))


if __name__ == '__main__':
    args = process_args()
    status, data = COMMANDS[args.cmd](args)
    print json.dumps({'status': status, 'data': data})
