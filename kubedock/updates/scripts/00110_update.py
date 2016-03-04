from fabric.api import run


CONF = '/etc/rsyslog.d/kuberdock.conf'
PARAM = '$LocalHostName'


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Fix node hostname in rsyslog configuration...')
    run("sed -i 's/^{0} .*/{0} {1}/' {2}".format(PARAM, env.host_string, CONF))
    run('systemctl restart rsyslog')


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass
