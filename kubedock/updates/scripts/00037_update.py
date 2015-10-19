from fabric.api import run


def upgrade(*args, **kwargs):
    pass


def downgrade(*args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Allow registries with self-sighned serts...')
    upd.print_log(run(r'''
        sed -i.old "s|^# \(INSECURE_REGISTRY='--insecure-registry\)'|\1=0.0.0.0/0'|" \
            /etc/sysconfig/docker
    '''))
    upd.print_log(run('systemctl restart docker'))


def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
    upd.print_log('Forbid registries with self-sighned serts...')
    upd.print_log(run(r'''
        sed -i.old "s|^\(INSECURE_REGISTRY='--insecure-registry\)=0.0.0.0/0'|# \1\'|"
            /etc/sysconfig/docker
    '''))
    upd.print_log(run('systemctl restart docker'))
