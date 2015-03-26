from kubedock.frontend import create_app
from kubedock.core import db
from kubedock.models import Role, User
from kubedock.billing.models import Package, Kube
from kubedock.rbac import gen_roles

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
    
    # Create all roles with users that has same name and password as role_name.
    # Useful to test permissions.
    for rolename in gen_roles():
        role = Role.query.filter_by(rolename=rolename).first()
        if role is None:
            role = Role(rolename=rolename)
            db.session.add(role)
        u = User.query.filter_by(username=rolename).first()
        if u is None:
            u = User(username=rolename, password=rolename, role=role, package=p,
                     active=True)
            db.session.add(u)
    db.session.commit()
    

    # Special user for convenience to type and login
    r = db.session.query(Role).filter_by(rolename='SuperAdmin').first()
    u = User.query.filter_by(username='admin').first()
    if u is None:
        u = User(username='admin', password='admin', role=r, package=p,
                 active=True)
        db.session.add(u)
    db.session.commit()
    
    generate_menu()

    ac.pop()