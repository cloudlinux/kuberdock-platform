from kubedock.frontend import create_app
from kubedock.core import db
from kubedock.models import Role, User

if __name__ == '__main__':
    app = create_app()
    ac = app.app_context()
    ac.push()
    #db.drop_all()
    db.create_all()

    Role.insert_roles()
    r = db.session.query(Role).filter_by(rolename='Administrator').first()
    u = User(username='admin', password='admin', role=r)
    db.session.add(u)
    db.session.commit()
    for i in range(10):
        r = db.session.query(Role).filter_by(rolename='Administrator').first()
        u = User(username='admin'+str(i), password='admin'+str(i), role=r)
        db.session.add(u)
        db.session.commit()

    ac.pop()