from kubedock.updates import helpers
from fabric.api import run


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Reloading flannel...')
    helpers.local('systemctl daemon-reload')
    helpers.local('systemctl restart flanneld')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Reloading flannel...')
    helpers.local('systemctl daemon-reload')
    helpers.local('systemctl restart flanneld')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log(helpers.remote_install('kernel-devel', with_testing))
    upd.print_log('Updating flannel...')
    upd.print_log(helpers.remote_install('flannel-0.5.3', with_testing))
    upd.print_log(run('systemctl daemon-reload'))
    upd.print_log(run('systemctl restart flanneld'))


def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
    upd.print_log(helpers.remote_install('kernel-devel', with_testing,
                                         action='remove'))
    upd.print_log('Downgrade flannel...')
    upd.print_log(helpers.remote_install('flannel-0.5.1', with_testing,
                                         action='downgrade'))
    upd.print_log(run('systemctl daemon-reload'))
    upd.print_log(run('systemctl restart flanneld'))
