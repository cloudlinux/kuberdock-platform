"""Tests for container.container.py classes"""
import copy
import json
import os
import shutil
import tempfile
import unittest

import mock
from kubecli.container import container
from kubecli.image import image

PODAPI_GET_RESULT1 = {
    'data': [
        {
            'name': 'a', 'status': 'running',
            'labels': {'name': 'a'},
            'containers': [{'image': 'img1'}, {}],
            'id': "176b9f1c-b25f-481e-98d0-034dd435f9a8"
        },
        {'name': 'b', 'id': "176b9f1c-b25f-481e-98d0-034dd435f934"}
    ]
}

GET_KUBE_TYPES_RESPONSE = {
    "data": {
        "High CPU": 1,
        "High memory": 2,
        "Standard": 0
    },
    "status": "OK"
}

PSTORAGE_GET_RESPONSE = {
    'data': [
        {'id': '1', 'name': 'test1', 'size': 1, 'in_use': False},
        {'id': '2', 'name': 'test2', 'size': 2, 'in_use': False}
    ]
}


class TestKubeCtl(unittest.TestCase):
    """Tests for container.KubeCtl class"""

    @mock.patch.object(container.KubeQuery, 'get')
    @mock.patch.object(container.PrintOut, 'show_list')
    def test_get(self, showlist_mock, get_mock):
        """Test for KubeCtl.get method."""
        get_mock.return_value = PODAPI_GET_RESULT1
        kctl = container.KubeCtl(json=False, resource='pod')
        kctl.get()
        get_mock.assert_called_with(container.PODAPI_PATH)
        showlist_mock.assert_called_once_with([
            {'name': 'a', 'status': 'running', u'labels': 'name=a',
             'images': u'img1,imageless', 'template_id': '???'},
            {'name': 'b', 'status': '???', 'labels': u'', 'images': u'',
             'template_id': '???'}
        ])

    @mock.patch.object(container.KubeQuery, 'get')
    @mock.patch.object(container.PrintOut, 'show')
    def test_describe(self, show_mock, get_mock):
        """Test for KubeCtl.describe method."""
        get_result = PODAPI_GET_RESULT1
        get_mock.return_value = get_result
        kctl = container.KubeCtl(json=False, name='a', resource='pod')
        kctl.describe()
        show_mock.assert_called_once_with(get_result['data'][0])
        kctl = container.KubeCtl(json=False, name='aaaa', resource='pod')
        self.assertRaises(SystemExit, kctl.describe)

    @mock.patch.object(container.KubeCtl, '_set_delayed')
    @mock.patch.object(container.KubeQuery, 'get')
    @mock.patch.object(container.KubeQuery, 'delete')
    def test_delete(self, delete_mock, get_mock, setdelayed_mock):
        """Test for KubeCtl.delete method."""
        get_result = PODAPI_GET_RESULT1
        get_mock.return_value = get_result
        kctl = container.KubeCtl(json=False, name='a', resource='pod')
        kctl.delete()
        get_mock.assert_called_once_with(container.PODAPI_PATH)
        delete_mock.assert_called_once_with(
            container.PODAPI_PATH + get_result['data'][0]['id'])
        setdelayed_mock.assert_called_once_with()
        kctl = container.KubeCtl(json=False, name='aaaa', resource='pod')
        self.assertRaises(SystemExit, kctl.delete)

    @mock.patch.object(container.KubeQuery, 'post')
    def test_create_pod(self, post_mock):
        """Test for KubeCtl.create (pod) method."""
        post_mock.return_value = {'status': 'OK'}
        with tempfile.TemporaryFile(mode='w+') as f:
            f.write('one\n')
            f.write('two')
            f.seek(0)
            kctl = container.KubeCtl(json=False, filename=f, resource='pod')
            kctl.create()
        post_mock.assert_called_once_with(container.POD_CREATE_API_PATH,
                                          {'data': 'one\ntwo'})

    @mock.patch.object(container.KubeQuery, 'post')
    def test_create_template(self, post_mock):
        """Test for KubeCtl.create (template) method."""
        post_mock.return_value = {'status': 'OK'}
        with tempfile.TemporaryFile(mode='w+') as f:
            f.write('one\n')
            f.write('two')
            f.seek(0)
            kctl = container.KubeCtl(json=False, filename=f,
                                     resource='template',
                                     origin='cpanel',
                                     name='test')
            kctl.create()
        post_mock.assert_called_once_with(container.PREDEFINED_APPS_PATH,
                                          {'template': 'one\ntwo',
                                           'origin': 'cpanel', 'name': 'test'})


class TestKuberDock(unittest.TestCase):
    """Tests for container.KuberDock class"""

    def setUp(self):
        """Replaces default kube directory with temporary one"""
        self.original_kubedir = container.KuberDock
        container.KuberDock.KUBEDIR = tempfile.mkdtemp()

    def tearDown(self):
        """Revert setup changes."""
        shutil.rmtree(container.KuberDock.KUBEDIR)
        container.KuberDock.KUBEDIR = self.original_kubedir

    def test_create(self):
        """Test for KuberDock.create method."""
        name = 'tmp1'
        kd = container.KuberDock(name=name, action='create')
        kd.create()
        # check created structure
        self.assertTrue(os.path.exists(kd._data_path))
        with open(kd._data_path) as fin:
            data = json.load(fin)
        self.assertEqual(data['name'], name)

    @mock.patch.object(container.KubeQuery, 'get')
    @mock.patch.object(container.KubeQuery, 'post')
    def test_set(self, post_mock, get_mock):
        """Test for KuberDock.set method."""

        name = 'tmp1'
        imagename = 'c1'

        # return value for POST /api/images/new
        post_mock.return_value = {
            "data": {
                "command": [],
                "env": [],
                "image": imagename,
                "ports": [],
                "volumeMounts": [],
                "workingDir": ""
            }
        }

        # return value for GET /api/pstorage
        get_mock.return_value = {"data": []}

        kd = container.KuberDock(name=name, action='create',
                                 restartPolicy="Always")
        kd.create()
        with open(kd._data_path) as fin:
            data = json.load(fin)
        self.assertEqual(data['name'], name)
        self.assertEqual(data['restartPolicy'], "Always")

        kd = container.KuberDock(name=name, action='set',
                                 restartPolicy="Never",
                                 kube_type=11)
        kd.set()
        with open(kd._data_path) as fin:
            data = json.load(fin)
        self.assertEqual(data['name'], name)
        self.assertEqual(data['restartPolicy'], "Never")
        self.assertEqual(data['kube_type'], 11)
        kd = container.KuberDock(name=name, action='set',
                                 container_port='+123:45:udp',
                                 mount_path='/sample',
                                 kubes=2,
                                 env='one:1,two:2',
                                 persistent_drive='/dev/sda1',
                                 size=1,
                                 image=imagename)
        kd.set()

        with open(kd._data_path) as fin:
            data = json.load(fin)
        self.assertEqual(len(kd.containers), 1)
        cnt = kd.containers[0]
        self.assertEqual(cnt['image'], 'c1')
        self.assertEqual(cnt['kubes'], 2)
        self.assertEqual(cnt['env'], [{'name': 'one', 'value': '1'},
                                      {'name': 'two', 'value': '2'}])
        self.assertEqual(cnt['ports'], [{'isPublic': True,
                                         'containerPort': 123,
                                         'hostPort': 45,
                                         'protocol': 'udp'}])
        self.assertEqual(len(cnt['volumeMounts']), 1)
        self.assertEqual(cnt['volumeMounts'][0]['mountPath'], '/sample')
        self.assertEqual(len(data['volumes']), 1)
        self.assertEqual(
            data['volumes'][0]['persistentDisk'],
            {'pdSize': 1, 'pdName': '/dev/sda1'}
        )

    @mock.patch.object(container.os.path, 'exists')
    @mock.patch.object(container.KuberDock, '_list_env')
    @mock.patch.object(container.KuberDock, '_load')
    @mock.patch.object(container.KubeQuery, 'get')
    @mock.patch.object(container.KubeQuery, 'post')
    def test_list_env_called(self, _post, _get, _load, _list, _os_path):
        """
        Tests if _list_env is called when --list-env is passed
        """
        _os_path.return_value = True
        _get.return_value = {"data": []}
        _get.return_value = {"status": "OK"}
        _load.return_value = True
        c = container.KuberDock(list_env=True, image='test', kubes=1)
        c._resolve_data_path('test')
        c.set()
        self.assertTrue(_list.called)

    @mock.patch.object(container.PrintOut, 'show_list')
    @mock.patch.object(container.os.path, 'exists')
    @mock.patch.object(container.KuberDock, '_load')
    @mock.patch.object(container.KubeQuery, 'get')
    @mock.patch.object(container.KubeQuery, 'post')
    def test_show_list_called_by_list_env(self, _post, _get, _load, _os_path,
                                          _po):
        """
        Tests if show_list is called when --list-env is passed
        """
        _os_path.return_value = True
        _get.return_value = {"data": []}
        _get.return_value = {"status": "OK"}
        _load.return_value = True
        c = container.KuberDock(list_env=True, image='test', kubes=1)
        c._resolve_data_path('test')
        c.containers = [{'image': 'test',
                         'env': [
                             {'name': 'ONE', 'value': 'first'},
                             {'name': 'TWO', 'value': 'second'}]}]
        c.set()
        _po.assert_called_once_with([
            {'name': 'ONE', 'value': 'first'},
            {'name': 'TWO', 'value': 'second'}])

    @mock.patch.object(container.KuberDock, '_delete_env')
    @mock.patch.object(container.KuberDock, '_list_env')
    @mock.patch.object(container.os.path, 'exists')
    @mock.patch.object(container.KuberDock, '_load')
    @mock.patch.object(container.KubeQuery, 'get')
    @mock.patch.object(container.KubeQuery, 'post')
    def test_delete_env_called(self, _post, _get, _load, _os_path, _list,
                               _delete):
        """
        Tests if _delete_env is called when --delete-env is passed
        """
        _os_path.return_value = True
        _get.return_value = {"data": []}
        _get.return_value = {"status": "OK"}
        _load.return_value = True
        c = container.KuberDock(list_env=False, image='test', kubes=1,
                                delete_env='ONE')
        c._resolve_data_path('test')
        c.set()
        self.assertFalse(_list.called)
        self.assertTrue(_delete.called)

    @mock.patch.object(container.os.path, 'exists')
    @mock.patch.object(container.KuberDock, '_load')
    @mock.patch.object(container.KubeQuery, 'get')
    @mock.patch.object(container.KubeQuery, 'post')
    def test_env_deleted(self, _post, _get, _load, _os_path):
        """
        Tests if envvar is deleted when --delete-env is passed
        """
        _os_path.return_value = True
        _get.return_value = {"data": []}
        _get.return_value = {"status": "OK"}
        _load.return_value = True
        c = container.KuberDock(delete_env='TWO,THREE', image='test', kubes=1)
        c._resolve_data_path('test')
        c.containers = [{'image': 'test',
                         'env': [
                             {'name': 'ONE', 'value': 'first'},
                             {'name': 'TWO', 'value': 'second'},
                             {'name': 'THREE', 'value': 'third'}]}]
        c.set()
        check_model = [{'name': 'ONE', 'value': 'first'}]
        self.assertEqual(check_model, c.containers[0]['env'],
                         "Only one item is expected after ENV deletion")

    @mock.patch.object(container.KubeQuery, 'get')
    @mock.patch.object(container.KubeQuery, 'post')
    def test_save(self, post_mock, get_mock):
        """Test for KuberDock.save method."""
        name = 'tmp1'
        imagename = 'c1'

        # return value for POST /api/images/new
        post_mock.return_value = {
            "data": {
                "command": [],
                "env": [],
                "image": imagename,
                "ports": [],
                "volumeMounts": [],
                "workingDir": ""
            }
        }

        # return value for GET /api/pstorage
        get_mock.return_value = {"data": []}

        # create pod, set one container parameters
        kd = container.KuberDock(name=name, action='create',
                                 restartPolicy="Always", kube_type="Standard")
        kd.create()
        kd = container.KuberDock(name=name, action='set',
                                 container_port='+123:45:udp',
                                 mount_path='/sample',
                                 kubes=2,
                                 env='one:1,two:2',
                                 persistent_drive='/dev/sda1',
                                 size=1,
                                 image=imagename)
        kd.set()

        # save pod to the server
        # response for saving of pod
        post_mock.return_value = {'status': 'OK'}
        # response for getting kube types
        get_mock.return_value = GET_KUBE_TYPES_RESPONSE
        kd = container.KuberDock(name=name)
        kd.save()
        # ensure temporary data file was deleted after saving
        self.assertFalse(os.path.exists(kd._data_path))

    @mock.patch.object(container.PrintOut, 'show_list')
    def test_list(self, showlist_mock):
        """Test for KuberDock.list method."""
        name = "test1"
        kd = container.KuberDock(name=name, action='create',
                                 restartPolicy="Always", kube_type="Standard")
        kd.create()

        kd = container.KuberDock()
        kd.list()
        showlist_mock.assert_called_once_with([{'name': name}])

    @mock.patch.object(container.PrintOut, 'show_list')
    @mock.patch.object(container.KubeQuery, 'get')
    def test_kube_types(self, get_mock, showlist_mock):
        """Test for KuberDock.kube_types method."""
        get_mock.return_value = GET_KUBE_TYPES_RESPONSE
        kd = container.KuberDock()
        kd.kube_types()
        showlist_mock.assert_called_once_with(sorted(
            [{'name': name, 'id': value}
             for name, value in GET_KUBE_TYPES_RESPONSE['data'].iteritems()],
            key=lambda x: x['id']))

    @mock.patch.object(container.PrintOut, 'show_list')
    @mock.patch.object(container.KubeQuery, 'get')
    def test_list_drives(self, get_mock, showlist_mock):
        """Test for KuberDock.list_drives method."""
        get_mock.return_value = PSTORAGE_GET_RESPONSE
        kd = container.KuberDock()
        kd.list_drives()
        showlist_mock.assert_called_once_with(get_mock.return_value['data'])

    @mock.patch.object(container.KubeQuery, 'post')
    def test_add_drive(self, post_mock):
        """Test for KuberDock.add_drive method."""

        kd = container.KuberDock(size=11, name='test12')
        kd.add_drive()
        post_mock.assert_called_once_with(
            container.PSTORAGE_PATH, {'name': 'test12', 'size': 11})

    @mock.patch.object(container.KubeQuery, 'get')
    @mock.patch.object(container.KubeQuery, 'delete')
    def test_delete_drive(self, delete_mock, get_mock):
        """Test for KuberDock.delete_drive method."""
        get_mock.return_value = PSTORAGE_GET_RESPONSE
        kd = container.KuberDock(name=PSTORAGE_GET_RESPONSE['data'][0]['name'])
        kd.delete_drive()
        get_mock.assert_called_once_with(container.PSTORAGE_PATH)
        delete_mock.assert_called_once_with(
            container.PSTORAGE_PATH +
            PSTORAGE_GET_RESPONSE['data'][0]['id'])

    @mock.patch.object(container.KubeCtl, '_set_delayed')
    @mock.patch.object(container.KubeQuery, 'put')
    @mock.patch.object(container.KubeQuery, 'get')
    def test_start(self, get_mock, put_mock, setdelayed_mock):
        """Test for KuberDock.start method."""
        get_mock.return_value = copy.deepcopy(PODAPI_GET_RESULT1)
        get_mock.return_value['data'][0]['status'] = 'stopped'
        kd = container.KuberDock(name=PODAPI_GET_RESULT1['data'][0]['name'])
        put_mock.return_value = {
            "data": {
                "status": "pending"
            },
            "status": "OK"
        }
        kd.start()
        pod = get_mock.return_value['data'][0]
        command = {'command': 'start'}
        put_mock.assert_called_once_with(
            container.PODAPI_PATH + pod['id'], command)
        setdelayed_mock.assert_called_once_with()

    @mock.patch.object(container.KubeQuery, 'put')
    @mock.patch.object(container.KubeQuery, 'get')
    def test_stop(self, get_mock, put_mock):
        """Test for KuberDock.stop method."""
        get_mock.return_value = copy.deepcopy(PODAPI_GET_RESULT1)
        get_mock.return_value['data'][0]['status'] = 'running'
        kd = container.KuberDock(name=PODAPI_GET_RESULT1['data'][0]['name'])
        put_mock.return_value = {
            "data": {
                "status": "stopped"
            },
            "status": "OK"
        }
        kd.stop()
        pod = get_mock.return_value['data'][0]
        command = {'command': 'stop'}
        put_mock.assert_called_once_with(
            container.PODAPI_PATH + pod['id'], command)

    def test_forget(self):
        """Test for KuberDock.stop method."""
        name = "test1"
        kd = container.KuberDock(name=name, action='create',
                                 restartPolicy="Always", kube_type="Standard")
        kd.create()
        self.assertTrue(os.path.exists(kd._data_path))
        kd = container.KuberDock(name=name)
        kd.forget()
        self.assertFalse(os.path.exists(kd._data_path))

    @mock.patch.object(container.PrintOut, 'show_list')
    @mock.patch.object(image.KubeQuery, 'get')
    def test_search(self, get_mock, showlist_mock):
        """Test for KuberDock.search method."""
        get_mock.return_value = {
            'data': [
                {
                    "description": "desc1",
                    "name": "name1",
                },
                {
                    "description": "desc2",
                    "name": "name2",
                },
            ],
            "num_pages": 2,
            "page": 1,
            "status": "OK"
        }
        kd = container.KuberDock(search_string='name', registry='', page=0)
        kd.search()
        get_mock.assert_called_once_with(image.IMAGES_PATH,
                                         {'url': 'http://',
                                          'searchkey': 'name', 'page': 0})
        showlist_mock.assert_called_once_with(get_mock.return_value['data'])

    @mock.patch.object(container.PrintOut, 'show')
    @mock.patch.object(image.KubeQuery, 'post')
    def test_image_info(self, post_mock, show_mock):
        """Test for KuberDock.image_info method."""
        post_mock.return_value = {
            "data": {
                "command": [],
                "env": [],
                "image": "some_image",
                "ports": [],
                "volumeMounts": [],
                "workingDir": ""
            },
            "status": "OK"
        }
        kd = container.KuberDock(image='some_image')
        kd.image_info()
        post_mock.assert_called_once_with(image.IMAGES_PATH + 'new',
                                          {'image': 'some_image'})
        show_mock.assert_called_once_with(post_mock.return_value['data'])

    def test_describe(self):
        """Test for KuberDock.describe method."""
        name = 'tmp1'
        kd = container.KuberDock(name=name, action='create')
        kd.create()
        kd = container.KuberDock(name='tmp1')
        kd.describe()
        kd = container.KuberDock(name='tmp2')
        self.assertRaises(SystemExit, kd.describe)


if __name__ == '__main__':
    unittest.main()
