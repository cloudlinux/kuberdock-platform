import os
import logging
import operator
import random
import re
import socket
import string
import time
import subprocess
from functools import wraps
from collections import defaultdict
from contextlib import contextmanager
from functools import wraps
from itertools import count, islice

import oca
from colorama import Fore, Style
from ipaddress import IPv4Address
from oca import OpenNebulaException

from tests_integration.lib.exceptions import PublicPortWaitTimeoutException, \
    NonZeroRetCodeException, NotEnoughFreeIPs

NO_FREE_IPS_ERR_MSG = 'no free public IP-addresses'
LOG = logging.getLogger(__name__)


def _proceed_exec_result(out, err, ret_code, check_retcode):
    msg_parts = [
        (Fore.GREEN, 'RetCode: ', str(ret_code)),
        (Fore.YELLOW, '=== StdOut ===\n', out),
        (Fore.RED, '=== StdErr ===\n', err)]
    msg = '\n'.join('{}{}{}'.format(c, n, v) for c, n, v in msg_parts if v)

    LOG.debug(msg + Style.RESET_ALL)
    if check_retcode and ret_code != 0:
        raise NonZeroRetCodeException(
            stdout=out, stderr=err, ret_code=ret_code)


def local_exec(cmd, env=None, timeout=None, check_retcode=True):
    LOG.debug("{}Calling local: '{}'{}".format(Style.DIM, cmd,
                                               Style.RESET_ALL))
    if env is not None:
        env = dict(os.environ, **env)
    proc = subprocess.Popen(cmd, env=env, stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    out, err = proc.communicate()
    ret_code = proc.returncode

    _proceed_exec_result(
        out.decode('ascii', 'ignore'), err.decode('ascii', 'ignore'),
        ret_code, check_retcode)
    return ret_code, out, err


def ssh_exec(ssh, cmd, timeout=None, check_retcode=True):
    LOG.debug("{}Calling SSH: '{}'{}".format(Style.DIM, cmd, Style.RESET_ALL))
    _, out, err = ssh.exec_command(cmd, timeout=timeout)
    ret_code = out.channel.recv_exit_status()
    out, err = out.read().strip(), err.read().strip()

    _proceed_exec_result(out, err, ret_code, check_retcode)
    return ret_code, out, err


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


KUBE_TYPE_TO_INT = {
    "Tiny": 0,
    "Standard": 1,
    "High memory": 2,
}
INT_TO_KUBE_TYPE = {
    v: k for k, v in KUBE_TYPE_TO_INT.iteritems()
}


def kube_type_to_int(kube_type):
    return KUBE_TYPE_TO_INT[kube_type]


def kube_type_to_str(kube_type):
    return INT_TO_KUBE_TYPE[kube_type]


def assert_eq(actual, expected):
    if actual != expected:
        raise AssertionError("Values are not equal\n"
                             "Expected: {0}\n"
                             "Actual  : {1}".format(expected, actual))


def assert_not_eq(actual, not_expected):
    if actual == not_expected:
        raise AssertionError("Value should not be equal {}"
                             .format(not_expected))


def assert_in(item, sequence):
    if item not in sequence:
        raise AssertionError("Item '{0}' not in '{1}'".format(
            item, sequence
        ))


@contextmanager
def assert_raises(expected_exc, text=".*"):
    try:
        yield
    except expected_exc as e:
        err_msg = str(e)
        if re.search(text, err_msg) is None:
            raise AssertionError("Given text '{}' is not found in error "
                                 "message: '{}'".format(text, err_msg))
    except Exception as e:
        raise AssertionError("Caught exception '{}' does not match expected "
                             "one '{}'".format(repr(e), str(expected_exc)))
    else:
        raise AssertionError("Expected to raise '{}' but nothing is "
                             "raised.".format(str(expected_exc)))


def merge_dicts(*dictionaries):
    """
    Merge a given number of dicts to the single one. If there are duplicate
    keys between the dictionaries then the value is taken from dictionary
    which has a higher priority. Priorities increase from the left to the right
    """
    result = {}
    for dictionary in dictionaries:
        result.update(dictionary)
    return result


def hooks(setup=None, teardown=None):
    """
    Decorator used to link per-test setup & teardown methods to test
    Usage:

    def my_setup(cluster)
        # do setup here
        pass

    @pipeline("my_pipeline")
    @hooks(setup=my_setup)
    def test_something(cluster):
        # do test here
        pass

    :param setup: setup callable ref
    :param teardown: teardown callable ref
    :return: None
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if setup:
                try:
                    setup(*args, **kwargs)
                except Exception as e:
                    msg = "=== Error in test linked setup: ===\n{}"
                    LOG.error(msg.format(repr(e)))
                    raise
            try:
                f(*args, **kwargs)
            finally:
                if teardown:
                    try:
                        teardown(*args, **kwargs)
                    except Exception as e:
                        msg = "=== Error in test linked teardown: ===\n{}"
                        LOG.error(msg.format(repr(e)))
                        raise

        return wrapper

    return decorator


def pod_factory(image, **create_kwargs):
    """
    A helper function which returns a factory function. It is then used to
    create a given amount of pods with unique names because POD names should be
    unique in KD. Also it is possible to specify some default arguments
    passed to the actual create_pod function but nevertheless it's possible
    to override them each time you create a pod

    :param cluster: an instance of KDIntegrationTestAPI
    :param image: the desired image name which will be used for pods
    :param create_kwargs: arguments (except image and name) which will passed
    through to the cluster's create_pod(...) method
    :return: a list of created pod instances
    """
    name_generator = ('{}_{}'.format(image, i) for i in count())

    def _factory(cluster, num=1, **override_kwargs):
        params = merge_dicts(create_kwargs, override_kwargs)
        names = islice(name_generator, num)
        return [cluster.create_pod(image, n, **params) for n in names]

    return _factory


def center_text_message(message, width=120, fill_char='-', color=''):
    """
    Returns a string where the message is centered relative to the specified
    width filling the empty space around text with the given character

    :param message: string
    :param width: width of the screen
    :param fill_char: char to use for filling blanks
    :return: formatted message
    """
    message = ' {} '.format(message)
    return '{}{{:{}^{}}}{}'.format(
        color, fill_char, width, Fore.RESET).format(message)


def retry(f, tries=3, interval=1, _raise=True, *f_args, **f_kwargs):
    """
    Retries given func call specified n times

    :param f: callable
    :param tries: number of retries
    :param interval: sleep interval between retries
    :param _raise: re-raise function exception when retries done
    :param f_args: callable args
    :param f_kwargs: callable kwargs
    :return:
    """
    while tries > 0:
        tries -= 1
        try:
            return f(*f_args, **f_kwargs)
        except Exception as ex:
            LOG.debug("Retry failed with exception: {0}".format(repr(ex)))
            if tries > 0:
                LOG.debug("{0} retries left".format(tries))
                time.sleep(interval)
            else:
                if _raise:
                    raise


class NebulaIPPool(object):
    def __init__(self, client):
        self.client = client
        self.reserved = defaultdict(set)

    @property
    def pool(self):
        p = oca.VirtualNetworkPool(self.client, preload_info=True)
        # Filter flag possible values:
        # -3: Connected user's resources
        # -2: All resources
        # -1: Connected user's and his group's resources
        p.info(filter=-2, range_start=-1, range_end=-1)
        return p

    def get_free_ip_list(self, network_name):
        """
        Returns the set of free IP addresses in the given network

        :param network_name: the name of a network in OpenNebula
        :return: a set of IPv4 addresses
        """
        net = self.pool.get_by_name(network_name)
        ip_list, used_ip_list = set(), set()

        for r in net.address_ranges:
            start_ip = int(IPv4Address(unicode(r.ip)))
            end_ip = start_ip + r.size

            for ip in range(start_ip, end_ip):
                ip_list.add(str(IPv4Address(ip)))
            for lease in r.leases:
                used_ip_list.add(lease.ip)

        return ip_list - used_ip_list

    def reserve_ips(self, network_name, count):
        # type: (str, int) -> list[str]
        """
        Tries to hold the given amount of given IP addresses of a network
        Automatically retries if IP were concurrently taken. Raises if there
        are not enough IP addresses

        :param network_name: the name of a network in OpenNebula
        :param count: number of IPs to hold
        :return: a set of reserved IPv4 addresses
        """

        def reserve_ip(ips, net):
            """
            Tries to reserve a random free IP. Retries if any OpenNebula
            related problem occurs. If ips set is empty or became empty
            during the while loop consider there is not enough IPs

            :return: reserved IP
            """
            while ips:
                ip = ips.pop()
                try:
                    net.hold(ip)
                    return ip
                except OpenNebulaException:
                    # It's not possible to distinguish if that was an
                    # arbitrary API error or the IP was concurrently
                    # reserved. We'll consider it's always the latter case
                    pass

            raise NotEnoughFreeIPs(
                'The number of free IPs became less than requested during '
                'reservation')

        ips = self.get_free_ip_list(network_name)
        if len(ips) < count:
            raise NotEnoughFreeIPs(
                '{} net has {} free IPs but {} requested'.format(network_name,
                                                                 len(ips),
                                                                 count))

        net = self.pool.get_by_name(network_name)

        for _ in range(count):
            ip = reserve_ip(ips, net)
            self.reserved[network_name].add(ip)

        return self.reserved[network_name]

    def free_reserved_ips(self):
        """
        Tries to release all IPs reserved within this class object instance
        """
        for net_name, ip_set in self.reserved.items():
            net = self.pool.get_by_name(net_name)
            for ip in ip_set:
                try:
                    net.release(ip)
                except OpenNebulaException:
                    pass

    @property
    def reserved_ips(self):
        return reduce(operator.or_, self.reserved.values())

    @classmethod
    def factory(cls, url, username, password):
        # type: (str, str, str) -> NebulaIPPool
        client = oca.Client('{}:{}'.format(username, password), url)
        return cls(client)

    def store_reserved_ips(self, ip):
        """
        Store information about reserved IPs by a VM given it's IP

        This information is needed for a GC script, which removes old VMs.
        The script should also release IPs which were reserved in this
        class. It will use this info saved here to extract a list of IPs
        it should release
        """
        vm = self._get_vm_by_ip(ip)
        reserved_ips = ','.join(self.reserved_ips)
        vm.update('RESERVED_IPS="{}"'.format(reserved_ips))

    def _get_vm_by_ip(self, ip):
        # type: (str) -> oca.VirtualMachine
        vm_pool = oca.VirtualMachinePool(self.client)
        vm_pool.info()
        for vm in vm_pool:
            if ip in (n.ip for n in vm.template.nics):
                return vm
        raise OpenNebulaException('VM {} not found'.format(ip))


def get_rnd_string(length=10, prefix=""):
    return prefix + ''.join(random.SystemRandom().choice(
        string.ascii_uppercase + string.digits) for _ in range(length))


@contextmanager
def suppress(exc=Exception):
    """
    A contextlib.suppress port from python 3.4 for suppressing a given type
    of exception

    :param exc: exception class to ignore
    """
    try:
        yield
    except exc:
        pass


def get_test_full_name(test):
    return '{}::{}'.format(test.__module__, test.__name__)


def http_share(cluster, host, shared_dir):
    def _is_running():
        cmd = "curl -X GET http://{}".format("127.0.0.1")
        try:
            cluster.ssh_exec(host, cmd)
            return True
        except NonZeroRetCodeException:
            return False

    if not _is_running():
        cmd = "docker run -d -p 80:80 -v {}:/usr/share/nginx/html/backups:ro" \
              " nginx".format(shared_dir)
        cluster.ssh_exec(host, cmd)
