
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

from StringIO import StringIO
import json

from fabric.operations import put

from kubedock import settings
from kubedock.users import User
from node_network_plugin import KD_CONF_PATH
from node_network_plugin import PLUGIN_PATH


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    # AC-4145: This fixes an issue for a customers who already applied
    # broken 160 script version.

    # Putting the new plugin
    upd.print_log('Update network plugin...')
    put('/var/opt/kuberdock/node_network_plugin.sh',
        PLUGIN_PATH + 'kuberdock')
    put('/var/opt/kuberdock/node_network_plugin.py',
        PLUGIN_PATH + 'kuberdock.py')

    # Rewriting config with a correct contents.
    kd_conf = {
        'nonfloating_public_ips':
            'yes' if settings.NONFLOATING_PUBLIC_IPS else 'no',
        'master': settings.MASTER_IP,
        'node': env.host_string,
        'token': User.get_internal().get_token()
    }
    put(StringIO(json.dumps(kd_conf)), KD_CONF_PATH)


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass
