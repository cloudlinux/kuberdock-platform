#!/usr/bin/python

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

import hashlib
import os
import pwd
import subprocess
import sys
import tempfile

from kubedock.settings import DB_USER, DB_PASSWORD, DB_NAME

CONF_PATH = '/var/lib/pgsql/data/pg_hba.conf'


def create_user(no_utf8=False):
    curr_user = os.geteuid();
    target = pwd.getpwnam('postgres')
    try:
        os.seteuid(target.pw_uid)
        m = hashlib.md5()
        m.update(DB_PASSWORD)
        m.update(DB_USER)
        command = """CREATE USER %s PASSWORD 'md5%s'""" % (DB_USER, m.hexdigest())
        subprocess.check_call(['psql', '-c', command])
        if no_utf8:
            command = """CREATE DATABASE %s OWNER %s""" % (DB_NAME, DB_USER)
        else:
            command = """CREATE DATABASE %s OWNER %s ENCODING 'UTF8'""" % (DB_NAME, DB_USER)
        subprocess.check_call(['psql', '-c', command])
        os.seteuid(curr_user)
    except Exception, e:
        raise SystemExit(str(e))
    return target


def modify_config(target_user):
    fh, fpath = tempfile.mkstemp(dir=os.path.dirname(CONF_PATH), prefix='kube_')
    with os.fdopen(fh, 'w') as o:
        with open(CONF_PATH) as i:
            for l in i:
                if l.startswith('host'):
                    l = l.replace('ident', 'md5')
                o.write(l)
    os.rename(fpath, CONF_PATH)
    os.chown(CONF_PATH, target_user.pw_uid, target_user.pw_gid)


if __name__ == '__main__':
    no_utf8 = False
    if len(sys.argv) > 1 and sys.argv[1] == 'no_utf8':
        no_utf8 = True
    target_user = create_user(no_utf8)
    modify_config(target_user)
