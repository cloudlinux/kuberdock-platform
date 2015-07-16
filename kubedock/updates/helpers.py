"""
Most of this helper functions should be used for constructing 000XX_update.py
scripts.
"""

import os
import re
import subprocess
from fabric.api import run, local as fabric_local
from kubedock import settings
from kubedock.sessions import SessionData

# For convenience to use in update scripts:
from flask.ext.migrate import upgrade as upgradedb


class UpgradeError(Exception):
    """
    Raise it if error "expected" and downgrade_func can handle it properly.
    Raise it when need to start downgrade right now.
    Pass some 'code' that helps downgrade_func to determine where was an error.
    If this code is 0 then exception is some kind of "unexpected"
    """
    def __init__(self, msg, code=0):
        # By this code we could determine on which point was error, but we still
        # need full downgrade for consistency
        super(UpgradeError, self).__init__(msg)
        self.code = code

    def __repr__(self):
        return "<{0}. message='{1}' code={2}>".format(self.__class__.__name__,
                                                      self.message,
                                                      self.code)

    def __str__(self):
        return "{0}. Code={1}".format(self.message, self.code)


def local(*args, **kwargs):
    if 'capture' not in kwargs:
        kwargs['capture'] = True
    return fabric_local(*args, **kwargs)


def _make_yum_opts(pkg, testing=False, action='install', noprogress=False):
    opts = ['yum', '--enablerepo=kube',
            '-y',
            action] + pkg.split()
    if testing:
        opts[1] += ',kube-testing'
    if noprogress:
        opts += ['-d', '1']
    return opts


def install_package(pkg, testing=False, reinstall=False):
    """
    :return: exit code
    """
    return subprocess.call(
        _make_yum_opts(pkg, testing, 'reinstall' if reinstall else 'install'))


def remote_install(pkg, testing=False, action='install'):
    return run(' '.join(_make_yum_opts(pkg, testing, action, True)))


def _set_param(text, var, param, value):
    res = param + value

    def x(matchobj):
        m = matchobj.group(1).strip()
        if m == '':
            return '{0}="{1}"'.format(var, res)
        if param in m:
            return '{0}="{1}"'.format(var,
                                      re.sub(r'(.*){0}(\w+)(.*)'.format(param),
                                             r'\g<1>{0}\g<3>'.format(res), m))
        return '{0}="{1} {2}"'.format(var, m, res)
    return re.sub(r'{0}="(.*?)"'.format(var), x, text, re.DOTALL)


def set_evicting_timeout(timeout):
    """
    Set pod evicting timeout and restarts kube-controller-manager
    :param timeout: string representing timeout like '5m0s' (default value)
    :return:
    """
    config_file = '/etc/kubernetes/controller-manager'
    with open(config_file, 'rt') as fr:
        text = fr.read()
    res = _set_param(text, "KUBE_CONTROLLER_MANAGER_ARGS",
                     "--pod-eviction-timeout=", timeout)
    with open(config_file, 'wt') as fw:
        fw.write(res)
    return restart_service('kube-controller-manager')


def restart_master_kubernetes(with_enable=False):
    res = subprocess.call(['systemctl', 'daemon-reload'])
    if res > 0:
        return 'systemctl daemon-reload', res
    for i in ('kube-apiserver', 'kube-scheduler', 'kube-controller-manager',):
        res = restart_service(i)
        if res > 0:
            return i, res
        if with_enable:
            res = subprocess.call(['systemctl', 'reenable', i])
            if res > 0:
                return 'Error_reenable {0}'.format(i), res
    return 0, 0


def restart_node_kubenetes(with_docker=False, with_enable=False):
    """
    :return: Tuple: service on which restart was error or 0, + fabric res
    """
    res = run('systemctl daemon-reload')
    if res.failed:
        return 'Error_daemon-reload', res
    services = ('kubelet', 'kube-proxy',)
    if with_docker:
        services += ('docker',)
    for i in services:
        res = run('systemctl restart ' + i)
        if res.failed:
            return i, res
        if with_enable:
            res = run('systemctl reenable ' + i)
            if res.failed:
                return i, res
    return 0, 'All node services restarted'


def set_maintenance(state):
    if state:
        open(settings.MAINTENANCE_LOCK_FILE, 'a').close()
    else:
        try:
            os.unlink(settings.MAINTENANCE_LOCK_FILE)
            # flush queue of pods and nodes(maybe for nodes after ALL upgrade)
        except OSError:
            pass


def get_maintenance():
    if os.path.exists(settings.MAINTENANCE_LOCK_FILE):
        return True
    return False


def restart_service(service):
    return subprocess.call(['systemctl', 'restart', service])


# do it inside update scripts
def close_all_sessions():
    return SessionData.query.delete()
