import json
from kubedock.static_pages.models import MenuItem, MenuItemRole
from kubedock.rbac.models import Role


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add menus Persistent volumes and Public IPs')
    user = Role.filter(Role.rolename == "User").one()
    trial_user = Role.filter(Role.rolename == "TrialUser").one()
    public_ips = MenuItem.create(name="Public IPs", path="/publicIPs/",
                                 ordering=1, menu_id=1)
    public_ips.save()
    perm = MenuItemRole(role=user, menuitem=public_ips)
    perm = MenuItemRole(role=trial_user, menuitem=public_ips)
    perm.save()
    p = MenuItem.create(name="Persistent volumes", path="/persistent-volumes/",
                        ordering=2, menu_id=1)
    p.save()
    perm = MenuItemRole(role=user, menuitem=p)
    perm = MenuItemRole(role=trial_user, menuitem=p)
    perm.save()


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Delete menus Persistent volumes and Public IPs')
    ps = MenuItem.filter(MenuItem.name == 'Persistent volumes').first()
    if ps:
        MenuItemRole.filter(MenuItemRole.menuitem == ps).delete()
        ps.delete()
    pip = MenuItem.filter(MenuItem.name == 'Public IPs').first()
    if pip:
        MenuItemRole.filter(MenuItemRole.menuitem == pip).delete()
        pip.delete()
