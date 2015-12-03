from string import ascii_letters, digits
from random import choice
from uuid import uuid4
import json

from kubedock.core import db
from kubedock.models import User, Pod
from kubedock.billing.models import Package, Kube, PackageKube
from kubedock.rbac.fixtures import add_permissions
from kubedock.rbac.models import Role
from kubedock.static_pages.fixtures import generate_menu
from kubedock.settings import KUBERDOCK_INTERNAL_USER


def initial_fixtures():
    """Almost the same stuff as manage.py createdb"""
    # Create default packages and kubes
    # Package and Kube with id=0 are default
    # and must be undeletable (always present with id=0) for fallback
    k_internal = Kube(id=Kube.get_internal_service_kube_type(),
                      name='Internal service', cpu=.01, cpu_units='Cores',
                      memory=64, memory_units='MB', disk_space=1,
                      disk_space_units='GB', included_traffic=0)
    k1 = Kube(id=Kube.get_default_kube_type(),
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

    db.session.add(k_internal)
    PackageKube(package=p1, kube=k1, kube_price=0)
    PackageKube(package=p1, kube=k2, kube_price=0)
    PackageKube(package=p1, kube=k3, kube_price=0)

    db.session.commit()

    add_permissions()

    # Special user for convenience to type and login
    r = Role.filter_by(rolename='Admin').first()
    u = User.filter_by(username='admin').first()
    if u is None:
        u = User.create(username='admin', password=randstr(), role=r, package=p1,
                        active=True)
        db.session.add(u)
    kr = Role.filter_by(rolename='User').first()
    ku = User.filter_by(username=KUBERDOCK_INTERNAL_USER).first()
    ku_passwd = uuid4().hex
    if ku is None:
        ku = User.create(username=KUBERDOCK_INTERNAL_USER,
                         password=ku_passwd, role=kr,
                         package=p1, first_name='KuberDock Internal',
                         active=True)
        # generate token immediately, to use it in node creation
        ku.get_token()
        db.session.add(ku)
    db.session.commit()

    # Special user for cPanel
    r = Role.filter_by(rolename='HostingPanel').first()
    u = User.filter_by(username='hostingPanel').first()
    if not u:
        u = User.create(username='hostingPanel', password='hostingPanel',
                        role=r, active=True)
        db.session.add(u)
        db.session.commit()

    generate_menu()

    # Fix packages id next val
    db.engine.execute("SELECT setval('packages_id_seq', 1, false)")


def user_fixtures(admin=False, active=True, **kwargs):
    username = 'user_' + randstr(8)
    password = randstr(10)
    role_id = Role.filter_by(
            rolename='User' if not admin else 'Admin').first().id
    email = randstr(10) + '@test.test'

    data = dict(username=username, password=password, active=active,
                role_id=role_id, package_id=0, email=email)
    user = User(**dict(data, **kwargs)).save()
    return user, password


def admin_fixtures(**kwargs):
    return user_fixtures(admin=True, **kwargs)


def pod(**kwargs):
    if 'owner_id' not in kwargs and 'owner' not in kwargs:
        kwargs['owner'], _ = user_fixtures()
    if 'kube_id' not in kwargs and 'kube' not in kwargs:
        kwargs['kube'] = Kube.get_default_kube()
    namespace = str(uuid4())
    kwargs.setdefault('id', namespace)
    kwargs.setdefault('name', 'pod-' + randstr())
    kwargs.setdefault('config', json.dumps({
        'node': None,
        'name': 'pod-' + randstr(),
        'replicas': 1,
        'secrets': [],
        'namespace': namespace,
        'restartPolicy': 'Never',
        'volumes': [],
        'sid': str(uuid4()),
        'kube_type': 0,
        'containers': [{
            'kubes': 1,
            'terminationMessagePath': None,
            'name': 'curl' + randstr(),
            'workingDir': '',
            'image': 'appropriate/curl',
            'args': ['curl', 'httpbin.org/get'],
            'volumeMounts': [],
            'sourceUrl': 'hub.docker.com/r/appropriate/curl',
            'env': [{'name': 'PATH',
                     'value': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'}],
            'ports': []}]}))
    return Pod(**kwargs).save()


def randstr(length=8, symbols=ascii_letters + digits):
    return ''.join(choice(symbols) for i in range(length))
