from kubedock.updates import helpers
from kubedock.system_settings.models import SystemSettings
from kubedock.billing.models import Kube


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading db...')
    helpers.upgrade_db(revision='3c832810a33c')
    upd.print_log('Raise max kubes to 64')
    max_kubes = 'max_kubes_per_container'
    old_value = SystemSettings.get_by_name(max_kubes)
    if old_value == '10':
        SystemSettings.set_by_name(max_kubes, 64)
    upd.print_log('Update kubes')
    small = Kube.get_by_name('Small')
    standard = Kube.get_by_name('Standard')
    if small:
        small.cpu = 0.12
        small.name = 'Tiny'
        small.memory = 64
        if small.is_default and standard:
            small.is_default = False
            standard.is_default = True
        small.save()
    if standard:
        standard.cpu = 0.25
        standard.memory = 128
        standard.save()
    high = Kube.get_by_name('High memory')
    if high:
        high.cpu = 0.25
        high.memory = 256
        high.disk_space = 3
        high.save()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading db...')
    helpers.downgrade_db(revision='220dacf65cba')
