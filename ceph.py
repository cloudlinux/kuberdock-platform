
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

import argparse
import os
import shutil
import tempfile

from fabric.api import cd, env, get, run, put, settings

TMPDIR = '/tmp'


def parse_args():
    args = argparse.ArgumentParser("Setup ceph client to remote host")
    args.add_argument('node', help="Name or IP address of node to install to")
    args.add_argument('-C', '--ceph', help="Name of IP address of ceph admin node")
    args.add_argument('-u', '--user', default='root', help="Username")
    args.add_argument('-p', '--password', help="Password")
    args.add_argument('-d', '--deploy-dir', default='/var/opt/deploy',
                      help="Directory to put deploy script to")
    args.add_argument('-D', '--deploy-script', default='ceph_install.sh',
                      help="Deploy script")
    args.add_argument('-w', '--app-dir', default='/var/opt/kuberdock',
                      help="Directory of web-application")
    args.add_argument('-c', '--conf-dir', default='/etc/ceph',
                      help="Directory of ceph-configs")
    args.add_argument('-T', '--temp-dir', default=TMPDIR, help="Temp directory")
    return args.parse_args()


if __name__ == '__main__':
    args = parse_args()
    env.user = args.user
    env.password = args.password
    # If we know ceph admin host, we would try to copy config from it
    if args.ceph is not None:
        with settings(host_string=args.ceph):
            try:
                tmp_store = tempfile.mkdtemp(prefix='kuberdock_', dir=args.temp_dir)
            except OSError:
                tmp_store = tempfile.mkdtemp(prefix='kuberdock_', dir=TMPDIR)
            get(args.conf_dir + '/ceph.*', tmp_store)

    with settings(host_string=args.node):
        with settings(warn_only=True):
            run('mkdir ' + args.conf_dir)
            run('mkdir ' + args.deploy_dir)
        if args.ceph is not None:
            put(tmp_store + '/ceph.*', args.conf_dir)
            put(os.path.join(args.app_dir, args.deploy_script), args.deploy_dir)
            shutil.rmtree(tmp_store)
        with cd(args.deploy_dir):
            run('sh ' + args.deploy_script)
