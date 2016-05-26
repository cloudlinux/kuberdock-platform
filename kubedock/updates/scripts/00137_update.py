from kubedock.updates import helpers
from kubedock.system_settings.models import SystemSettings


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading db...')
    helpers.upgrade_db(revision='3c832810a33c')
    upd.print_log('Raise max kubes to 64')
    max_kubes = 'max_kubes_per_container'
    old_value = SystemSettings.get_by_name(max_kubes)
    if old_value == '10':
        SystemSettings.set_by_name(max_kubes, 64)


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading db...')
    helpers.downgrade_db(revision='220dacf65cba')
