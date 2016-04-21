from kubedock.rbac.fixtures import (
    Role, Permission, Resource, add_permissions,
    add_roles, _add_permissions, permissions_base,
)
from kubedock.users.models import User, db
from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Removing HostingPanel role and user...')
    User.query.filter(User.username == 'hostingPanel').delete()
    Permission.query.delete()
    Resource.query.delete()
    Role.query.filter(Role.rolename == 'HostingPanel').delete()
    add_permissions()
    db.session.commit()
    helpers.close_all_sessions()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Creating HostingPanel role and user...')
    add_roles([('HostingPanel', True)])
    role = Role.filter_by(rolename='HostingPanel').first()
    user = User.filter_by(username='hostingPanel').first()
    if not user:
        db.session.add(User(username='hostingPanel', role=role,
                            password='hostingPanel', active=True))
    perms = dict(permissions_base, **{
        ('images', 'get'): True,
        ('images', 'isalive'): True,
        ('predefined_apps', 'get'): True,
    })
    _add_permissions([(resource, role.rolename, action, allow)
                      for (resource, action), allow in perms.iteritems()])
    db.session.commit()
    helpers.close_all_sessions()
