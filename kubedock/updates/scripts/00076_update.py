from fabric.api import run


CONF = '/etc/sysctl.d/75-kuberdock.conf'


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Add kernel parameters to make pod isolation work...')

    run('sed -i "/net.bridge.bridge-nf-call-ip6\?tables/d" {0}'.format(CONF))

    run("echo net.bridge.bridge-nf-call-iptables = 1 >> {0}".format(CONF))
    run("echo net.bridge.bridge-nf-call-ip6tables = 1 >> {0}".format(CONF))

    run("sysctl -w net.bridge.bridge-nf-call-iptables=1")
    run("sysctl -w net.bridge.bridge-nf-call-ip6tables=1")


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')
