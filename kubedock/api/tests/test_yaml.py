import mock

from kubedock.api import yaml_api
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
          kdCopyFromImage: true
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
        response = self.user_open(YamlURL.post(), 'POST')
        self.assertAPIError(response, 400, 'InsufficientData')

    def test_invalid_yml_file(self):
        response = self.user_open(YamlURL.post(), 'POST', {
            'data': """
            - a
            b
            """
        })
        self.assertAPIError(response, 400, 'UnparseableTemplate')

    def test_no_object(self):
        response = self.user_open(YamlURL.post(), 'POST', {
            'data': ""
        })
        self.assertAPIError(response, 400, 'ValidationError',
                            {'data': 'empty values not allowed'})

    def test_no_document(self):
        response = self.user_open(YamlURL.post(), 'POST', {
            'data': "123123"
        })
        self.assertAPIError(response, 400, 'ValidationError')

    def test_no_kind(self):
        response = self.user_open(YamlURL.post(), 'POST', {
            'data': """
            apiVersion: 1
            """
        })
        self.assertAPIError(response, 400, 'ValidationError')

    def test_no_api_version(self):
        response = self.user_open(YamlURL.post(), 'POST', {
            'data': """
            kind: Pod
            """
        })
        self.assertAPIError(response, 400, 'ValidationError')

    def test_usupported_object_kind(self):
        response = self.user_open(YamlURL.post(), 'POST', {
            'data': """
            apiVersion: v1
            kind:
                - Pod
                - Pod2
            """
        })
        self.assertAPIError(response, 400, 'ValidationError')

    def test_duplicate_kind(self):
        for kind in ['Pod', 'ReplicationController', 'Service']:
            response = self.user_open(YamlURL.post(), 'POST', {
                'data': "---\n"
                        "apiVersion: v1\n"
                        "kind: {0}\n"
                        "---\n"
                        "apiVersion: v1\n"
                        "kind: {0}\n".format(kind)
            })
            self.assertAPIError(response, 400, 'ValidationError')

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
            response = self.user_open(YamlURL.post(), 'POST', {
                'data': item
            })
            self.assertAPIError(response, 400, 'ValidationError')

    @mock.patch.object(yaml_api, 'send_event_to_user')
    @mock.patch('kubedock.validation.V._validate_kube_type_exists')
    @mock.patch('kubedock.kapi.apps.PodCollection')
    def test_correct_yaml(self, PodCollection, *_):
        PodCollection().add.return_value = {}

        for yml_config in [_CORRECT_NGINX_YAML, _CORRECT_REDIS_YML]:
            response = self.user_open(YamlURL.post(), 'POST', {
                'data': yml_config
            })
            self.assert200(response)
