
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

from fabric.api import local, put, run

from kubedock.core import db
from kubedock.kapi.podcollection import PodCollection
from kubedock.pods.models import Pod
from kubedock.rbac import fixtures
from kubedock.rbac.models import Role
from kubedock.static_pages.models import MenuItemRole
from kubedock.updates import helpers
from kubedock.utils import POD_STATUSES


# 00102_update.py
PLUGIN_DIR = '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/'

# 00103_update.py
OVERRIDE_CONF = """\
[Service]
Restart=always
RestartSec=1s
"""
SERVICE_DIR = "/etc/systemd/system/ntpd.service.d"
OVERRIDE_FILE = SERVICE_DIR + "/restart.conf"

# 00105_update.py
PERMISSIONS = (
    # Admin
    ("yaml_pods", "Admin", "create", False),
    # User
    ("yaml_pods", "User", "create", True),
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
    ("yaml_pods", "TrialUser", "create", True),
    # HostingPanel
    ("yaml_pods", "HostingPanel", "create", False),
)
RESOURCES = ("yaml_pods",)
ROLES = (
    ("LimitedUser", False),
)

# Update uwsgi configuration.
UWSGI_KUBERDOCK_INI_SOURCE = '/var/opt/kuberdock/conf/kuberdock.ini'
UWSGI_KUBERDOCK_INI_DEST = '/etc/uwsgi/vassals/kuberdock.ini'
SAVE_KUBERDOCK_INI = '/tmp/kuberdock.ini.save.107'


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading db...')
    helpers.upgrade_db()

    # 00103_update.py
    upd.print_log('Enabling restart for ntpd.service on master')
    local('mkdir -p ' + SERVICE_DIR)
    local('echo -e "' + OVERRIDE_CONF + '" > ' + OVERRIDE_FILE)
    local('systemctl daemon-reload')
    local('systemctl restart ntpd')

    # 00104_update.py
    upd.print_log('Restart pods with persistent storage')
    pc = PodCollection()
    pods = Pod.query.with_entities(Pod.id).filter(Pod.persistent_disks).all()
    for pod_id in pods:
        p = pc._get_by_id(pod_id[0])
        if p.status == POD_STATUSES.running:
            pc._stop_pod(p)
            pc._collection.pop((pod_id[0], pod_id[0]))
            pc._merge()
            p = pc._get_by_id(pod_id[0])
            pc._start_pod(p)

    # 00105_update.py
    upd.print_log('Add roles {}, resources {} and its permissions...'.format(
        ROLES, RESOURCES))
    fixtures.add_permissions(
        roles=ROLES, resources=RESOURCES, permissions=PERMISSIONS)
    upd.print_log('Add MenuRoles...')
    PAUserRole = Role.query.filter(Role.rolename == 'LimitedUser').first()
    for menu_role in Role.query.filter(Role.rolename == 'User').first().menus_assocs:
        db.session.add(MenuItemRole(role=PAUserRole, menuitem_id=menu_role.menuitem_id))
    db.session.commit()

    # Fixes for celery workers launching
    upd.print_log('Updating uwsgi configuration ...')
    local('test -f "{0}" && cp "{0}" "{1}"'.format(
        UWSGI_KUBERDOCK_INI_DEST, SAVE_KUBERDOCK_INI
    ))
    local('cp "{0}" "{1}"'.format(
        UWSGI_KUBERDOCK_INI_SOURCE, UWSGI_KUBERDOCK_INI_DEST
    ))
    local('chmod 644 "{0}"'.format(UWSGI_KUBERDOCK_INI_DEST))


def downgrade(upd, with_testing, exception, *args, **kwargs):
    # 00103_update.py
    upd.print_log('Disabling restart for ntpd.service on master')
    local('rm -f ' + OVERRIDE_FILE)
    local('systemctl daemon-reload')

    # 00105_update.py
    upd.print_log('Remove MenuRoles...')
    PAUserRole = Role.query.filter(Role.rolename == 'LimitedUser').first()
    if PAUserRole is not None:
        for menu_role in PAUserRole.menus_assocs:
            db.session.delete(menu_role)

    upd.print_log('Delete roles {} with its permissions...'.format(ROLES))
    fixtures.delete_roles([name for name, internal in ROLES])
    upd.print_log(
        'Delete resources {} with its permissions...'.format(RESOURCES))
    fixtures.delete_resources(RESOURCES)
    db.session.commit()

    upd.print_log('Downgrading db...')
    helpers.downgrade_db(revision='2df8c40ab250')  # first of rc5

    upd.print_log('Restoring uwsgi configuration ...')
    local('test -f "{0}" && mv "{0}" "{1}"'.format(
        SAVE_KUBERDOCK_INI, UWSGI_KUBERDOCK_INI_DEST
    ))


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    run('yum --enablerepo=kube,kube-testing clean metadata')

    # 00101_update.py
    upd.print_log('Update fslimit.py script...')
    upd.print_log(put('/var/opt/kuberdock/fslimit.py',
                      '/var/lib/kuberdock/scripts/fslimit.py',
                      mode=0755))

    # 00102_update.py
    put('/var/opt/kuberdock/node_network_plugin.sh', PLUGIN_DIR + 'kuberdock')
    put('/var/opt/kuberdock/node_network_plugin.py', PLUGIN_DIR + 'kuberdock.py')
    run('systemctl restart kuberdock-watcher')

    # 00103_update.py
    upd.print_log('Enabling restart for ntpd.service')
    run('mkdir -p ' + SERVICE_DIR)
    run('echo -e "' + OVERRIDE_CONF + '" > ' + OVERRIDE_FILE)
    run('systemctl daemon-reload')
    run('systemctl restart ntpd')


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    # 00103_update.py
    upd.print_log('Disabling restart for ntpd.service')
    run('rm -f ' + OVERRIDE_FILE)
    run('systemctl daemon-reload')
