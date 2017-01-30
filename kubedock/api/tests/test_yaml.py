
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import mock

from kubedock.api import yaml_api
from kubedock.testutils.fixtures import VALID_TEMPLATE1
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
    image: nginx:1.11
    ports:
    - containerPort: 80"""


class YamlURL(object):
    post = '/yamlapi/'.format


class TestYamlAPI(APITestCase):
    url = '/yamlapi'

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

    @mock.patch.object(yaml_api.KubeUtils, 'get_current_user')
    @mock.patch.object(yaml_api, 'AppInstance')
    def test_switch_pod_plan(self, AppInstanceMock, get_current_user):
        pod_id = '79fd8c00-f6d6-41c5-956f-188e48767bce'
        plan_id = 0
        AppInstanceMock.return_value.update_plan.return_value = {}
        url = self.item_url('switch', pod_id, plan_id)
        self.open(url, 'PUT', auth=self.userauth)
        AppInstanceMock.assert_called_once_with(
            pod_id, get_current_user.return_value)
        AppInstanceMock.return_value.update_plan_by_name.assert_not_called()
        AppInstanceMock.return_value.update_plan.assert_called_once_with(
            plan_id, async=True, dry_run=False)

    @mock.patch.object(yaml_api.KubeUtils, 'get_current_user')
    @mock.patch.object(yaml_api, 'AppInstance')
    def test_switch_pod_plan_by_name(self, AppInstanceMock, get_current_user):
        pod_id = '79fd8c00-f6d6-41c5-956f-188e48767bce'
        plan_id = 'M'
        AppInstanceMock.return_value.update_plan_by_name.return_value = {}
        url = self.item_url('switch', pod_id, plan_id)
        self.open(url, 'PUT', auth=self.userauth)
        AppInstanceMock.assert_called_once_with(
            pod_id, get_current_user.return_value)
        instanceMock = AppInstanceMock.return_value
        instanceMock.update_plan.assert_not_called()
        instanceMock.update_plan_by_name.assert_called_once_with(
            plan_id, async=True, dry_run=False)

    def test_check_for_update(self):
        # Add PA and pod
        data = self.admin_open('/predefined-apps', 'POST', {
            'name': 'test', 'template': VALID_TEMPLATE1}).json['data']
        pa_id, version_id_1 = data['id'], data['activeVersionID']
        pod = self.fixtures.pod(template_id=pa_id,
                                template_version_id=version_id_1,
                                template_plan_name='M')

        resp = self.user_open(self.item_url('update', pod.id))
        self.assert200(resp)
        self.assertEqual(resp.json['data'], {
            "activeVersionID": version_id_1,
            "currentVersionID": version_id_1,
            "updateAvailable": False,
        })

        # add a new version (not active)
        data = self.admin_open('/predefined-apps/{}'.format(pa_id), 'POST', {
            'template': VALID_TEMPLATE1}).json['data']
        version_id_2 = data['templates'][1]['id']

        resp = self.user_open(self.item_url('update', pod.id))
        self.assert200(resp)
        self.assertEqual(resp.json['data'], {
            "activeVersionID": version_id_1,
            "currentVersionID": version_id_1,
            "updateAvailable": False,
        })

        # make second version the active one
        url = '/predefined-apps/{}/{}'.format(pa_id, version_id_2)
        resp = self.admin_open(url, 'PUT', {'active': True})

        resp = self.user_open(self.item_url('update', pod.id))
        self.assert200(resp)
        self.assertEqual(resp.json['data'], {
            "activeVersionID": version_id_2,
            "currentVersionID": version_id_1,
            "updateAvailable": True,
        })

    @mock.patch('kubedock.kapi.apps.PodCollection')
    def test_update_app(self, PodCollection):
        # Add PA and pod
        data = self.admin_open('/predefined-apps', 'POST', {
            'name': 'test', 'template': VALID_TEMPLATE1}).json['data']
        pa_id, version_id_1 = data['id'], data['activeVersionID']
        pod = self.fixtures.pod(template_id=pa_id,
                                template_version_id=version_id_1,
                                template_plan_name='M',
                                owner=self.user)

        # if there is no available update, do nothing
        resp = self.user_open(self.item_url('update', pod.id), 'POST')
        self.assert200(resp)
        self.assertFalse(PodCollection.called)

        # add a new version
        data = self.admin_open('/predefined-apps/{}'.format(pa_id), 'POST', {
            'template': VALID_TEMPLATE1, 'active': True}).json['data']
        version_id_2 = data['activeVersionID']

        # perform the update
        resp = self.user_open(self.item_url('update', pod.id), 'POST')
        self.assert200(resp)

        PodCollection.assert_called_once_with(self.user)
        pod_collection = PodCollection.return_value
        pod_collection._get_by_id.assert_called_once_with(pod.id)
        pod_collection.edit.assert_called_once_with(
            pod_collection._get_by_id.return_value, mock.ANY)
        second_arg = pod_collection.edit.call_args[0][1]
        self.assertIn('edited_config', second_arg)
        pod_collection.update.assert_called_once_with(pod.id, {
            'command': 'redeploy', 'commandOptions': {
                'applyEdit': True,
                'internalEdit': True,
            }
        })

        self.assertEqual(pod.template_version_id, version_id_2)
