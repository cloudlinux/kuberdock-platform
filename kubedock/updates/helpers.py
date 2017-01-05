"""
Most of this helper functions should be used for constructing 000XX_update.py
scripts.
"""

import os
import re
import subprocess
import time

from fabric.api import run, env, output, local as fabric_local

from kubedock import settings
from kubedock.core import db
from kubedock.rbac.models import Role
from kubedock.sessions import SessionData
from kubedock.utils import send_event_to_role

# For convenience to use in update scripts:
from flask.ext.migrate import upgrade
# noinspection PyUnresolvedReferences
from flask.ext.migrate import downgrade as downgrade_db


def upgrade_db(*args, **kwargs):
    if 'revision' in kwargs:
        print 'Trying to apply db revision:', kwargs.pop('revision')
    return upgrade(*args, **kwargs)


def setup_fabric():
    env.user = 'root'
    env.abort_exception = UpgradeError
    env.key_filename = settings.SSH_KEY_FILENAME
    env.warn_only = True
    output.stdout = False
    output.aborts = False


class UpgradeError(Exception):
    """
    Raise it if error "expected" and downgrade_func can handle it properly.
    Raise it when need to start downgrade right now.
    Pass some 'code' that helps downgrade_func to determine where was an error.
    If this code is 0 then exception is some kind of "unexpected"
    """

    def __init__(self, msg, code=0):
        # By this code we could determine on which point was error, but we
        # still need full downgrade for consistency
        super(UpgradeError, self).__init__(msg)
        self.code = code

    def __repr__(self):
        return "<{0}. message='{1}' code={2}>".format(self.__class__.__name__,
                                                      self.message,
                                                      self.code)

    def __str__(self):
        return "{0}. Code={1}".format(self.message, self.code)


def local(*args, **kwargs):
    kwargs.setdefault('capture', True)
    return fabric_local(*args, **kwargs)


def _make_yum_opts(pkg, testing=False, action='install', noprogress=False):
    opts = ['yum', '--enablerepo=kube', '-y', action] + pkg.split()
    if testing:
        opts[1] += ',kube-testing'
    if noprogress:
        opts += ['-d', '1']
    return opts


def install_package(pkg, testing=False, action='install'):
    """
    :return: exit code
    """
    return subprocess.call(
        _make_yum_opts(pkg, testing, action=action),
        env=dict(os.environ, LANG=settings.EXTERNAL_UTILS_LANG))


def remote_install(pkg, testing=False, action='install'):
    return run(' '.join(['LANG=' + settings.EXTERNAL_UTILS_LANG] +
                        _make_yum_opts(pkg, testing, action, True)))


def update_local_config_file(conf_file, new_vars):
    with open(conf_file, "r+") as conf:
        conf_str = conf.read()
        conf_str = _update_config_str(conf_str, new_vars)
        conf.seek(0)
        conf.write(conf_str)
        conf.truncate()


def update_remote_config_file(config_file, new_vars):
    conf_str = run("cat '{}'".format(config_file), quiet=True) \
        .replace('\r', '')
    conf_str = _update_config_str(conf_str, new_vars)
    conf_str = conf_str.replace("'", "'\\''")  # escape single quote
    run("echo -e '{}' > {}".format(conf_str, config_file), quiet=True)


def _update_config_str(conf_str, new_vars):
    for var, updates in new_vars.iteritems():
        for param, new_value in updates.iteritems():
            assert not re.findall('\s+', param)
            assert new_value is None or not re.findall('\s+', new_value)
            if new_value is None:
                conf_str = _unset_param(conf_str, var, param)
            else:
                conf_str = _set_param(conf_str, var, param, new_value)
    return conf_str


def _set_param(text, var, param, value):
    res = param + value

    def x(matchobj):
        m = matchobj.group(1).strip()
        if m == '':
            return '{0}="{1}"'.format(var, res)
        if param in m:
            return '{0}="{1}"'.format(
                var,
                re.sub(r'(.*){0}([^\s"]+)(.*)'.format(param),
                       r'\g<1>{0}\g<3>'.format(res), m))
        return '{0}="{1} {2}"'.format(var, m, res)

    return re.sub(r'{0}="(.*?)"'.format(var), x, text, re.DOTALL)


def _unset_param(text, var, param):
    def x(matchobj):
        m = matchobj.group(1).strip()
        if m == '':
            return '{0}=""'.format(var)
        if param in m:
            return '{0}="{1}"'.format(
                var,
                re.sub('{0}([^\s"]*)'.format(param), '', m))
        return '{0}="{1}"'.format(var, m)

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


def restart_node_kubernetes(with_docker=False, with_enable=False):
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
    return 0, 0


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


def stop_service(service):
    return subprocess.call(['systemctl', 'stop', service])


def start_service(service):
    return subprocess.call(['systemctl', 'start', service])


# Will be executed after successful upgrade only
def close_all_sessions():
    for (role_id,) in db.session.query(Role.id).all():
        send_event_to_role('refresh', {}, role_id)
    deleted = SessionData.query.delete()
    db.session.commit()
    return deleted


def reboot_node(db_upd):
    """
    :param db_upd: update database object
    :return:
    """
    db_upd.print_log("Rebooting node")
    run('(sleep 2; reboot) &', pty=False)


def fabric_retry(f, cmd, retry_pause, max_retries, exc_message=None, upd=None,
                 *f_args, **f_kwargs):
    """
    Retries the given function call until it succeed

    :param f: a function to retry, e.g. local or run
    :param cmd: command to execute
    :param retry_pause: pause between retries (seconds)
    :param max_retries: max retries num.
    :param exc_message: exception message template
    :param upd: db record of current update script
    :return: result of the cmd's stdout
    """
    for _ in range(max_retries):
        out = f(cmd, *f_args, **f_kwargs)
        if out.succeeded:
            return out
        if upd:
            upd.print_log('Retrying: {cmd}'.format(cmd=cmd))
        time.sleep(retry_pause)
    if exc_message:
        raise UpgradeError(exc_message.format(out=out), code=out.return_code)
