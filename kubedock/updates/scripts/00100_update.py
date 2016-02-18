from datetime import timedelta
from urlparse import urlparse
from shutil import copyfile

from fabric.api import run, put, local
from sqlalchemy import Table

from kubedock.updates import helpers
from kubedock.core import ConnectionPool, db
from kubedock.system_settings.fixtures import add_system_settings
from kubedock.system_settings.models import SystemSettings
from kubedock.users.models import User
from kubedock.settings import KUBERDOCK_INTERNAL_USER, MASTER_IP
from kubedock.kapi.nodes import (
    get_kuberdock_logs_config,
    get_kuberdock_logs_pod_name,
)
from kubedock.kapi.podcollection import PodCollection
from kubedock.validation import check_internal_pod_data


DOCKERCLEANER = \
"""
#!/bin/bash

# the following command will not remove running containers, just displaying errors on them
docker rm $(docker ps -a -q)
docker rm $(docker ps -f=status=exited -q)
docker rmi `docker images -qf 'dangling=true'`
docker rm -f `docker ps -a | grep Dead | awk '{print $1 }'`

EOF
"""

CONF = '/etc/rsyslog.d/kuberdock.conf'
PARAM1 = '$template'
PARAM2 = '*.* @127.0.0.1:5140'
TEMPLATE = ('LongTagForwardFormat,"<%PRI%>%TIMESTAMP:::date-rfc3339% %HOSTNAME%'
            ' %syslogtag%%msg:::sp-if-no-1st-sp%%msg%"')
TEMPLATE_NAME = 'LongTagForwardFormat'

FSTAB_BACKUP = "/var/lib/kuberdock/backups/fstab.pre-swapoff"


def upgrade(upd, with_testing, *args, **kwargs):
    # 00090_update.py
    upd.print_log('Update system settings scheme...')
    helpers.upgrade_db()

    redis = ConnectionPool.get_connection()

    billing_apps_link = SystemSettings.get_by_name('billing_apps_link')
    persitent_disk_max_size = SystemSettings.get_by_name('persitent_disk_max_size')

    # backup for downgrade
    if not redis.get('old_billing_apps_link'):
        redis.set('old_billing_apps_link', billing_apps_link or '',
                  ex=int(timedelta(days=7).total_seconds()))
    if not redis.get('old_persitent_disk_max_size'):
        redis.set('old_persitent_disk_max_size', persitent_disk_max_size,
                  ex=int(timedelta(days=7).total_seconds()))

    billing_url = (urlparse(billing_apps_link)._replace(path='', query='',
                                                        params='').geturl()
                   if billing_apps_link else None)
    SystemSettings.query.delete()
    add_system_settings()
    SystemSettings.set_by_name(
        'persitent_disk_max_size', persitent_disk_max_size, commit=False)
    SystemSettings.set_by_name('billing_url', billing_url, commit=False)
    db.session.commit()

    # 00094_update.py
    upd.print_log('Drop table "node_missed_actions" if exists')
    table = Table('node_missed_actions', db.metadata)
    table.drop(bind=db.engine, checkfirst=True)
    db.session.commit()

    # 00095_update.py
    upd.print_log('Restart k8s2etcd service')
    upd.print_log(helpers.local('systemctl restart kuberdock-k8s2etcd'))

    # 00098_update.py
    copyfile('/var/opt/kuberdock/conf/sudoers-nginx.conf', '/etc/sudoers.d/nginx')
    local('chown nginx:nginx /etc/nginx/conf.d/shared-kubernetes.conf')
    local('chown nginx:nginx /etc/nginx/conf.d/shared-etcd.conf')

    helpers.close_all_sessions()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    # 00090_update.py
    upd.print_log('Downgrade system_settings scheme...')

    redis = ConnectionPool.get_connection()
    SystemSettings.query.delete()
    db.session.add_all([
        SystemSettings(name='billing_apps_link',
                       label='Link to billing system script',
                       description='Link to predefined application request processing script',
                       placeholder='http://whmcs.com/script.php',
                       value=redis.get('old_billing_apps_link')),
        SystemSettings(name='persitent_disk_max_size',
                       value=redis.get('old_persitent_disk_max_size'),
                       label='Persistent disk maximum size',
                       description='maximum capacity of a user container persistent disk in GB',
                       placeholder='Enter value to limit PD size')
    ])
    db.session.commit()

    helpers.downgrade_db(revision='27ac98113841')

    # 00094_update.py
    try:
        from kubedock.nodes.models import NodeMissedAction
    except ImportError:
        upd.print_log('Cannot find NodeMissedAction model')
    else:
        upd.print_log('Create table for NodeMissedAction model if not exists')
        NodeMissedAction.__table__.create(bind=db.engine, checkfirst=True)
        db.session.commit()

    # 00099_update.py
    helpers.downgrade_db(revision='46bba639e6fb')   # first of rc4


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    run('yum --enablerepo=kube,kube-testing clean metadata')

    # 00091_update.py
    upd.print_log('Upgrading nodes with docker-cleaner.sh')
    run("""rm -f /var/lib/kuberdock/scripts/docker-cleaner.sh""")
    run("""crontab -l | grep -v "docker-cleaner.sh" | crontab - """)

    # 00092_update.py
    put('/var/opt/kuberdock/node_network_plugin.sh',
        '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/kuberdock')

    # 00093_update.py
    upd.print_log('Use custom log template with rsyslog...')
    run("sed -i '/^{0}/d' {1}".format(PARAM1, CONF))
    run("sed -i '/^{0}/d' {1}".format(PARAM2, CONF))
    run("sed -i '$ a{0} {1}' {2}".format(PARAM1, TEMPLATE, CONF))
    run("sed -i '$ a{0};{1}' {2}".format(PARAM2, TEMPLATE_NAME, CONF))
    run('systemctl restart rsyslog')

    # 00096_update.py
    upd.print_log('Disabling swap and backing up fstab to {0}...'.format(FSTAB_BACKUP))
    run('swapoff -a')
    run('mkdir -p /var/lib/kuberdock/backups')
    run('test -f {0} && echo "{0} is already exists" || cp /etc/fstab {0}'.format(FSTAB_BACKUP))
    run("sed -r -i '/[[:space:]]+swap[[:space:]]+/d' /etc/fstab")

    # 00097_update.py
    upd.print_log('Update elasticsearch for logs...')
    upd.print_log(put('/var/opt/kuberdock/make_elastic_config.py',
                      '/var/lib/elasticsearch',
                      mode=0755))
    upd.print_log('Update logging pod...')
    ki = User.filter_by(username=KUBERDOCK_INTERNAL_USER).first()
    pod_name = get_kuberdock_logs_pod_name(env.host_string)

    for pod in PodCollection(ki).get(as_json=False):
        if pod['name'] == pod_name:
            break
    else:
        return

    PodCollection(ki).delete(pod['id'], force=True)
    logs_config = get_kuberdock_logs_config(
        env.host_string,
        pod_name,
        pod['kube_type'],
        pod['containers'][0]['kubes'],
        pod['containers'][1]['kubes'],
        MASTER_IP,
        ki.get_token(),
    )
    check_internal_pod_data(logs_config, user=ki)
    logs_pod = PodCollection(ki).add(logs_config, skip_check=True)

    run('docker pull kuberdock/elasticsearch:2.2')
    run('docker pull kuberdock/fluentd:1.5')

    PodCollection(ki).update(logs_pod['id'], {'command': 'start'})


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    # 00091_update.py
    upd.print_log('Downgrading nodes with docker-cleaner.sh')
    run("cat > /var/lib/kuberdock/scripts/docker-cleaner.sh << 'EOF' {0}"
    .format(DOCKERCLEANER))
    run("""chmod +x /var/lib/kuberdock/scripts/docker-cleaner.sh""")
    run("""crontab -l | { cat; echo "0 */6 * * * /var/lib/kuberdock/scripts/docker-cleaner.sh"; } | crontab - """)

    # 00096_update.py
    upd.print_log('Rolling back fstab and re-enabling swap...')
    run('cp '+FSTAB_BACKUP+' /etc/fstab')
    run('swapon -a')
