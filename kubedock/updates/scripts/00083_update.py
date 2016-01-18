from fabric.api import run, put

from kubedock.updates import helpers

from kubedock.users.models import User
from kubedock.static_pages.models import MenuItem, db
from kubedock.settings import KUBERDOCK_INTERNAL_USER, MASTER_IP
from kubedock.kapi.nodes import (
    get_kuberdock_logs_config,
    get_kuberdock_logs_pod_name,
)
from kubedock.validation import check_internal_pod_data
from kubedock.kapi.podcollection import PodCollection
# 00076_update.py
CONF = '/etc/sysctl.d/75-kuberdock.conf'

# 00082_update.py
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


def upgrade(upd, with_testing, *args, **kwargs):
    helpers.upgrade_db()
    # 00077_update.py
    upd.print_log('Clear cache...')
    from kubedock.core import ConnectionPool
    redis = ConnectionPool.get_connection()
    redis.delete('KDCOLLECTION')
    # 00081_update.py
    upd.print_log('Fix urls in main menu...')
    for item in MenuItem.query.all():
        if item.path:
            item.path = item.path.replace('/', '#', 1).rstrip('/')
    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    # 00080_update.py
    upd.print_log('Downgrading db...')
    helpers.downgrade_db(revision='37ccf7811576')
    # 00081_update.py
    upd.print_log('Return old urls')
    for item in MenuItem.query.all():
        if item.path:
            item.path = '{0}/'.format(item.path.replace('#', '/', 1))
    db.session.commit()


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    # 00076_update.py
    upd.print_log('Add kernel parameters to make pod isolation work...')

    run('sed -i "/net.bridge.bridge-nf-call-ip6\?tables/d" {0}'.format(CONF))

    run("echo net.bridge.bridge-nf-call-iptables = 1 >> {0}".format(CONF))
    run("echo net.bridge.bridge-nf-call-ip6tables = 1 >> {0}".format(CONF))

    run("sysctl -w net.bridge.bridge-nf-call-iptables=1")
    run("sysctl -w net.bridge.bridge-nf-call-ip6tables=1")

    # 00079_update.py
    upd.print_log('Copy Elasticsearch config maker...')
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

    run('docker pull kuberdock/elasticsearch:1.5')

    PodCollection(ki).update(logs_pod['id'], {'command': 'start'})

    # 00082_update.py
    upd.print_log('Upgrading nodes with docker-cleaner.sh')
    run("cat > /var/lib/kuberdock/scripts/docker-cleaner.sh << 'EOF' {0}" .format(DOCKERCLEANER))
    run("""chmod +x /var/lib/kuberdock/scripts/docker-cleaner.sh""")
    run("""crontab -l | { cat; echo "0 */6 * * * /var/lib/kuberdock/scripts/docker-cleaner.sh"; } | crontab - """)


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    # 00082_update.py
    upd.print_log('Downgrading nodes with docker-cleaner.sh ')
    run("""rm -f /var/lib/kuberdock/scripts/docker-cleaner.sh""")
    run("""crontab -l | grep -v "docker-cleaner.sh" | crontab - """)
