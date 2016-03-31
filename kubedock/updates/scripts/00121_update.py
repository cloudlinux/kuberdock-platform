"""Set proper performance profiles for nodes"""
from fabric.api import run


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    run('yum install -y tuned')
    run('systemctl enable tuned')
    run('systemctl start tuned')
    result = run('systemd-detect-virt --vm --quiet')
    if result.return_code:
        run('tuned-adm profile latency-performance')
    else:
        run('tuned-adm profile virtual-guest')


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass
