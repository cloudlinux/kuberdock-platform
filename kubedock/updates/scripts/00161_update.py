import StringIO

from fabric.operations import put

from kubedock import settings
from kubedock.users import User
from node_network_plugin import INI_PATH

KUBERDOCK_INI = '''NONFLOATING_PUBLIC_IPS={0}
MASTER={1}
NODE={2}
TOKEN={3}
'''


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    # AC-4145: This fixes an issue for a customers who already applied
    # broken 160 script version. Rewriting ini with a correct contents.
    upd.print_log('Updating kuberdock network plugin config...')
    token = User.get_internal().get_token()
    ini = KUBERDOCK_INI.format(
        'yes' if settings.NONFLOATING_PUBLIC_IPS else 'no',
        settings.MASTER_IP, env.host_string, token)
    put(StringIO.StringIO(ini), INI_PATH)


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass
