from random import randint
from uuid import uuid4
import json
import socket
import struct
import responses

from kubedock.billing.fixtures import add_kubes_and_packages
from kubedock.core import db
from kubedock.pods.models import PersistentDisk
from kubedock.utils import randstr, NODE_STATUSES
from kubedock.kapi.node import Node as K8SNode
from kubedock.models import User, Pod
from kubedock.billing.models import Kube
from kubedock.nodes.models import Node
from kubedock.notifications.fixtures import add_notifications
from kubedock.predefined_apps.models import PredefinedApp
from kubedock.rbac.fixtures import add_all_permissions
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

    add_all_permissions()

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
            'env': [{
                'name': 'PATH',
                'value': '/usr/local/sbin:/usr/local/bin:'
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

    return Node(
        ip=ip, hostname=hostname, kube_id=kube_id.id,
        state=NODE_STATUSES.pending)


def kube_type(**kwargs):
    return Kube(**dict(
        kwargs, name=randstr(), cpu=.25, memory=64, disk_space=1)).save()


def random_ip():
    return unicode(socket.inet_ntoa(struct.pack('>I', randint(1, 0xffffffff))))


def persistent_disk(**kwargs):
    if 'owner_id' not in kwargs and 'owner' not in kwargs:
        kwargs['owner'], _ = user_fixtures()
    return PersistentDisk(**kwargs).save()


def predefined_app(**kwargs):
    db_app = PredefinedApp(name=kwargs.get('name', randstr()))
    db.session.add(db_app)
    for key, value in kwargs.items():
        setattr(db_app, key, value)
    db.session.commit()
    return db_app


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


VALID_TEMPLATE1 = """---
apiVersion: v1
kind: ReplicationController
kuberdock:
  icon: http://icons.iconarchive.com/wordpress-icon.png
  name: Wordpress app
  packageID: 0
  postDescription: Some \$test %PUBLIC_ADDRESS%
  preDescription: Some pre description
  template_id: 1
  appPackages:
    - name: S
      recommended: yes
      goodFor: up to 100 users
      publicIP: false
      pods:
        - name: $APP_NAME$
          kubeType: 0
          containers:
            - name: mysql
              kubes: 1
            - name: wordpress
              kubes: 2
          persistentDisks:
            - name: wordpress-persistent-storage
              pdSize: 1
            - name: mysql-persistent-storage$VAR_IN_NAME$
              pdSize: $MYSQL_PD_SIZE|default:2|MySQL persistent disk size$
    - name: M
      goodFor: up to 100K visitors
      publicIP: true
      pods:
        - name: $APP_NAME$
          kubeType: 0
          containers:
            - name: mysql
              kubes: 2
            - name: wordpress
              kubes: 4
          persistentDisks:
            - name: wordpress-persistent-storage
              pdSize: 2
            - name: mysql-persistent-storage$VAR_IN_NAME$
              pdSize: 3
metadata:
  name: $APP_NAME|default:WordPress|App name$
spec:
  template:
    metadata:
      labels:
        name: $APP_NAME$
    spec:
      volumes:
        - name: mysql-persistent-storage$VAR_IN_NAME|default:autogen|v$
          persistentDisk:
            pdName: wordpress_mysql_$PD_RAND|default:autogen|PD rand$
        - name: wordpress-persistent-storage
          persistentDisk:
            pdName: wordpress_www_$PD_RAND$
      containers:
        -
          env:
            -
              name: WORDPRESS_DB_NAME
              value: wordpress
            -
              name: WORDPRESS_DB_USER
              value: wordpress
            -
              name: WORDPRESS_DB_PASSWORD
              value: paSd43
            -
              name: WORDPRESS_DB_HOST
              value: 127.0.0.1
            -
              name: WP_ENV1
              value: $WPENV1|default:1|test var 1 1$
            -
              name: WP_ENV2
              value: $WPENV1$
            -
              name: WP_ENV3
              value: $WPENV1$
            -
              name: WP_ENV4
              value: $WPENV1|default:2|test var 1 2$
          image: wordpress:4.6
          name: wordpress
          ports:
            -
              containerPort: 80
              hostPort: 80
              isPublic: True
          volumeMounts:
            - mountPath: /var/www/html
              name: wordpress-persistent-storage

        -
          args: []

          env:
            -
              name: MYSQL_ROOT_PASSWORD
              value: wordpressdocker
            -
              name: MYSQL_DATABASE
              value: wordpress
            -
              name: MYSQL_USER
              value: wordpress
            -
              name: MYSQL_PASSWORD
              value: paSd43
            -
              name: TEST_AUTOGEN1
              value: $TESTAUTO1|default:autogen|test auto1$
          image: mysql:5.7
          name: mysql
          ports:
            -
              containerPort: 3306
          volumeMounts:
            - mountPath: /var/lib/mysql
              name: mysql-persistent-storage$VAR_IN_NAME$

      restartPolicy: Always
"""

# Self-Signed *.example.com certificate
sample_certificate = {
    'cert': open(
        'kubedock/testutils/certificates/wildcard.example.com.crt').read(),
    'key': open(
        'kubedock/testutils/certificates/wildcard.example.com.key').read(),
}
