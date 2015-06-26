"""
Most of this helper functions should be used for constructing 000XX_update.py
scripts.
They must be backward compatible because they may be used during applying
older 000XX_update.py scripts too
"""

import os
import re
import subprocess
from kubedock import settings
from kubedock.sessions import SessionData
from .models import Updates, db

# For convenience to use in update scripts:
from flask.ext.migrate import upgrade as upgradedb


class UPDATE_STATUSES:
    started = 'started'
    applied = 'applied'
    failed = 'failed'
    failed_downgrade = 'downgrade failed too'


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


def get_available_updates():
    patt = re.compile(r'^[0-9]{5}_update\.py$')
    return sorted(filter(patt.match, os.listdir(settings.UPDATES_PATH)))


def get_applied_updates():
    return sorted(
        [i.fname for i in Updates.query.filter_by(status=UPDATE_STATUSES.applied).all()])


def print_log(upd_obj, msg):
    print msg
    upd_obj.log = (upd_obj.log or '') + msg + '\n'
    db.session.commit()


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


# remote node, async, other params?
def restart_service(service):
    return subprocess.call(['systemctl', 'restart', service])


# do it inside updates
def close_all_sessions():
    return SessionData.query.delete()
