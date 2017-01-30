
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import datetime
from fabric.api import run, put
from sqlalchemy import Table
from kubedock.core import db
from kubedock.nodes.models import NodeAction
from kubedock.system_settings.models import SystemSettings
from kubedock.rbac.fixtures import add_permissions, Permission, Resource
from kubedock.updates import helpers
from kubedock.usage.models import PersistentDiskState
from kubedock.pods.models import PersistentDisk, PersistentDiskStatuses

# 00115
DOCKER_SERVICE_FILE = '/etc/systemd/system/docker.service'
DOCKER_SERVICE = r'''[Unit]
Description=Docker Application Container Engine
Documentation=http://docs.docker.com
After=network.target

[Service]
Type=notify
EnvironmentFile=-/etc/sysconfig/docker
EnvironmentFile=-/etc/sysconfig/docker-storage
EnvironmentFile=-/etc/sysconfig/docker-network
Environment=GOTRACEBACK=crash
ExecStart=/usr/bin/docker daemon $OPTIONS \\
          $DOCKER_STORAGE_OPTIONS \\
          $DOCKER_NETWORK_OPTIONS \\
          $ADD_REGISTRY \\
          $BLOCK_REGISTRY \\
          $INSECURE_REGISTRY
LimitNOFILE=1048576
LimitNPROC=1048576
LimitCORE=infinity
MountFlags=slave
TimeoutStartSec=1min
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target'''
DOCKER_SERVICE_DIR = '/etc/systemd/system/docker.service.d'
FLANNEL_CONF_FILE = '/etc/systemd/system/docker.service.d/flannel.conf'
FLANNEL_CONF = '''[Service]
EnvironmentFile=/run/flannel/docker'''

# 00116
# see also kubedock/system_settings/fixtures.py
CPU_MULTIPLIER = '8'
MEMORY_MULTIPLIER = '4'


# 00117
# old rbac fixtures
RESOURCES = ("users", "nodes", "pods", "yaml_pods", "ippool",
             "notifications", "system_settings", "images", "predefined_apps")

ROLES = (
    ("Admin", False),
    ("User", False),
    ("LimitedUser", False),
    ("TrialUser", False),
    ("HostingPanel", True),
)

PERMISSIONS = (
    # Admin
    ("users", "Admin", "create", True),
    ("users", "Admin", "get", True),
    ("users", "Admin", "edit", True),
    ("users", "Admin", "delete", True),
    ("users", "Admin", "auth_by_another", True),
    ("nodes", "Admin", "create", True),
    ("nodes", "Admin", "get", True),
    ("nodes", "Admin", "edit", True),
    ("nodes", "Admin", "delete", True),
    ("nodes", "Admin", "redeploy", True),
    ("pods", "Admin", "create", False),
    ("pods", "Admin", "get", False),
    ("pods", "Admin", "edit", False),
    ("pods", "Admin", "delete", False),
    ("yaml_pods", "Admin", "create", False),
    ("ippool", "Admin", "create", True),
    ("ippool", "Admin", "get", True),
    ("ippool", "Admin", "edit", True),
    ("ippool", "Admin", "delete", True),
    ("ippool", "Admin", "view", True),
    ("notifications", "Admin", "create", True),
    ("notifications", "Admin", "get", True),
    ("notifications", "Admin", "edit", True),
    ("notifications", "Admin", "delete", True),
    ("system_settings", "Admin", "read", True),
    ("system_settings", "Admin", "write", True),
    ("system_settings", "Admin", "delete", True),
    ("images", "Admin", "get", True),
    ("images", "Admin", "isalive", True),
    ("predefined_apps", "Admin", "create", True),
    ("predefined_apps", "Admin", "get", True),
    ("predefined_apps", "Admin", "edit", True),
    ("predefined_apps", "Admin", "delete", True),
    # User
    ("users", "User", "create", False),
    ("users", "User", "get", False),
    ("users", "User", "edit", False),
    ("users", "User", "delete", False),
    ("users", "User", "auth_by_another", False),
    ("nodes", "User", "create", False),
    ("nodes", "User", "get", False),
    ("nodes", "User", "edit", False),
    ("nodes", "User", "delete", False),
    ("nodes", "User", "redeploy", False),
    ("pods", "User", "create", True),
    ("pods", "User", "get", True),
    ("pods", "User", "edit", True),
    ("pods", "User", "delete", True),
    ("yaml_pods", "User", "create", True),
    ("ippool", "User", "create", False),
    ("ippool", "User", "get", False),
    ("ippool", "User", "edit", False),
    ("ippool", "User", "delete", False),
    ("ippool", "User", "view", False),
    ("notifications", "User", "create", False),
    ("notifications", "User", "get", False),
    ("notifications", "User", "edit", False),
    ("notifications", "User", "delete", False),
    ("images", "User", "get", True),
    ("images", "User", "isalive", True),
    ("predefined_apps", "User", "create", False),
    ("predefined_apps", "User", "get", True),
    ("predefined_apps", "User", "edit", False),
    ("predefined_apps", "User", "delete", False),
    # LimitedUser
    ("users", "LimitedUser", "create", False),
    ("users", "LimitedUser", "get", False),
    ("users", "LimitedUser", "edit", False),
    ("users", "LimitedUser", "delete", False),
    ("users", "LimitedUser", "auth_by_another", False),
    ("nodes", "LimitedUser", "create", False),
    ("nodes", "LimitedUser", "get", False),
    ("nodes", "LimitedUser", "edit", False),
    ("nodes", "LimitedUser", "delete", False),
    ("nodes", "LimitedUser", "redeploy", False),
    ("pods", "LimitedUser", "create", False),
    ("pods", "LimitedUser", "get", True),
    ("pods", "LimitedUser", "edit", True),
    ("pods", "LimitedUser", "delete", True),
    ("yaml_pods", "LimitedUser", "create", True),
    ("ippool", "LimitedUser", "create", False),
    ("ippool", "LimitedUser", "get", False),
    ("ippool", "LimitedUser", "edit", False),
    ("ippool", "LimitedUser", "delete", False),
    ("ippool", "LimitedUser", "view", False),
    ("notifications", "LimitedUser", "create", False),
    ("notifications", "LimitedUser", "get", False),
    ("notifications", "LimitedUser", "edit", False),
    ("notifications", "LimitedUser", "delete", False),
    ("images", "LimitedUser", "get", True),
    ("images", "LimitedUser", "isalive", True),
    ("predefined_apps", "LimitedUser", "create", False),
    ("predefined_apps", "LimitedUser", "get", True),
    ("predefined_apps", "LimitedUser", "edit", False),
    ("predefined_apps", "LimitedUser", "delete", False),
    # TrialUser
    ("users", "TrialUser", "create", False),
    ("users", "TrialUser", "get", False),
    ("users", "TrialUser", "edit", False),
    ("users", "TrialUser", "delete", False),
    ("users", "TrialUser", "auth_by_another", False),
    ("nodes", "TrialUser", "create", False),
    ("nodes", "TrialUser", "get", False),
    ("nodes", "TrialUser", "edit", False),
    ("nodes", "TrialUser", "delete", False),
    ("nodes", "TrialUser", "redeploy", False),
    ("pods", "TrialUser", "create", True),
    ("pods", "TrialUser", "get", True),
    ("pods", "TrialUser", "edit", True),
    ("pods", "TrialUser", "delete", True),
    ("yaml_pods", "TrialUser", "create", True),
    ("ippool", "TrialUser", "create", False),
    ("ippool", "TrialUser", "get", False),
    ("ippool", "TrialUser", "edit", False),
    ("ippool", "TrialUser", "delete", False),
    ("ippool", "TrialUser", "view", False),
    ("notifications", "TrialUser", "create", False),
    ("notifications", "TrialUser", "get", False),
    ("notifications", "TrialUser", "edit", False),
    ("notifications", "TrialUser", "delete", False),
    ("images", "TrialUser", "get", True),
    ("images", "TrialUser", "isalive", True),
    ("predefined_apps", "TrialUser", "create", False),
    ("predefined_apps", "TrialUser", "get", True),
    ("predefined_apps", "TrialUser", "edit", False),
    ("predefined_apps", "TrialUser", "delete", False),
    # HostingPanel
    ("users", "HostingPanel", "create", False),
    ("users", "HostingPanel", "get", False),
    ("users", "HostingPanel", "edit", False),
    ("users", "HostingPanel", "delete", False),
    ("users", "HostingPanel", "auth_by_another", False),
    ("nodes", "HostingPanel", "create", False),
    ("nodes", "HostingPanel", "get", False),
    ("nodes", "HostingPanel", "edit", False),
    ("nodes", "HostingPanel", "delete", False),
    ("nodes", "HostingPanel", "redeploy", False),
    ("pods", "HostingPanel", "create", False),
    ("pods", "HostingPanel", "get", False),
    ("pods", "HostingPanel", "edit", False),
    ("pods", "HostingPanel", "delete", False),
    ("yaml_pods", "HostingPanel", "create", False),
    ("ippool", "HostingPanel", "create", False),
    ("ippool", "HostingPanel", "get", False),
    ("ippool", "HostingPanel", "edit", False),
    ("ippool", "HostingPanel", "delete", False),
    ("ippool", "HostingPanel", "view", False),
    ("notifications", "HostingPanel", "create", False),
    ("notifications", "HostingPanel", "get", False),
    ("notifications", "HostingPanel", "edit", False),
    ("notifications", "HostingPanel", "delete", False),
    ("images", "HostingPanel", "get", True),
    ("images", "HostingPanel", "isalive", True),
    ("predefined_apps", "HostingPanel", "create", False),
    ("predefined_apps", "HostingPanel", "get", True),
    ("predefined_apps", "HostingPanel", "edit", False),
    ("predefined_apps", "HostingPanel", "delete", False),
)

# 00120
PLUGIN_DIR = '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/'

# 00123
PLUGIN_PY = PLUGIN_DIR + 'kuberdock.py'
WATCHER_SERVICE = """[Unit]
Description=KuberDock Network Plugin watcher
After=flanneld.service
Requires=flanneld.service

[Service]
ExecStart=/usr/bin/env python2 {0} watch
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target""".format(PLUGIN_PY)


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading DB...')
    helpers.upgrade_db()

    # 00116
    upd.print_log('Add system settings for CPU and Memory multipliers')
    db.session.add_all([
        SystemSettings(
            name='cpu_multiplier', value=CPU_MULTIPLIER,
            label='CPU multiplier',
            description='Cluster CPU multiplier',
            placeholder='Enter value for CPU multiplier'),
        SystemSettings(
            name='memory_multiplier', value=MEMORY_MULTIPLIER,
            label='Memory multiplier',
            description='Cluster Memory multiplier',
            placeholder='Enter value for Memory multiplier'),
    ])

    upd.print_log('Create table for NodeAction model if not exists')
    NodeAction.__table__.create(bind=db.engine, checkfirst=True)
    db.session.commit()

    # 00117
    upd.print_log('Update permissions...')
    Permission.query.delete()
    Resource.query.delete()
    add_permissions()
    db.session.commit()

    # Fix wrong pd_states if exists.
    wrong_states = db.session.query(PersistentDiskState).join(
        PersistentDisk,
        db.and_(
            PersistentDisk.name == PersistentDiskState.pd_name,
            PersistentDisk.owner_id == PersistentDiskState.user_id,
            PersistentDisk.state == PersistentDiskStatuses.DELETED
        )
    ).filter(
        PersistentDiskState.end_time == None
    )
    for state in wrong_states:
        state.end_time = datetime.datetime.utcnow()
    db.session.commit()

    helpers.close_all_sessions()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    # 00119
    upd.print_log('Allow null in User.package_id field...')
    helpers.downgrade_db(revision='2c64986d76b9')

    # 00118
    upd.print_log('Reverting package count_type column...')
    helpers.downgrade_db(revision='42b36be03945')

    # 00117
    upd.print_log('Downgrade permissions...')
    Permission.query.delete()
    Resource.query.delete()
    add_permissions()
    db.session.commit()

    # 00116
    upd.print_log('Remove system settings for CPU and Memory multipliers')
    for name in ('cpu_multiplier', 'memory_multiplier'):
        entry = SystemSettings.query.filter_by(name=name).first()
        if entry is not None:
            db.session.delete(entry)

    upd.print_log('Drop table "node_actions" if exists')
    table = Table('node_actions', db.metadata)
    table.drop(bind=db.engine, checkfirst=True)
    db.session.commit()


    helpers.close_all_sessions()


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    # 00115
    upd.print_log('Updating flannel and docker services...')
    upd.print_log(
        run("echo '{0}' > '{1}'".format(DOCKER_SERVICE, DOCKER_SERVICE_FILE))
    )
    upd.print_log(run('mkdir -p {0}'.format(DOCKER_SERVICE_DIR)))
    upd.print_log(
        run("echo '{0}' > '{1}'".format(FLANNEL_CONF, FLANNEL_CONF_FILE))
    )
    upd.print_log(run('systemctl daemon-reload'))
    upd.print_log(run('systemctl reenable docker'))
    upd.print_log(run('systemctl reenable flanneld'))

    # 00116
    upd.print_log('Copy kubelet_args.py...')
    put('/var/opt/kuberdock/kubelet_args.py',
        '/var/lib/kuberdock/scripts/kubelet_args.py',
        mode=0755)

    # 00120
    put('/var/opt/kuberdock/node_network_plugin.sh', PLUGIN_DIR + 'kuberdock')

    # 00121
    run('yum install -y tuned')
    run('systemctl enable tuned')
    run('systemctl start tuned')
    result = run('systemd-detect-virt --vm --quiet')
    if result.return_code:
        run('tuned-adm profile latency-performance')
    else:
        run('tuned-adm profile virtual-guest')

    # 00123
    put('/var/opt/kuberdock/node_network_plugin.py', PLUGIN_PY, mode=0755)
    run('echo "{0}" > "{1}"'.format(
        WATCHER_SERVICE, '/etc/systemd/system/kuberdock-watcher.service'
    ))
    run('systemctl daemon-reload')
    run('systemctl restart kuberdock-watcher')

    # 00115 pt2, check and reboot
    check = run(
        'source /run/flannel/docker'
        ' && '
        'grep "$DOCKER_NETWORK_OPTIONS" <<< "$(ps ax)"'
        ' > /dev/null'
    )

    if check.failed:
        upd.print_log('Node need to be rebooted')
        helpers.reboot_node(upd)

def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    # 00115
    upd.print_log('Removing custom flannel and docker services...')
    upd.print_log(run("rm -rf '{0}'".format(DOCKER_SERVICE_DIR)))
    upd.print_log(run("rm -rf '{0}'".format(DOCKER_SERVICE_FILE)))
    upd.print_log(run('systemctl daemon-reload'))
    upd.print_log(run('systemctl reenable docker'))
    upd.print_log(run('systemctl reenable flanneld'))

    # 00116
    upd.print_log('Remove kubelet_args.py...')
    run('rm -f /var/lib/kuberdock/scripts/kubelet_args.py')
