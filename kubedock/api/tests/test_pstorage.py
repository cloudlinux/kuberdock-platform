import json
import unittest
import mock
from kubedock.pods.models import PersistentDisk
from kubedock.testutils.testcases import APITestCase
from kubedock.utils import API_VERSIONS

url = '/pstorage'


class TestPStorageApiGeneral(APITestCase):
    @mock.patch('kubedock.kapi.node_utils.get_nodes_collection')
    def test_user_has_permissions(self, m1):
        m1.return_value = []
        self.assert200(self.open(url, auth=self.userauth))

    def test_admin_has_no_permissions(self):
        self.assert403(self.open(url, auth=self.adminauth))

    def test_not_authenticated_has_no_permissions(self):
        self.assert401(self.open(url, auth=None))


class TestPStorageApiGet(APITestCase):
    url = url

    def setUp(self):
        self.pod = self.fixtures.pod(
            owner_id=self.user.id,
            config=json.dumps({
                "volumes_public": [
                    {
                        "persistentDisk": {"pdSize": 1, "pdName": 'q'},
                    }
                ]

            })
        )
        self.free_pd = PersistentDisk.create(size=3, owner=self.user,
                                             name='free-pd')
        self.non_free_pd = PersistentDisk.create(size=2, owner=self.user,
                                                 name='non-free-pd',
                                                 pod_id=self.pod.id)
        self.free_pd.save()
        self.non_free_pd.save()

    @mock.patch('kubedock.kapi.node_utils.get_nodes_collection')
    def test_get_one(self, m1):
        m1.return_value = []
        device_id = self.free_pd.id
        res = self.user_open(self.item_url(device_id), 'GET')
        self.assert200(res)
        data = res.json['data']
        data_exp = {'name': 'free-pd', 'size': 3, 'owner': self.user.username}
        self.assertEqual(data['id'], device_id)
        for k, v in data_exp.items():
            self.assertEqual(data[k], v)

    @mock.patch('kubedock.kapi.node_utils.get_nodes_collection')
    def test_get_all(self, m1):
        m1.return_value = []
        res = self.user_open()
        self.assert200(res)
        self.assertEqual(res.json['status'], 'OK')
        data_all = res.json['data']
        self.assertEqual(len(data_all), 2)
        data_all_dict = {d['id']: d for d in data_all}
        self.assertEqual(len(data_all_dict), 2)

        pd = self.free_pd
        data = data_all_dict[pd.id]
        expected = {
            'name': 'free-pd',
            'owner': self.user.username,
            'owner_id': self.user.id,
            'size': 3,
            'id': pd.id,
            'pod_id': None,
            'pod_name': None,
            'in_use': False
        }
        for k, v in expected.items():
            self.assertEqual(data[k], v)

        pd = self.non_free_pd
        data = data_all_dict[pd.id]
        expected = {
            'name': 'non-free-pd',
            'owner': self.user.username,
            'owner_id': self.user.id,
            'size': 2,
            'id': pd.id,
            'pod_id': self.pod.id,
            'pod_name': self.pod.name,
            'in_use': True,
        }
        for k, v in expected.items():
            self.assertEqual(data[k], v)

    @mock.patch('kubedock.kapi.node_utils.get_nodes_collection')
    def test_get_free_only(self, m1):
        m1.return_value = []
        res = self.user_open(query_string={'free-only': 'true'})
        self.assert200(res)
        data = res.json['data']
        self.assertEqual(len(data), 1)
        pd_data = data[0]
        expected = {
            'id': self.free_pd.id,
            'name': 'free-pd',
            'in_use': False
        }
        for k, v in expected.items():
            self.assertEqual(pd_data[k], v)

    @mock.patch('kubedock.kapi.node_utils.get_nodes_collection')
    def test_device_not_exists(self, m1):
        m1.return_value = []
        res = self.user_open(self.item_url('not_existed'))
        self.assertAPIError(res, 404, 'PDNotFound')


class TestPStorageApiPost(APITestCase):
    url = url
    devices = [{
        'name': 'device1',
        'size': 1
    }, {
        'name': 'device2',
        'size': 2
    }]

    @unittest.skip('bliss')
    def test_good_path(self):
        resp = self.user_open(url, 'POST', self.devices[0])
        self.assert200(resp)
        disk_id = resp.json['data']['id']
        disk = PersistentDisk.query.get(disk_id)
        self.assertIsNotNone(disk)
        expected = {
            'status': 'OK',
            'data': disk.to_dict()
        }
        self.assertEqual(expected, resp.json)

    def checkValidation(self, data, errors, message='Invalid data: '):
        resp = self.user_open(url, 'POST', data, version=API_VERSIONS.v1)
        self.assertAPIError(resp, 400, 'ValidationError', errors)
        self.assertEqual(resp.json['data'], errors)

        resp = self.user_open(url, 'POST', data, version=API_VERSIONS.v2)
        self.assertAPIError(resp, 400, 'ValidationError', errors)
        self.assertIn(message, resp.json['message'])

    def test_size_less_zero(self):
        self.checkValidation({'name': 'some_name', 'size': -1},
                             {'size': 'min value is 1'})

    def test_size_equal_zero(self):
        self.checkValidation({'name': 'some_name', 'size': 0},
                             {'size': 'min value is 1'})

    def test_size_is_not_number(self):
        self.checkValidation({'name': 'some_name', 'size': 'zxc'},
                             {'size': ["field 'size' could not be coerced",
                                       'must be of integer type']})

    def test_size_is_not_specified(self):
        self.checkValidation({'name': 'some_name'}, {'size': 'required field'})

    def test_name_is_not_specified(self):
        self.checkValidation({'size': 1}, {'name': 'required field'})

    def test_name_is_empty(self):
        self.checkValidation({'name': '', 'size': 1}, {'name': [
            u'Latin letters, digits, undescores and dashes are '
            'expected only. Must start with a letter',
            u'empty values not allowed']})

    def test_name_is_not_a_string(self):
        self.checkValidation({'name': 1, 'size': 1},
                             {'name': 'must be of string type'})

    def test_already_exists(self):
        existed = PersistentDisk.create(owner=self.user,
                                        name=self.devices[0]['name'], size=1)
        existed.save()
        res = self.user_open(url, 'POST', self.devices[0])
        self.assertAPIError(res, 406, 'DuplicateName')

    @mock.patch('kubedock.pods.models.PersistentDisk.save')
    def test_creation_fallen(self, save_mock):
        save_mock.side_effect = Exception('test exception')
        res = self.user_open(url, 'POST', self.devices[0])
        self.assertAPIError(res, 400, 'APIError')


class TestPStorageApiDelete(APITestCase):
    url = url

    def setUp(self):
        self.pod = self.fixtures.pod(
            owner_id=self.user.id,
            config=json.dumps({
                "volumes_public": [
                    {
                        "persistentDisk": {"pdSize": 1, "pdName": 'q'},
                    }
                ]
            })
        )
        self.free_pd = PersistentDisk.create(size=3, owner=self.user,
                                             name='free-pd')
        self.non_free_pd = PersistentDisk.create(size=2, owner=self.user,
                                                 name='non-free-pd',
                                                 pod_id=self.pod.id)
        self.free_pd.save()
        self.non_free_pd.save()

    @mock.patch('kubedock.kapi.pstorage.delete_drive_by_id')
    def test_pstorage_delete_called(self, delete_mock):
        res = self.user_open(self.item_url(self.free_pd.id), method='DELETE')
        self.assert200(res)
        delete_mock.assert_called_once_with(self.free_pd.id, force=None)

    @mock.patch('kubedock.kapi.node_utils.get_nodes_collection')
    def test_delete_free_pd(self, m1):
        m1.return_value = []
        res = self.user_open(self.item_url(self.free_pd.id), method='DELETE')
        self.assert200(res)
        res1 = self.user_open(self.item_url(self.free_pd.id))
        self.assert404(res1)

    def test_delete_non_free_pd_raise_exception(self):
        res = self.user_open(self.item_url(self.non_free_pd.id),
                             method='DELETE')
        self.assertAPIError(res, 400, 'PDIsUsed')

    def test_delete_non_free_pd_force(self):
        res = self.user_open(self.item_url(self.non_free_pd.id),
                             method='DELETE', json={'force': True})
        self.assert200(res)

    @mock.patch('kubedock.kapi.node_utils.get_nodes_collection')
    def test_used_disk_is_not_deleted(self, m1):
        m1.return_value = []
        res = self.user_open(self.item_url(self.non_free_pd.id),
                             method='DELETE')

        self.assert400(res)
        res1 = self.user_open(self.item_url(self.non_free_pd.id))
        self.assert200(res1)

    def test_device_not_exists(self):
        res = self.user_open(self.item_url('not_existed'), method='DELETE')
        self.assert404(res)

    @mock.patch('kubedock.pods.models.PersistentDisk.owner_id',
                new_callable=mock.PropertyMock)
    def test_device_is_not_owned_by_current_user(self, mock_owner_id):
        mock_owner_id.return_value = 0
        res = self.user_open(self.item_url(self.free_pd.id), method='DELETE')
        self.assertAPIError(res, 404, 'PDNotFound')

    @mock.patch('kubedock.kapi.pstorage.drive_can_be_deleted')
    def test_cannot_be_deleted(self, mock_can_be_deleted):
        mock_can_be_deleted.return_value = (False, 'Test description')
        res = self.user_open(self.item_url(self.free_pd.id), method='DELETE')
        self.assertAPIError(res, 400, 'APIError')

    def test_not_allowed_without_args(self):
        self.assert405(self.open(method='DELETE', auth=self.userauth))
