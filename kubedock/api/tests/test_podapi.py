from random import randint
from uuid import uuid4

import mock

from kubedock.kapi.podcollection import PodNotFound
from kubedock.testutils.testcases import APITestCase


def valid_create_pod_params():
    return {
        'name': 'just name',
        'containers': [{
            'name': 'just name',  # hasn't in the validation schema
            'image': 'simple-image'
        }],
        'kube_type': 0,
        'restartPolicy': 'Always'
    }


class PodAPIUrl(object):
    get = '/podapi/{0}'.format
    post = '/podapi/'.format
    put = '/podapi/{0}'.format
    delete = '/podapi/{0}'.format

    check_updates = '/podapi/{0}/{1}/update'.format
    update_container = '/podapi/{0}/{1}/update'.format


class TestPodAPI(APITestCase):
    @mock.patch('kubedock.api.podapi.PodCollection')
    def test_get_not_found(self, PodCollection):
        PodCollection().get.side_effect = PodNotFound()

        response = self.open(
            PodAPIUrl.get(12345), 'GET', auth=self.userauth)

        self.assertAPIError(response, 404, 'PodNotFound')

    def test_post_invalid_params(self):
        response = self.open(
            PodAPIUrl.post(), 'POST', {}, auth=self.userauth)

        self.assertAPIError(response, 400, 'APIError')

    @mock.patch('kubedock.validation.V._validate_kube_type_exists')
    # @mock.patch('kubedock.kapi.images.Image._check_availability')
    @mock.patch('kubedock.api.podapi.PodCollection')
    def test_post(self, PodCollection, *_):
        PodCollection().add.return_value = {}
        response = self.open(
            PodAPIUrl.post(), 'POST', valid_create_pod_params(),
            auth=self.userauth)

        self.assert200(response)

    def test_put_invalid(self):
        response = self.open(
            PodAPIUrl.put(str(uuid4())), 'PUT', {}, auth=self.userauth)

        self.assertAPIError(response, 404, 'PodNotFound')

    @mock.patch('kubedock.api.podapi.Pod')
    @mock.patch('kubedock.api.podapi.PodCollection')
    def test_put(self, PodCollection, Pod):
        pod_id = randint(1, 1000)
        PodCollection().update.return_value = {}
        Pod.query = mock.Mock()

        response = self.open(
            PodAPIUrl.put(pod_id), 'PUT', {},
            auth=self.userauth)

        self.assert200(response)

    @mock.patch('kubedock.api.podapi.PodCollection')
    def test_delete_not_found(self, PodCollection):
        PodCollection().delete.side_effect = PodNotFound()

        response = self.open(
            PodAPIUrl.delete(123), 'DELETE', {}, auth=self.userauth)

        self.assertAPIError(response, 404, 'PodNotFound')

    @mock.patch('kubedock.api.podapi.PodCollection')
    def test_delete(self, PodCollection):
        delete_id = randint(1, 1000)
        PodCollection().delete.return_value = delete_id

        response = self.open(
            PodAPIUrl.delete(delete_id), 'DELETE', {}, auth=self.userauth)

        self.assert200(response)

    @mock.patch('kubedock.api.podapi.PodCollection')
    def test_check_updates(self, PodCollection):
        PodCollection().check_updates.return_value = False

        pod_id = str(uuid4())
        container_name = 'just name'

        response = self.open(
            PodAPIUrl.check_updates(pod_id, container_name),
            'GET', {}, auth=self.userauth)

        self.assert200(response)

        PodCollection().check_updates.assert_called_once_with(
            pod_id, container_name)

    @mock.patch('kubedock.api.podapi.PodCollection')
    def test_update_container(self, PodCollection):
        PodCollection().update_container.return_value = {}

        pod_id = str(uuid4())
        container_name = 'just name'

        response = self.open(
            PodAPIUrl.check_updates(pod_id, container_name),
            'POST', {}, auth=self.userauth)

        self.assert200(response)

        PodCollection().update_container.assert_called_once_with(
            pod_id, container_name)
