from fabric.api import run

FSTAB_BACKUP="/var/lib/kuberdock/backups/fstab.pre-swapoff"

def upgrade(upd, with_testing, *args, **kwargs):
    pass

def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass

def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Disabling swap and backing up fstab to {0}...'.format(FSTAB_BACKUP))
    run('swapoff -a')
    run('mkdir -p /var/lib/kuberdock/backups')
    run('test -f {0} && echo "{0} is already exists" || cp /etc/fstab {0}'.format(FSTAB_BACKUP))
    run("sed -r -i '/[[:space:]]+swap[[:space:]]+/d' /etc/fstab")

def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Rolling back fstab and re-enabling swap...')
    run('cp '+FSTAB_BACKUP+' /etc/fstab')
    run('swapon -a')
