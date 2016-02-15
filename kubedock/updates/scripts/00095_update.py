from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Restart k8s2etcd service')
    upd.print_log(helpers.local('systemctl restart kuberdock-k8s2etcd'))


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')
