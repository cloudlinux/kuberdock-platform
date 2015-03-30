from kubedock.frontend import create_app
from kubedock.core import db
from kubedock.models import User
from kubedock.billing.models import Package, Kube
from kubedock.rbac import gen_roles
from kubedock.rbac.fixtures import add_permissions
from kubedock.rbac.models import Role

from kubedock.static_pages.fixtures import generate_menu

if __name__ == '__main__':
    app = create_app()
    ac = app.app_context()
    ac.push()
    db.drop_all()
    db.create_all()
    
    # Create default packages and kubes
    # Package and Kube with id=0 are default
    # end must be undeletable (always present with id=0) for fallback
    k1 = Kube(id=0, name='standard', cpu=700, cpu_units='KCU',
              memory=64, memory_units='MB', disk_space='0', total_traffic=0)
    k2 = Kube(name='hi memory', cpu=700, cpu_units='KCU',
              memory=256, memory_units='MB', disk_space='0', total_traffic=0)
    k3 = Kube(name='hi cpu', cpu=1400, cpu_units='KCU',
              memory=64, memory_units='MB', disk_space='0', total_traffic=0)
    db.session.add_all([k1, k2, k3])
    db.session.commit()

    p = Package(id=0, name='basic', kube=k1, amount=0,
                currency='USD', period='hour')

    add_permissions()

    # Create all roles with users that has same name and password as role_name.
    # Useful to test permissions.
    for role in Role.all():
        u = User.filter_by(username=role.rolename).first()
        if u is None:
            u = User.create(username=role.rolename, password=role.rolename,
                            role=role, package=p, active=True)
            db.session.add(u)
    db.session.commit()

    # Special user for convenience to type and login
    r = Role.filter_by(rolename='SuperAdmin').first()
    u = User.filter_by(username='admin').first()
    if u is None:
        u = User.create(username='admin', password='admin', role=r, package=p,
                        active=True)
        db.session.add(u)
    db.session.commit()

    generate_menu()

    ac.pop()