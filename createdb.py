from kubedock.api import create_app
from kubedock.core import db
from kubedock.models import User
from kubedock.billing.models import Package, Kube, ExtraTax
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
    k1 = Kube(id=0, name='Standart kube', cpu=700, cpu_units='KCU',
              memory=64, memory_units='MB', disk_space='0', total_traffic=0)
    k2 = Kube(name='High CPU', cpu=1400, cpu_units='KCU',
              memory=64, memory_units='MB', disk_space='0', total_traffic=0)
    k3 = Kube(name='Hight memory', cpu=700, cpu_units='KCU',
              memory=254, memory_units='MB', disk_space='0', total_traffic=0)
    db.session.add_all([k1, k2, k3])
    db.session.commit()

    p1 = Package(id=0, name='basic', kube=k1, amount=1,
                 currency='USD', period='hour')
    p2 = Package(id=1, name='professional', kube=k2, amount=2,
                 currency='USD', period='hour')
    p3 = Package(id=2, name='enterprise', kube=k3, amount=3,
                 currency='USD', period='hour')
    e1 = ExtraTax(id=0, key='public_ip', name='public ip', amount=6,
                  currency='USD', period='hour')
    db.session.add_all([p1, p2, p3, e1])
    db.session.commit()

    add_permissions()

    # Create all roles with users that has same name and password as role_name.
    # Useful to test permissions.
    # Delete all users from setup KuberDock. Only admin must be after install.
    # AC-228
    # for role in Role.all():
    #     u = User.filter_by(username=role.rolename).first()
    #     if u is None:
    #         u = User.create(username=role.rolename, password=role.rolename,
    #                         role=role, package=p, active=True)
    #         db.session.add(u)
    # db.session.commit()

    # Special user for convenience to type and login
    r = Role.filter_by(rolename='Admin').first()
    u = User.filter_by(username='admin').first()
    if u is None:
        u = User.create(username='admin', password='admin', role=r, package=p1,
                        active=True)
        db.session.add(u)
    db.session.commit()

    generate_menu()

    ac.pop()
