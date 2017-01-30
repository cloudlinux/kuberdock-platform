
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

import json

from kubedock.pods.models import Pod
from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading db...')
    helpers.upgrade_db(revision='5173b3f01db4')

    upd.print_log('Clear pod configs from old api...')
    for pod in Pod.query.all():
        conf = json.loads(pod.config)
        try:
            del conf['save_only']
        except KeyError:
            pass
        pod.config = json.dumps(conf)
    upd.print_log('Done.')


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Downgrading db...')
    helpers.downgrade_db()
