import mock

from kubedock.api import yaml_api
from kubedock.kapi import podcollection
from kubedock.testutils.testcases import APITestCase

_CORRECT_REDIS_YML = """
apiVersion: v1
kind: ReplicationController
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    name: redis
  template:
    metadata:
      labels:
        name: redis
    spec:
      containers:
      - name: redis
        image: kubernetes/redis:v1
        ports:
        - containerPort: 6379
        volumeMounts:
        - mountPath: /redis-master-data
          name: data
      volumes:
        - name: data
"""

_CORRECT_NGINX_YAML = """
apiVersion: v1
kind: Pod
metadata:
  name: nginx
spec:
  containers:
  - name: nginx
    image: nginx
    ports:
    - containerPort: 80"""


class YamlURL(object):
    post = '/yamlapi/'.format


class TestYamlAPI(APITestCase):
    def test_invalid_data(self):
        response = self.open(YamlURL.post(), 'POST', auth=self.userauth)
        self.assertAPIError(response, 400, 'APIError')

    def test_invalid_yml_file(self):
        response = self.open(YamlURL.post(), 'POST', {
            'data': """
            - a
            b
            """
        }, auth=self.userauth)
        self.assertAPIError(response, 400, 'APIError')

    def test_no_object(self):
        response = self.open(YamlURL.post(), 'POST', {
            'data': ""
        }, auth=self.userauth)
        self.assertAPIError(response, 400, 'APIError')

    def test_no_document(self):
        response = self.open(YamlURL.post(), 'POST', {
            'data': "123123"
        }, auth=self.userauth)
        self.assertAPIError(response, 400, 'APIError')

    def test_no_kind(self):
        response = self.open(YamlURL.post(), 'POST', {
            'data': """
            apiVersion: 1
            """
        }, auth=self.userauth)
        self.assertAPIError(response, 400, 'APIError')

    def test_no_api_version(self):
        response = self.open(YamlURL.post(), 'POST', {
            'data': """
            kind: Pod
            """
        }, auth=self.userauth)
        self.assertAPIError(response, 400, 'APIError')

    def test_usupported_object_kind(self):
        response = self.open(YamlURL.post(), 'POST', {
            'data': """
            apiVersion: v1
            kind:
                - Pod
                - Pod2
            """
        }, auth=self.userauth)
        self.assertAPIError(response, 400, 'APIError')

    def test_duplicate_kind(self):
        for kind in ['Pod', 'ReplicationController', 'Service']:
            response = self.open(YamlURL.post(), 'POST', {
                'data': "---\n"
                        "apiVersion: v1\n"
                        "kind: {0}\n"
                        "---\n"
                        "apiVersion: v1\n"
                        "kind: {0}\n".format(kind)
            }, auth=self.userauth)
            self.assertAPIError(response, 400, 'APIError')

    def test_invalid_pod_and_rc(self):
        # not found pod and rc
        data = (
            "---\n"
            "apiVersion: v1\n"
            "kind: Pod\n"
            "---\n"
            "apiVersion: v1\n"
            "kind: ReplicationController\n",  # found pod and rc
            "apiVersion: v1\n"
            "kind: Service\n",  # not found pod and rc
        )

        for item in data:
            response = self.open(YamlURL.post(), 'POST', {
                'data': item
            }, auth=self.userauth)
            self.assertAPIError(response, 400, 'APIError')

    @mock.patch.object(yaml_api, 'send_event')
    @mock.patch('kubedock.validation.V._validate_kube_type_exists')
    @mock.patch.object(podcollection.PodCollection, 'add')
    def test_correct_yaml(self, add, *_):
        add.return_value = {}
        for yml_config in [_CORRECT_NGINX_YAML, _CORRECT_REDIS_YML]:
            response = self.open(YamlURL.post(), 'POST', {
                'data': yml_config
            }, auth=self.userauth)
            self.assert200(response)
