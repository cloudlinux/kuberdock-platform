from fabric.operations import run


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Update node {} local PV SELinux labels...'.format(
        env.host_string))
    run("chcon -Rv --range=s0 /var/lib/kuberdock/storage/")


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass
