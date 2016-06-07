from kubedock.updates.helpers import restart_service


def upgrade(*args, **kwargs):
    restart_service('nginx')


def downgrade(*args, **kwars):
    pass
