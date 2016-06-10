from string import ascii_letters, digits
from random import choice, randint
from uuid import uuid4
import json
import socket
import struct
import responses

from kubedock.billing.fixtures import add_kubes_and_packages
from kubedock.core import db
from kubedock.utils import randstr
from kubedock.kapi.node import Node as K8SNode
from kubedock.models import User, Pod
from kubedock.billing.models import Kube
from kubedock.nodes.models import Node
from kubedock.notifications.fixtures import add_notifications
from kubedock.rbac.fixtures import add_permissions
from kubedock.rbac.models import Role
from kubedock.system_settings.fixtures import add_system_settings
from kubedock.static_pages.fixtures import generate_menu
from kubedock.users.fixtures import add_users_and_roles
from kubedock.utils import get_api_url


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
            'env': [{'name': 'PATH', 'value': '/usr/local/sbin:/usr/local/bin:'
                                              '/usr/sbin:/usr/bin:/sbin:/bin'
            }],
            'ports': []}]}))
    return Pod(**kwargs).save()


def node(hostname=None, ip=None, kube_id=None, owner=None):
    if owner is None:
        owner, _ = user_fixtures()
    if kube_id is None:
        kube_id = Kube.get_default_kube()
    if ip is None:
        ip = random_ip()
    if hostname is None:
        hostname = randstr()

    return Node(ip=ip, hostname=hostname, kube_id=kube_id.id, state='pending')


def kube_type(**kwargs):
    return Kube(**dict(
        kwargs, name=randstr(), cpu=.25, memory=64, disk_space=1)).save()


def randstr(length=8, symbols=ascii_letters + digits):
    return ''.join(choice(symbols) for _ in range(length))


def random_ip():
    return unicode(socket.inet_ntoa(struct.pack('>I', randint(1, 0xffffffff))))


class K8SAPIStubs(object):
    def __init__(self):
        self.metadata = {}
        self.nodes = {}

    def node_info_update_in_k8s_api(self, hostname,
                                    always_raise_conflict=False,
                                    always_raise_failure=False):
        def request_callback(request):
            payload = json.loads(request.body)
            version = int(payload['metadata']['resourceVersion'])
            # Node spec is altered. Increase version
            payload['metadata']['resourceVersion'] = str(version + 1)
            payload['code'] = 200
            self.nodes[hostname] = payload
            return 200, {}, json.dumps(payload)

        url = get_api_url('nodes', hostname, namespace=None)
        if always_raise_conflict:
            resp_body_on_conflict = """{
                "apiVersion": "v1",
                "code": 409,
                "details": {},
                "kind": "status"
            }
            """
            responses.add(responses.PUT, url, status=409,
                          body=resp_body_on_conflict)
        elif always_raise_failure:
            responses.add(responses.PUT, url, status=500,
                          body="")
        else:
            responses.add_callback(responses.PUT, url,
                                   callback=request_callback)

    def node_info_patch_in_k8s_api(self, hostname):
        """
        Stubs K8S API call used to update node info using PATCH requests.
        For now it saves metadata part in cache per node, so it can be used
        by node_info stub if one is enabled
        on
        :param hostname: hostname of a node to enable this stub for
        """

        def request_callback(request):
            payload = json.loads(request.body)
            if 'metadata' in payload:
                # TODO: Actually patch metadata, not just replace it
                self.metadata[hostname] = payload['metadata']
            return 200, {}, json.dumps(payload)

        url = get_api_url('nodes', hostname, namespace=None)
        responses.add_callback(responses.PATCH, url,
                               callback=request_callback)

    def node_info_in_k8s_api(self, hostname):
        """
        Stubs K8S api call used to retrieve node data from K8S.
        Response is dynamic if node info update stubs were also enabled. It
        uses metadata altered by PATCH requests. Otherwise returns some
        predefined stub
        :param hostname: hostname of a node to enable this stub for
        """

        def request_callback(request):
            metadata = {
                "resourceVersion": 1,
                "annotations": {
                    K8SNode.FREE_PUBLIC_IP_COUNTER_FIELD: "0"
                }
            }

            if hostname in self.nodes:
                body = self.nodes[hostname]
            else:
                body = {
                    "apiVersion": "v1",
                    "kind": "Node",
                    "metadata": metadata,
                    "labels": {
                        "kuberdock-kube-type": "type_0",
                        "kuberdock-node-hostname": hostname
                    },
                    "name": hostname,
                    "status": {},
                }
            return 200, {}, json.dumps(body)

        url = get_api_url('nodes', hostname, namespace=None)
        responses.add_callback(responses.GET, url, callback=request_callback)

    def build_api_url(self, *args, **kwargs):
        return get_api_url(*args, **kwargs)
