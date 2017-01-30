
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

import os
from ConfigParser import ConfigParser

from fabric.operations import run

from kubedock import settings

KUBERDOCK_MAIN_CONFIG = '/etc/sysconfig/kuberdock/kuberdock.conf'


def upgrade(upd, with_testing, *args, **kwargs):
    try:
        from kubedock import amazon_settings
    except ImportError:
        upd.print_log('Not AWS, skipping')
        return

    aws_settings_names = ['AVAILABILITY_ZONE', 'AWS', 'AWS_ACCESS_KEY_ID',
                          'AWS_SECRET_ACCESS_KEY', 'REGION']

    config = ConfigParser()

    with open(settings.KUBERDOCK_SETTINGS_FILE, 'r+') as f:
        config.readfp(f)

        for setting in aws_settings_names:
            config.set('main', setting, getattr(amazon_settings, setting))
        config.set('main', 'AWS_EBS_DEFAULT_SIZE', 20)

        f.seek(0)
        config.write(f)

    run('rm {}'.format(os.path.join(settings.APP_ROOT, 'amazon_settings.py')))


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    pass


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass
