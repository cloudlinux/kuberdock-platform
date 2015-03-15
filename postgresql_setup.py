#!/usr/bin/python
import hashlib
import os
import pwd
import subprocess
import tempfile


DB_USER = 'kuberdock'
DB_PASSWORD = 'Iwb4gDo'
DB_NAME = 'kuberdock'

CONF_PATH = '/var/lib/pgsql/data/pg_hba.conf'


def create_user():
    curr_user = os.geteuid();
    target = pwd.getpwnam('postgres')
    try:
        os.seteuid(target.pw_uid)
        m = hashlib.md5()
        m.update(DB_PASSWORD)
        m.update(DB_USER)
        command = """CREATE USER %s PASSWORD 'md5%s'""" % (DB_USER, m.hexdigest())
        subprocess.check_call(['psql', '-c', command])
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
    target_user = create_user()
    modify_config(target_user)
