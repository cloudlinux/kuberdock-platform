"""Common constants and functions for node storage management."""
from __future__ import absolute_import

import os
import sys
import subprocess

# Command execution results
OK = 'OK'
ERROR = 'ERROR'

# Mount point to logical volume
LOCAL_STORAGE_MOUNT_POINT = '/var/lib/kuberdock/storage'


class TimeoutError(Exception):
    """Helper exception for timeouts handling"""
    pass


def silent_call(commands):
    """Calls subprocess and returns it's exitcode. Hides stdout and stderr of
    called subprocess.
    """
    p = subprocess.Popen(commands, stdout=sys.stderr)
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
