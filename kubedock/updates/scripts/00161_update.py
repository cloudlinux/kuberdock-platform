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
