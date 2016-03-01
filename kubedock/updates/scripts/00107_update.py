from fabric.api import local, put, run

from kubedock.core import db
from kubedock.kapi.podcollection import PodCollection
from kubedock.pods.models import Pod
from kubedock.rbac import fixtures
from kubedock.rbac.models import Role
from kubedock.static_pages.models import MenuItemRole
from kubedock.updates import helpers


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


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    run('yum --enablerepo=kube,kube-testing clean metadata')

    # 00101_update.py
    upd.print_log('Update fslimit.py script...')
    upd.print_log(put('/var/opt/kuberdock/fslimit.py',
                      '/var/lib/kuberdock/scripts/fslimit.py',
                      mode=0755))

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
