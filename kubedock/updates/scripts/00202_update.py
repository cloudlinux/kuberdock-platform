"""Update fluentd image in logs pods"""
from StringIO import StringIO
from fabric.operations import run, put

from kubedock.kapi import nodes
from kubedock.kapi.podcollection import PodCollection
from kubedock.users.models import User


RSYSLOG_CONF = '/etc/rsyslog.d/kuberdock.conf'


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    _00202_upgrade_node(upd, env)


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass


def _00202_upgrade_node(upd, env):
    """Update log pod"""

    upd.print_log("Upgrading logs pod ...")
    ki = User.get_internal()
    pod_name = nodes.get_kuberdock_logs_pod_name(env.host_string)

    for pod in PodCollection(ki).get(as_json=False):
        if pod['name'] == pod_name:
            PodCollection(ki).delete(pod['id'], force=True)
            break
    else:
        upd.print_log(u"Warning: logs pod '{}' not found".format(pod_name))

    run('docker pull kuberdock/elasticsearch:2.2')
    run('docker pull kuberdock/fluentd:1.8')
    log_pod = nodes.create_logs_pod(env.host_string, ki)

    # Also we should update rsyslog config, because log pod IP was changed.
    pod_ip = log_pod['podIP']
    put(
        StringIO(
            '$LocalHostName {node_name}\n'
            '$template LongTagForwardFormat,'
            '"<%PRI%>%TIMESTAMP:::date-rfc3339% %HOSTNAME% '
            '%syslogtag%%msg:::sp-if-no-1st-sp%%msg%"\n'
            '*.* @{pod_ip}:5140;LongTagForwardFormat\n'.format(
                node_name=env.host_string, pod_ip=pod_ip
            )
        ),
        RSYSLOG_CONF,
        mode=0644
    )
    run('systemctl restart rsyslog')

    upd.print_log("Logs pod successfully upgraded")
