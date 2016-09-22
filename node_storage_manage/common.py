"""Common constants and functions for node storage management."""
from __future__ import absolute_import

import os
import sys
import subprocess
import re

# Command execution results
OK = 'OK'
ERROR = 'ERROR'

# Mount point to logical volume
LOCAL_STORAGE_MOUNT_POINT = '/var/lib/kuberdock/storage'

# Pattern to get output of du -b -s <path> command
DU_OUTPUT_PATTERN = re.compile(r'^(\d+)\s+.*')


class TimeoutError(Exception):
    """Helper exception for timeouts handling"""
    pass


def silent_call(commands):
    """Calls subprocess and returns it's exitcode. Hides stdout and stderr of
    called subprocess.
    """
    with open(os.devnull, 'wb') as DEVNULL:
        p = subprocess.Popen(commands, stdout=DEVNULL, stderr=DEVNULL)
        p.communicate()
        retcode = p.returncode
        return retcode


def get_subprocess_result(args):
    try:
        return 0, subprocess.check_output(args, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as err:
        return err.returncode, err.output


class CmdError(Exception):
    """Exception to raise when some external command fails."""
    def __init__(self, error_code, message):
        self.error_code = error_code
        super(CmdError, self).__init__(message)

    def to_dict(self):
        return {'error_code': self.error_code, 'message': self.message}


def raise_cmd_error(err_code, message):
    if not err_code:
        return
    raise CmdError(err_code, message)


def get_fs_usage(mountpoint):
    st = os.statvfs(mountpoint)
    return {
        'size': st.f_frsize * st.f_blocks,
        'available': st.f_frsize * st.f_bavail
    }


def get_path_relative_to_localstorage(full_path):
    """Returns relative path with start of LOCAL_STORAGE_MOUNT_POINT.
    :param full_path: full path, that must be converted to relative
    """
    return os.path.relpath(full_path, LOCAL_STORAGE_MOUNT_POINT)


def utilized_path_size(path):
    """Returns current size for given path in bytes.
    """
    err_code, output = get_subprocess_result(['du', '-s', '-b', path])
    if err_code:
        return -1

    try:
        size = int(DU_OUTPUT_PATTERN.match(output).group(1))
    except (AttributeError, ValueError, TypeError) as err:
        return -1
    return size


def volume_can_be_resized_to(path, new_size):
    """Checks size of given path is less than specified new size (in bytes).
    If it is less, then returns tuple of (True, None).
    If it is not less or failed to get current size for the path, then
    returns tuple of (False, <error message>).
    """
    already_used = utilized_path_size(path)
    if already_used < 0:
        return False, 'Failed to get already used size of the volume'
    GB = 1024 ** 3
    if already_used >= new_size:
        return (
            False,
            'Volume can not be reduced to {:.2f}G. Already used {:.2f}G.'
            .format(float(new_size) / GB, float(already_used) / GB)
        )
    return True, None
