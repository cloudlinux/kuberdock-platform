import json
import os
from datetime import timedelta
from fabric.api import run, get, put

from kubedock.updates import helpers
from kubedock.core import ConnectionPool, db
from kubedock.system_settings.fixtures import add_system_settings
from kubedock.system_settings.models import SystemSettings


#00110_update.py
CONF = '/etc/rsyslog.d/kuberdock.conf'
PARAM = '$LocalHostName'

#00111_update.py
KUBELET_PATH = '/etc/kubernetes/kubelet'
KUBELET_ARG = 'KUBELET_ARGS'
KUBELET_MULTIPLIERS = ' --cpu-multiplier=8 --memory-multiplier=4'
KUBELET_TEMP_PATH = '/tmp/kubelet'


def upgrade(upd, with_testing, *args, **kwargs):
    #00109_update.py
    upd.print_log('Update system settings scheme...')
    helpers.upgrade_db()

    redis = ConnectionPool.get_connection()
    old_settings = SystemSettings.get_all()

    # backup for downgrade
    if not redis.get('old_system_settings'):
        redis.set('old_system_settings', json.dumps(old_settings),
                  ex=int(timedelta(days=7).total_seconds()))

    SystemSettings.query.delete()
    add_system_settings()
    for param in old_settings:
        SystemSettings.set_by_name(param.get('name'), param.get('value'), commit=False)
    db.session.commit()

    #00111_update.py
    res = helpers.install_package('kubernetes-master-1.1.3', with_testing)
    if res:
        raise helpers.UpgradeError('Failed to update kubernetes on master')
    helpers.restart_master_kubernetes()

    #00113_update.py
    upd.print_log('Adding "count_type" column to packages...')
    helpers.upgrade_db(revision='42b36be03945')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    #00109_update.py
    upd.print_log('Downgrade system_settings scheme...')

    redis = ConnectionPool.get_connection()
    old_settings = redis.get('old_system_settings')
    if old_settings:
        # restore old settings
        SystemSettings.query.delete()
        for param in json.loads(old_settings):
            db.session.add(
                SystemSettings(name=param.get('name'),
                               label=param.get('label'),
                               description=param.get('description'),
                               placeholder=param.get('placeholder'),
                               options=json.dumps(param.get('options')),
                               value=param.get('value')))
        db.session.commit()

    #00113_update.py
    upd.print_log('Removing "count_type" column from packages...')
    helpers.downgrade_db(revision='27c8f4c5f242')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    run('yum --enablerepo=kube,kube-testing clean metadata')
    #00110_update.py
    upd.print_log('Fix node hostname in rsyslog configuration...')
    run("sed -i 's/^{0} .*/{0} {1}/' {2}".format(PARAM, env.host_string, CONF))
    run('systemctl restart rsyslog')

    #00111_update.py
    res = helpers.remote_install('kubernetes-node-1.1.3', with_testing)
    upd.print_log(res)
    if res.failed:
        raise helpers.UpgradeError('Failed to update kubernetes on node')
    get(KUBELET_PATH, KUBELET_TEMP_PATH)
    lines = []
    with open(KUBELET_TEMP_PATH) as f:
        lines = f.readlines()
    with open(KUBELET_TEMP_PATH, 'w+') as f:
        for line in lines:
            if KUBELET_ARG in line and KUBELET_MULTIPLIERS not in line:
                s = line.split('"')
                s[1] += KUBELET_MULTIPLIERS
                line = '"'.join(s)
            f.write(line)
    put(KUBELET_TEMP_PATH, KUBELET_PATH)
    os.remove(KUBELET_TEMP_PATH)
    helpers.restart_node_kubernetes(with_enable=True)


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass
