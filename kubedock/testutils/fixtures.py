from string import ascii_letters, digits
from random import choice
from uuid import uuid4
import json

from kubedock.core import db
from kubedock.models import User, Pod
from kubedock.billing.models import Kube
from kubedock.billing.fixtures import add_kubes_and_packages
from kubedock.users.fixtures import add_users_and_roles
from kubedock.notifications.fixtures import add_notifications
from kubedock.rbac.fixtures import add_permissions
from kubedock.rbac.models import Role
from kubedock.system_settings.fixtures import add_system_settings
from kubedock.static_pages.fixtures import generate_menu


def initial_fixtures():
    """Almost the same stuff as manage.py createdb"""

    add_kubes_and_packages()

    add_system_settings()

    add_notifications()

    add_permissions()

    add_users_and_roles(randstr())

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
    if 'config' in kwargs and not isinstance(kwargs['config'], basestring):
        kwargs['config'] = json.dumps(kwargs['config'])
    namespace = str(uuid4())
    kwargs.setdefault('id', namespace)
    kwargs.setdefault('name', 'pod-' + randstr())
    kwargs.setdefault('config', json.dumps({
        'node': None,
        'replicas': 1,
        'secrets': [],
        'namespace': namespace,
        'restartPolicy': 'Never',
        'volumes': [],
        'sid': str(uuid4()),
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
