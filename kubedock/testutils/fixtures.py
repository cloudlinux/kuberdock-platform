from kubedock.core import db

from kubedock.models import User
from kubedock.billing.models import (
    Package, Kube, PackageKube, DEFAULT_KUBE_TYPE)
from kubedock.rbac.fixtures import add_permissions
from kubedock.rbac.models import Role
from kubedock.static_pages.fixtures import generate_menu
from kubedock.settings import KUBERDOCK_INTERNAL_USER


def initial_fixtures():
    """Almost the same stuff as manage.py createdb"""

    # Create default packages and kubes
    # Package and Kube with id=0 are default
    # end must be undeletable (always present with id=0) for fallback
    k0 = Kube(id=Kube.get_internal_service_kube_type(),
              name='Internal service', cpu=.01, cpu_units='Cores',
              memory=64, memory_units='MB', disk_space=1,
              disk_space_units='GB', included_traffic=0)
    k1 = Kube(id=DEFAULT_KUBE_TYPE,
              name='Standard', cpu=.01, cpu_units='Cores',
              memory=64, memory_units='MB', disk_space=1,
              disk_space_units='GB', included_traffic=0,
              is_default=True)
    k2 = Kube(name='High CPU', cpu=.02, cpu_units='Cores',
              memory=64, memory_units='MB', disk_space=1,
              disk_space_units='GB', included_traffic=0)
    k3 = Kube(name='High memory', cpu=.01, cpu_units='Cores',
              memory=256, memory_units='MB', disk_space=1,
              disk_space_units='GB', included_traffic=0)

    p1 = Package(id=0, name='Standard package', first_deposit=0, currency='USD',
                 period='hour', prefix='$', suffix=' USD')

    db.session.add(k0)
    PackageKube(packages=p1, kubes=k1, kube_price=0)
    PackageKube(packages=p1, kubes=k2, kube_price=0)
    PackageKube(packages=p1, kubes=k3, kube_price=0)

    db.session.commit()

    add_permissions()

    # Special user for convenience to type and login
    r = Role.filter_by(rolename='Admin').first()
    u = User.filter_by(username='admin').first()
    if u is None:
        u = User.create(username='admin', password='admin', role=r, package=p1,
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

    # Fix packages id next val
    db.engine.execute("SELECT setval('packages_id_seq', 1, false)")


def user_fixtures(**kwargs):
    password = 'o3r2hdfe'
    data = dict(username='test_user', password=password, active=True,
                role_id=Role.filter_by(rolename='User').first().id,
                package_id=0, email='mfkdeogn49ekj@test.test')
    user = User(**dict(data, **kwargs)).save()
    return user, password


def admin_fixtures(**kwargs):
    password = 'mdld0oenbf'
    data = dict(username='test_admin', password=password, active=True,
                role_id=Role.filter_by(rolename='Admin').first().id,
                package_id=0, email='mdfldpnrfu3489e@test.test')
    user = User(**dict(data, **kwargs)).save()
    return user, password
