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
    
    # Create default package and kube
    k = Kube(id=0, name='standard', default=True, cpu=0, cpu_units='MHz',
             memory=0, memory_units='MB', disk_space='0', total_traffic=0)
    p = Package(id=0, name='basic', default=True, kube=k, amount=0,
                currency='USD', period='hour')
    
    # Create all roles with users that has same name and password as role_name. Useful to test permissions.
    for rolename in gen_roles():
        role = Role.query.filter_by(rolename=rolename).first()
        if role is None:
            role = Role(rolename=rolename)
            db.session.add(role)
        u = User.query.filter_by(username=rolename).first()
        if u is None:
            u = User(username=rolename, password=rolename, role=role, package=p, active=True)
            db.session.add(u)
    db.session.commit()
    

    # Special user for convenience to type and login
    r = db.session.query(Role).filter_by(rolename='SuperAdmin').first()
    u = User.query.filter_by(username='admin').first()
    if u is None:
        u = User(username='admin', password='admin', role=r, package=p, active=True)
        db.session.add(u)
    db.session.commit()
    
    generate_menu()

    ac.pop()