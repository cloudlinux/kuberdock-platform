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

# Self-Signed certificate
sample_certiicate = {
    "cert": "-----BEGIN CERTIFICATE-----\nMIIE7TCCA9WgAwIBAgITAPr7gzctRoas3Fq0JY2vAX51IjANBgkqhkiG9w0BAQsF\nADAiMSAwHgYDVQQDDBdGYWtlIExFIEludGVybWVkaWF0ZSBYMTAeFw0xNjEyMDEx\nMDM3MDBaFw0xNzAzMDExMDM3MDBaMB8xHTAbBgNVBAMTFGJsYWJsYS5jbC1taXJy\nb3IuY29tMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA5GHT/paVLcOe\nf2xt1JtPYm71bWOrFoMmkDZjroV4Rx/d9BqD5CjMdUw3MTOz8mn3VIrrhCtOaJ0h\n3Y2GVRU6vDyc6Z3AN9OaUsrsNeQRtUorsepeok/rn5XYoZpUtu4NE5sc0T6/eR6d\nocGejiQ5hrnw5oKlXhmrdHerMc2H8uFECNWBDOgER7D9cBzPOvHiawWVR+jEVuhJ\nYPJt+En/tFy0A8oHHTH5kIq9poN7MTom4tsiJtQfFX284Ot8t41gxqWy7IaWALTj\nuFfEVUi2x9rI7lN2iCFUeL8Zjvrm2zVYGLPTEC5Imoc4IBvJ3yDlS+AFj+9i1r3b\n7SdS7Ell7QIDAQABo4ICHTCCAhkwDgYDVR0PAQH/BAQDAgWgMB0GA1UdJQQWMBQG\nCCsGAQUFBwMBBggrBgEFBQcDAjAMBgNVHRMBAf8EAjAAMB0GA1UdDgQWBBQvxz/l\n8fCzdFQdbDAf4Bm195k+GTAfBgNVHSMEGDAWgBTAzANGuVggzFxycPPhLssgpvVo\nOjB4BggrBgEFBQcBAQRsMGowMwYIKwYBBQUHMAGGJ2h0dHA6Ly9vY3NwLnN0Zy1p\nbnQteDEubGV0c2VuY3J5cHQub3JnLzAzBggrBgEFBQcwAoYnaHR0cDovL2NlcnQu\nc3RnLWludC14MS5sZXRzZW5jcnlwdC5vcmcvMB8GA1UdEQQYMBaCFGJsYWJsYS5j\nbC1taXJyb3IuY29tMIH+BgNVHSAEgfYwgfMwCAYGZ4EMAQIBMIHmBgsrBgEEAYLf\nEwEBATCB1jAmBggrBgEFBQcCARYaaHR0cDovL2Nwcy5sZXRzZW5jcnlwdC5vcmcw\ngasGCCsGAQUFBwICMIGeDIGbVGhpcyBDZXJ0aWZpY2F0ZSBtYXkgb25seSBiZSBy\nZWxpZWQgdXBvbiBieSBSZWx5aW5nIFBhcnRpZXMgYW5kIG9ubHkgaW4gYWNjb3Jk\nYW5jZSB3aXRoIHRoZSBDZXJ0aWZpY2F0ZSBQb2xpY3kgZm91bmQgYXQgaHR0cHM6\nLy9sZXRzZW5jcnlwdC5vcmcvcmVwb3NpdG9yeS8wDQYJKoZIhvcNAQELBQADggEB\nAGP53vaO5XPNOgOUfkS4BCqXwUzAh+UHvyl+ggjHHSSnwNLVsYVWrPeakyvRDG1y\nWTfVJtvOxVZsXCXa08pL3khwYLZBRtqNhktrN4AS2ixT+lSupX40kjIuf/+NEY8T\nnl5CqSj+bck1EJ8irbh5O+zGKuwnXCwe7fI39tr6Havo/nz+QgJqMdeQeSBr3NhO\nFpNq9C3iF+31xJh2FFU7Og+czxR6E+Dxg7JYO+yjBSRtA7R/n7GUXmt89sxRd5ox\naHntAYuARBdBO9E3lrGeDOJk5YKC/yvd+cXlHxFW1q+n0UP16GIVCl/lPnPdg1K+\neWQ67SWkQustRWHLe5sNQtw=\n-----END CERTIFICATE-----\n-----BEGIN CERTIFICATE-----\nMIIEqzCCApOgAwIBAgIRAIvhKg5ZRO08VGQx8JdhT+UwDQYJKoZIhvcNAQELBQAw\nGjEYMBYGA1UEAwwPRmFrZSBMRSBSb290IFgxMB4XDTE2MDUyMzIyMDc1OVoXDTM2\nMDUyMzIyMDc1OVowIjEgMB4GA1UEAwwXRmFrZSBMRSBJbnRlcm1lZGlhdGUgWDEw\nggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDtWKySDn7rWZc5ggjz3ZB0\n8jO4xti3uzINfD5sQ7Lj7hzetUT+wQob+iXSZkhnvx+IvdbXF5/yt8aWPpUKnPym\noLxsYiI5gQBLxNDzIec0OIaflWqAr29m7J8+NNtApEN8nZFnf3bhehZW7AxmS1m0\nZnSsdHw0Fw+bgixPg2MQ9k9oefFeqa+7Kqdlz5bbrUYV2volxhDFtnI4Mh8BiWCN\nxDH1Hizq+GKCcHsinDZWurCqder/afJBnQs+SBSL6MVApHt+d35zjBD92fO2Je56\ndhMfzCgOKXeJ340WhW3TjD1zqLZXeaCyUNRnfOmWZV8nEhtHOFbUCU7r/KkjMZO9\nAgMBAAGjgeMwgeAwDgYDVR0PAQH/BAQDAgGGMBIGA1UdEwEB/wQIMAYBAf8CAQAw\nHQYDVR0OBBYEFMDMA0a5WCDMXHJw8+EuyyCm9Wg6MHoGCCsGAQUFBwEBBG4wbDA0\nBggrBgEFBQcwAYYoaHR0cDovL29jc3Auc3RnLXJvb3QteDEubGV0c2VuY3J5cHQu\nb3JnLzA0BggrBgEFBQcwAoYoaHR0cDovL2NlcnQuc3RnLXJvb3QteDEubGV0c2Vu\nY3J5cHQub3JnLzAfBgNVHSMEGDAWgBTBJnSkikSg5vogKNhcI5pFiBh54DANBgkq\nhkiG9w0BAQsFAAOCAgEABYSu4Il+fI0MYU42OTmEj+1HqQ5DvyAeyCA6sGuZdwjF\nUGeVOv3NnLyfofuUOjEbY5irFCDtnv+0ckukUZN9lz4Q2YjWGUpW4TTu3ieTsaC9\nAFvCSgNHJyWSVtWvB5XDxsqawl1KzHzzwr132bF2rtGtazSqVqK9E07sGHMCf+zp\nDQVDVVGtqZPHwX3KqUtefE621b8RI6VCl4oD30Olf8pjuzG4JKBFRFclzLRjo/h7\nIkkfjZ8wDa7faOjVXx6n+eUQ29cIMCzr8/rNWHS9pYGGQKJiY2xmVC9h12H99Xyf\nzWE9vb5zKP3MVG6neX1hSdo7PEAb9fqRhHkqVsqUvJlIRmvXvVKTwNCP3eCjRCCI\nPTAvjV+4ni786iXwwFYNz8l3PmPLCyQXWGohnJ8iBm+5nk7O2ynaPVW0U2W+pt2w\nSVuvdDM5zGv2f9ltNWUiYZHJ1mmO97jSY/6YfdOUH66iRtQtDkHBRdkNBsMbD+Em\n2TgBldtHNSJBfB3pm9FblgOcJ0FSWcUDWJ7vO0+NTXlgrRofRT6pVywzxVo6dND0\nWzYlTWeUVsO40xJqhgUQRER9YLOLxJ0O6C8i0xFxAMKOtSdodMB3RIwt7RFQ0uyt\nn5Z5MqkYhlMI3J1tPRTp1nEt9fyGspBOO05gi148Qasp+3N+svqKomoQglNoAxU=\n-----END CERTIFICATE-----\n",
    "key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEpQIBAAKCAQEA5GHT/paVLcOef2xt1JtPYm71bWOrFoMmkDZjroV4Rx/d9BqD\n5CjMdUw3MTOz8mn3VIrrhCtOaJ0h3Y2GVRU6vDyc6Z3AN9OaUsrsNeQRtUorsepe\nok/rn5XYoZpUtu4NE5sc0T6/eR6docGejiQ5hrnw5oKlXhmrdHerMc2H8uFECNWB\nDOgER7D9cBzPOvHiawWVR+jEVuhJYPJt+En/tFy0A8oHHTH5kIq9poN7MTom4tsi\nJtQfFX284Ot8t41gxqWy7IaWALTjuFfEVUi2x9rI7lN2iCFUeL8Zjvrm2zVYGLPT\nEC5Imoc4IBvJ3yDlS+AFj+9i1r3b7SdS7Ell7QIDAQABAoIBAQDK8lwuuqWqW1F3\nrmUTL0imEjAqmw0oHjego5SFO7ociib0irN1hwPZoHbTVDyuSJgvGpwbgVhWAnxb\noy4iYZEmQT63IyXy9ikHNageY6OQ1G5r1fduiVK7J6+wO7LYNEaOi6JaF0aTXS96\n1NIPQgWUwZtfW+2T53/DKayJvzj2DKZnhoCHvLohUw35POAfRzG1Y7X70t+EU7fw\nCLmHuydFcbZaXvyNiRws8pU0sgFj+EG4CXTlgr7c6biWoF0FzJb1Nt8R2xcxTKMY\nQRdTuEkJGk44jol5dfwtevkRZNY1vUGv6GarWOzWUcA/Y9L2olnGIdG6uToXD4wx\nzfLrSQFBAoGBAPClqvGuTFEqFpwpy9dXmVD99j1w/U8FvioAf5gLXuRPb+hp5ISg\novugvHuPqPFR/+IA51OiwwaO1IjyDWDvQ74amsSxY+PTBgGelC7LF/jm7SBCsHMu\nLs3F7W7rJZF9jNKSpDMF0W+IT1HD/gTGcPFx9IsGlzZufgH1th4ZR3D5AoGBAPLz\n2BqtxS24yRwlTyj6rEAIGcyKQ0eRzZc7hXU+Q2MPXJbMidzp6urQoK6q5/r70bRH\nUDXNl31vvSlquh4chVOTX903Wr7+qHjzQ+FoL8D1Vhrgju7ifZ5FWdF6sIHvsAg0\nUTLQ2/RsxLGCUKmTtb6OE8eQuZ+wZObyGKnyuA2VAoGBANBXbbcNos8GNEsBOJR4\nJ6liJeStxPC8VRYCFnVpKr9ZMtaxjwFwHYribyw+hRJgXruo8p2LJXOxBrqFbSXG\nIA0e9W1i8stUcDfIthwJAvkf3J34ftFJY4YNXPGRrZXXb6sDABuYZuk7xwhQOcSi\nlTfD4+bVTub2JCvIMeK/GgXpAoGBAJaUMa2fZCWJcQRDz4NbkmUBYFQYoch7Asyn\n9HiNRaDhBYblcND+Hj65Xc3EWZGCgB/XT0x5h1oUZk6EOqStEqmRHwpx44mbNnn4\ndGsBcw+KP3rbEVvX/vmYjCm8fCeckiMTofv33UvqGiLW3P2tciiP0IyRE6t43aES\nDd1PdWndAoGAc65dDq1tZEsWVQHzUxHUW8usWsGrkFXH+MUO3ocfKWF2yHvR9zWK\nxJIo/QAiwowO3bMKy27yZ9fKj1m/RUQdk1Ub30OXdEs9rCo88lEAW/2ruD2BoVQt\nG78eK0PYZnJSWJ5/6AYbVhmO4500GezvvOksa0VkwYFHWtcVsT8EYvs=\n-----END RSA PRIVATE KEY-----\n"}
