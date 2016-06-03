import socket
import time
import logging

LOG = logging.getLogger(__name__)


def ssh_exec(ssh, cmd, timeout=None, check_retcode=True):
    LOG.debug("Calling SSH: '{0}'".format(cmd))
    stdin, out, err = ssh.exec_command(cmd, timeout=timeout)
    retcode = out.channel.recv_exit_status()
    out, err = out.read(), err.read()
    LOG.debug("\nRetCode: {0}\nStdOut: {1}\nStdErr: {2}".format(retcode, out, err))
    if check_retcode:
        assert_eq(retcode, 0)
    return retcode, out, err


class PublicPortWaitTimeoutException(Exception):
    pass


def wait_net_port(ip, port, timeout, try_interval=2):
    LOG.debug("Waiting for {0}:{1} to become available.".format(ip, port))
    end = time.time() + timeout
    while time.time() < end:
        try:
            s = socket.create_connection((ip, port), timeout=5)
        except socket.timeout:
            # cannot connect after timeout
            continue
        except socket.error as ex:
            # cannot connect immediately (e.g. no route)
            # wait timeout before next try
            LOG.debug("Wait cycle msg: {0}".format(repr(ex)))
            time.sleep(try_interval)
            continue
        else:
            # success!
            s.close()
            return
    raise PublicPortWaitTimeoutException()


def kube_type_to_int(kube_type):
    int_types = {
        "Small": 0,
        "Standard": 1,
    }
    return int_types[kube_type]


def assert_eq(actual, expected):
    if actual != expected:
        raise AssertionError("Values are not equal\n"
                             "Expected: {0}\n"
                             "Actual  : {1}".format(expected, actual))


def assert_in(item, sequence):
    if item not in sequence:
        raise AssertionError("Item '{0}' not in '{1}'".format(
            item, sequence
        ))
