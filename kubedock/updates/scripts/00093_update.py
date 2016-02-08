from fabric.api import run


CONF = '/etc/rsyslog.d/kuberdock.conf'
PARAM1 = '$template'
PARAM2 = '*.* @127.0.0.1:5140'
TEMPLATE = ('LongTagForwardFormat,"<%PRI%>%TIMESTAMP:::date-rfc3339% %HOSTNAME%'
            ' %syslogtag%%msg:::sp-if-no-1st-sp%%msg%"')
TEMPLATE_NAME = 'LongTagForwardFormat'


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Use custom log template with rsyslog...')

    run("sed -i '/^{0}/d' {1}".format(PARAM1, CONF))
    run("sed -i '/^{0}/d' {1}".format(PARAM2, CONF))
    run("sed -i '$ a{0} {1}' {2}".format(PARAM1, TEMPLATE, CONF))
    run("sed -i '$ a{0};{1}' {2}".format(PARAM2, TEMPLATE_NAME, CONF))
    run('systemctl restart rsyslog')


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')
