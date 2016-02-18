from fabric.api import put


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Update fslimit.py script...')
    upd.print_log(put('/var/opt/kuberdock/fslimit.py',
                      '/var/lib/kuberdock/scripts/fslimit.py',
                      mode=0755))


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade_node provided')
