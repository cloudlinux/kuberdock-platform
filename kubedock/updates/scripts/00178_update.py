from fabric.api import put, run


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading backup symlinks ...')

    put("/var/opt/kuberdock/backup_node.py", "/usr/bin/kd-backup-node")
    put("/var/opt/kuberdock/backup_node_merge.py", "/usr/bin/kd-backup-node-merge")

    run('chmod +x  "/usr/bin/kd-backup-node-merge"')
    run('chmod +x  "/usr/bin/kd-backup-node"')


def downgrade_node(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading backup symlinks ...')

    run('rm  "/usr/bin/kd-backup-node-merge"')
    run('rm  "/usr/bin/kd-backup-node"')
