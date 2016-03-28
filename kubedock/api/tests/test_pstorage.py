import mock
from kubedock.kapi.podcollection import PodCollection
from kubedock.pods.models import PersistentDisk
from kubedock.testutils.testcases import APITestCase

url = '/pstorage'


class TestPStorageApiGeneral(APITestCase):
    def test_user_has_permissions(self):
        self.assert200(self.open(url, auth=self.userauth))

    def test_admin_has_no_permissions(self):
        self.assert403(self.open(url, auth=self.adminauth))

    def test_not_authenticated(self):
        self.assert401(self.open(url, auth=None))


class TestPStorageApiGet(APITestCase):
    url = url

    def setUp(self):
        super(TestPStorageApiGet, self).setUp()

        pod_dict = PodCollection(self.user).add(params={'containers': [], 'name': 'test_pod'})
        pod_id = pod_dict['id']
        self.free_pd = PersistentDisk.create(size=3, owner=self.user, name='free-pd')
        self.non_free_pd = PersistentDisk.create(size=2, owner=self.user, name='non-free-pd', pod_id=pod_id)
        self.free_pd.save()
        self.non_free_pd.save()
        self.pod_id = pod_id

    def test_get_one(self):
        device_id = self.free_pd.id
        res = self.open(self.item_url(device_id), 'GET', auth=self.userauth)
        self.assert200(res)
        data = res.json['data']
        data_exp = {'name': 'free-pd', 'size': 3, 'owner': self.user.username}
        self.assertEqual(data['id'], device_id)
        for k, v in data_exp.items():
            self.assertEqual(data[k], v)

    def test_get_all(self):
        res = self.open(url, auth=self.userauth)
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
            'pod_id': self.pod_id,
            'pod_name': 'test_pod',
            'in_use': True,
        }
        for k, v in expected.items():
            self.assertEqual(data[k], v)

    def test_get_free_only(self):
        res = self.open(url, json={'free-only': 'true'}, auth=self.userauth)
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

    def test_device_not_exists(self):
        res = self.open(self.item_url('not_existed'), auth=self.userauth)
        self.assert404(res)
        self.assertEqual(res.json, {
            "data": "Persistent disk not found.",
            "status": "error",
            "type": "PDNotFound"
        })


class TestPStorageApiPost(APITestCase):
    url = url
    devices = [{
        'name': 'device1',
        'size': 1
    }, {
        'name': 'device2',
        'size': 2
    }]

    def test_good_path(self):
        resp = self.open(url, 'POST', self.devices[0], self.userauth)
        self.assert200(resp)
        disk_id = resp.json['data']['id']
        disk = PersistentDisk.query.get(disk_id)
        self.assertIsNotNone(disk)
        expected = {
            'status': 'OK',
            'data': disk.to_dict()
        }
        self.assertEqual(expected, resp.json)

    def test_size_less_zero(self):
        resp = self.open(
            url, 'POST', {'name': 'some_name', 'size': -1}, self.userauth)
        expected = {
            'data': '"size" must be > 0',
            'status': 'error',
            'type': 'APIError'
        }
        self.assert400(resp)
        self.assertEqual(expected, resp.json)

    def test_size_equal_zero(self):
        resp = self.open(
            url, 'POST', {'name': 'some_name', 'size': 0}, self.userauth)
        expected = {
            'data': '"size" must be > 0',
            'status': 'error',
            'type': 'APIError'
        }
        self.assert400(resp)
        self.assertEqual(expected, resp.json)

    def test_size_is_not_number(self):
        resp = self.open(
            url, 'POST', {'name': 'some_name', 'size': 'zxc'}, self.userauth)
        expected = {
            'data': '"size" must be an integer',
            'status': 'error',
            'type': 'APIError'
        }
        self.assert400(resp)
        self.assertEqual(expected, resp.json)

    def test_size_is_not_specified(self):
        resp = self.open(
            url, 'POST', {'name': 'some_name'}, self.userauth)
        expected = {
            'data': '["name", "size"] are mandatory fields',
            'status': 'error',
            'type': 'APIError'
        }
        self.assert400(resp)
        self.assertEqual(expected, resp.json)

    def test_name_is_not_specified(self):
        resp = self.open(
            url, 'POST', {'size': 1}, self.userauth)
        expected = {
            'data': '["name", "size"] are mandatory fields',
            'status': 'error',
            'type': 'APIError'
        }
        self.assert400(resp)
        self.assertEqual(expected, resp.json)

    def test_name_is_empty(self):
        resp = self.open(
            url, 'POST', {'name': '', 'size': 1}, self.userauth)
        expected = {
            'data': '"name" must be not empty',
            'status': 'error',
            'type': 'APIError'
        }
        self.assert400(resp)
        self.assertEqual(expected, resp.json)

    def test_name_is_not_a_string(self):
        resp = self.open(
            url, 'POST', {'name': 1, 'size': 1}, self.userauth)
        expected = {
            'data': '"name" must be a string',
            'status': 'error',
            'type': 'APIError'
        }
        self.assert400(resp)
        self.assertEqual(expected, resp.json)

    def test_already_exists(self):
        existed = PersistentDisk.create(owner=self.user, name=self.devices[0]['name'], size=1)
        existed.save()
        res = self.open(url, 'POST', self.devices[0], self.userauth)
        self.assertStatus(res, 406)
        self.assertEqual(res.json, {
            "data": "device1 already exists",
            "status": "error",
            "type": "APIError"
        })

    @mock.patch('kubedock.pods.models.PersistentDisk.save')
    def test_creation_fallen(self, save_mock):
        save_mock.side_effect = Exception('test exception')
        res = self.open(url, 'POST', self.devices[0], self.userauth)
        self.assert400(res)
        self.assertEqual(res.json, {
            "data": "Couldn't save persistent disk.",
            "status": "error",
            "type": "APIError"
        })


class TestPStorageApiDelete(APITestCase):
    url = url

    def setUp(self):
        super(TestPStorageApiDelete, self).setUp()

        pod_dict = PodCollection(self.user).add(params={'containers': [], 'name': 'test_pod'})
        pod_id = pod_dict['id']
        self.free_pd = PersistentDisk.create(size=3, owner=self.user, name='free-pd')
        self.non_free_pd = PersistentDisk.create(size=2, owner=self.user, name='non-free-pd', pod_id=pod_id)
        self.free_pd.save()
        self.non_free_pd.save()
        self.pod_id = pod_id

    @mock.patch('kubedock.kapi.pstorage.delete_drive_by_id')
    def test_pstorage_delete_called(self, delete_mock):
        res = self.open(self.item_url(self.free_pd.id),
                        method='DELETE', auth=self.userauth)
        self.assert200(res)
        delete_mock.assert_called_once_with(self.free_pd.id)

    def test_delete_free_pd(self):
        res = self.open(self.item_url(self.free_pd.id),
                        method='DELETE', auth=self.userauth)
        self.assert200(res)
        res1 = self.open(self.item_url(self.free_pd.id), auth=self.userauth)
        self.assert404(res1)

    def test_delete_non_free_pd_raise_exception(self):
        res = self.open(self.item_url(self.non_free_pd.id),
                        method='DELETE', auth=self.userauth)
        self.assert400(res)
        self.assertEqual(res.json, {
            "data": "Persistent disk is used.",
            "status": "error",
            "type": "PDIsUsed"
        })

    def test_used_disk_is_not_deleted(self):
        res = self.open(self.item_url(self.non_free_pd.id),
                        method='DELETE', auth=self.userauth)

        self.assert400(res)
        res1 = self.open(self.item_url(self.non_free_pd.id),
                         method='GET', auth=self.userauth)
        self.assert200(res1)

    def test_device_not_exists(self):
        res = self.open(self.item_url('not_existed'),
                        method='DELETE', auth=self.userauth)
        self.assert404(res)

    @mock.patch('kubedock.pods.models.PersistentDisk.owner_id',
                new_callable=mock.PropertyMock)
    def test_device_is_not_owned_by_current_user(self, mock_owner_id):
        mock_owner_id.return_value = 0
        res = self.open(self.item_url(self.free_pd.id),
                        method='DELETE', auth=self.userauth)
        self.assert403(res)
        self.assertEqual(res.json, {
            "data": "Volume does not belong to current user",
            "status": "error",
            "type": "APIError"
        })

    @mock.patch('kubedock.kapi.pstorage.drive_can_be_deleted')
    def test_cannot_be_deleted(self, mock_can_be_deleted):
        mock_can_be_deleted.return_value = (False, 'Test description')
        res = self.open(self.item_url(self.free_pd.id),
                        method='DELETE', auth=self.userauth)
        self.assert400(res)
        self.assertEqual(res.json, {
            "data": "Volume can not be deleted. Reason: Test description",
            "status": "error",
            "type": "APIError"
        })

    def test_not_allowed_without_args(self):
        self.assert405(self.open(url, method='DELETE', auth=self.userauth))
