import os
import shutil

from kubedock.api import create_app
from kubedock.core import db
from kubedock.models import User, Pod
from kubedock.billing.models import Package, Kube
from kubedock.rbac.fixtures import add_permissions
from kubedock.rbac.models import Role
from kubedock.static_pages.fixtures import generate_menu
from kubedock.settings import KUBERDOCK_INTERNAL_USER

from flask.ext.script import Manager, Shell, Command, Option
from flask.ext.migrate import Migrate, MigrateCommand, init, upgrade
from flask.ext.migrate import migrate as migrate_func

directory = 'kdmigrations'

class Creator(Command):
    option_list = (Option('password'),)
    
    def run(self, password):
        db.drop_all()
        db.create_all()
        
        # Create default packages and kubes
        # Package and Kube with id=0 are default
        # end must be undeletable (always present with id=0) for fallback
        k1 = Kube(id=0, name='Standard kube', cpu=.01, cpu_units='Cores',
                  memory=64, memory_units='MB', disk_space='0', total_traffic=0, price=0)
        k2 = Kube(name='High CPU', cpu=.02, cpu_units='Cores',
                  memory=64, memory_units='MB', disk_space='0', total_traffic=0, price=1)
        k3 = Kube(name='High memory', cpu=.01, cpu_units='Cores',
                  memory=256, memory_units='MB', disk_space='0', total_traffic=0, price=2)
        
        p1 = Package(id=0, name='basic', setup_fee=0, currency='USD', period='hour')
        p2 = Package(id=1, name='professional', setup_fee=1, currency='USD', period='hour')
        p3 = Package(id=2, name='enterprise', setup_fee=2, currency='USD', period='hour')
        
        p1.kubes.append(k1)
        p2.kubes.append(k1)
        p2.kubes.append(k2)
        p3.kubes.append(k1)
        p3.kubes.append(k2)
        p3.kubes.append(k3)
        
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
            u = User.create(username='admin', password=password, role=r, package=p1,
                            active=True)
            db.session.add(u)
        kr = Role.filter_by(rolename='User').first()
        ku = User.filter_by(username=KUBERDOCK_INTERNAL_USER).first()
        if ku is None:
            ku = User.create(username=KUBERDOCK_INTERNAL_USER, password='', role=kr,
                             package=p1, first_name='KuberDock Internal',
                             active=True)
            db.session.add(ku)
        db.session.commit()
        
        generate_menu()
        
        if os.path.isdir(directory):
            shutil.rmtree(directory)
        init(directory=directory)

class Updater(Command):
    def run(self):
        migrate_func(directory=directory)
        upgrade(directory=directory)

app = create_app()
manager = Manager(app, with_default_commands=False)
migrate = Migrate(app, db)

def make_shell_context():
    return dict(app=app, db=db, User=User, Pod=Pod, Package=Package, Kube=Kube)

manager.add_command('shell', Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)
manager.add_command('createdb', Creator())
manager.add_command('updatedb', Updater())


if __name__ == '__main__':
    manager.run()
