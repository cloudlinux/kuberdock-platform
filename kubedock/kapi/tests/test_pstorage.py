"""Tests for kapi.pstorage module."""

import unittest
import json
import uuid

import mock

from kubedock.core import db
from kubedock.kapi import pstorage
from kubedock.settings import PD_NS_SEPARATOR
from kubedock.testutils.testcases import DBTestCase, FlaskTestCase
from kubedock.pods.models import PersistentDisk, PersistentDiskStatuses, Pod
from kubedock.billing.models import Kube
from kubedock.nodes.models import Node

from kubedock.testutils import create_app


class TestCase(FlaskTestCase):
    def create_app(self):
        return create_app(self)


class TestPstorageFuncs(DBTestCase):
    """Tests for kapi.pstorage independent functions."""

    @mock.patch.object(pstorage, 'run_remote_command')
    def test_get_all_ceph_drives(self, run_mock):
        image1 = 'q1'
        image2 = 'q2'
        size1 = 121212
        size2 = 232323
        node = 'somehost.com'
        run_mock.return_value = [
            {'image': image1, 'size': size1, 'format': 1},
            {'image': image2, 'size': size2, 'format': 2},
        ]
        res = pstorage.get_all_ceph_drives(node)
        self.assertEqual(
            res,
            {
                image1: {'size': size1, 'in_use': False},
                image2: {'size': size2, 'in_use': False},
            })
        run_mock.assert_called_once_with(node, 'rbd list --long --format=json',
                                         jsonresult=True)
        run_mock.return_value = 'invalid format'
        with self.assertRaises(pstorage.NodeCommandError):
            pstorage.get_all_ceph_drives(node)

    @mock.patch.object(pstorage, 'run_remote_command')
    def test_get_mapped_ceph_devices_for_node(self, run_remote_command):
        name1 = 'somevolume1'
        pool = 'somepool'
        name2 = 'somevolume2'
        device1 = '/dev/rbd0'
        device2 = '/dev/rbd1'
        node = '123.456.789.123'
        run_remote_command.return_value = {
            '0': {
                'name': name1,
                'pool': pool,
                'device': device1
            },
            '1': {
                'name': name2,
                'pool': pool,
                'device': device2
            },
        }
        res = pstorage._get_mapped_ceph_devices_for_node(node)
        run_remote_command.assert_called_once_with(
            node,
            'rbd showmapped --format=json',
            jsonresult=True
        )
        self.assertEqual(
            res,
            {device1: {'pool': pool, 'name': name1},
             device2: {'pool': pool, 'name': name2}}
        )

        run_remote_command.return_value = 'some unknown result'
        with self.assertRaises(pstorage.NodeCommandError):
            pstorage._get_mapped_ceph_devices_for_node(node)

    @mock.patch.object(pstorage, 'get_storage_class')
    def test_delete_persistent_drives(self, getsc_mock):
        """Test for pstorage.delete_persistent_drives function"""
        user, _ = self.fixtures.user_fixtures()
        pd = PersistentDisk(
            name='q', owner_id=user.id, size=1
        )
        db.session.add(pd)
        db.session.commit()

        ps_delete_by_id_mock = getsc_mock.return_value.return_value.delete_by_id

        ps_delete_by_id_mock.return_value = 1

        pstorage.delete_persistent_drives([pd.id])
        pds = db.session.query(PersistentDisk).all()
        self.assertEqual(len(pds), 1)
        self.assertEqual(pds[0].state, pd.state)

        ps_delete_by_id_mock.return_value = 0
        pstorage.delete_persistent_drives([pd.id], mark_only=True)
        pds = db.session.query(PersistentDisk).all()
        self.assertEqual(len(pds), 1)
        self.assertEqual(pds[0].state, PersistentDiskStatuses.DELETED)

        ps_delete_by_id_mock.return_value = 0
        pstorage.delete_persistent_drives([pd.id])
        pds = db.session.query(PersistentDisk).all()
        self.assertEqual(pds, [])

    @mock.patch.object(pstorage, 'update_pods_volumes')
    @mock.patch.object(pstorage, 'delete_persistent_drives_task')
    def test_delete_drive_by_id(self, delete_pd_mock, update_pod_mock):
        """Test pstorage.delete_drive_by_id function."""
        user, _ = self.fixtures.user_fixtures()
        pd = PersistentDisk(
            name='q', owner_id=user.id, size=1
        )
        db.session.add(pd)
        db.session.commit()
        old_id = pd.id
        old_drive_name = pd.drive_name
        old_name = pd.name

        pstorage.delete_drive_by_id(pd.id)

        new_pd = db.session.query(PersistentDisk).filter(
            PersistentDisk.state == PersistentDiskStatuses.DELETED
        ).first()
        self.assertIsNotNone(new_pd)
        update_pod_mock.assert_called_once_with(new_pd)
        delete_pd_mock.delay.assert_called_once_with([old_id], mark_only=False)

        updated_pd = db.session.query(PersistentDisk).filter(
            PersistentDisk.id == old_id
        ).first()
        self.assertIsNotNone(updated_pd)
        self.assertNotEqual(updated_pd.name, old_name)
        self.assertEqual(updated_pd.state, PersistentDiskStatuses.TODELETE)
        self.assertEqual(updated_pd.drive_name, old_drive_name)
        self.assertEqual(updated_pd.drive_name + '_1', new_pd.drive_name)
        self.assertEqual(new_pd.name, old_name)
        self.assertEqual(new_pd.owner_id, updated_pd.owner_id)

    def test_update_pods_volumes(self):
        """Test pstorage.update_pods_volumes function"""
        user, _ = self.fixtures.user_fixtures()
        old_drive_name = 'qq11'
        new_drive_name = 'ww22'
        pdname = 'qwerty1243'
        pod_id = str(uuid.uuid4())
        storage_prefix = pstorage.NODE_LOCAL_STORAGE_PREFIX
        pod = Pod(
            id=pod_id, name='somename', owner_id=user.id,
            kube_id=Kube.get_default_kube_type(),
            config=json.dumps({
                "volumes": [
                    {
                        "hostPath": {
                            "path": storage_prefix + '/' + old_drive_name
                        },
                        "name": "var-qqq7824431125",
                        "annotation": {
                            "localStorage": {
                                "path": storage_prefix + '/' + old_drive_name,
                                "size": 1
                            }
                        }
                    }
                ],
                "volumes_public": [
                    {
                        "persistentDisk": {"pdSize": 1, "pdName": pdname},
                        "name": "var-qqq7824431125"
                    }
                ]

            })
        )
        db.session.add(pod)
        new_pd = PersistentDisk(
            name=pdname, drive_name=new_drive_name, owner_id=user.id, size=1
        )
        db.session.add(new_pd)
        db.session.commit()
        pstorage.update_pods_volumes(new_pd)
        pods = db.session.query(Pod).all()
        self.assertTrue(len(pods), 1)
        new_pod = pods[0]
        config = new_pod.get_dbconfig()
        self.assertEqual(len(config['volumes']), len(config['volumes_public']))
        self.assertEqual(len(config['volumes']), 1)
        new_drive_path = storage_prefix + '/' + new_drive_name
        self.assertEqual(
            config['volumes'][0]['hostPath']['path'], new_drive_path
        )
        self.assertEqual(
            config['volumes'][0]['annotation']['localStorage']['path'],
            new_drive_path
        )
        self.assertEqual(
            config['volumes_public'][0]['persistentDisk']['pdName'], pdname
        )


class TestLocalStorage(DBTestCase):
    """Tests for kapi.LocalStorage class."""
    def setUp(self):
        super(TestLocalStorage, self).setUp()
        self.user, _ = self.fixtures.user_fixtures()

    def test_check_node_is_locked(self):
        """Test LocalStorage.check_node_is_locked method."""
        kube_type = Kube.get_default_kube_type()
        node1 = Node(ip='192.168.1.2', hostname='host1', kube_id=kube_type)
        node2 = Node(ip='192.168.1.3', hostname='host2', kube_id=kube_type)
        db.session.add_all([node1, node2])
        db.session.commit()
        user, _ = self.fixtures.user_fixtures()
        pd = PersistentDisk(
            name='q', owner_id=user.id, size=1
        )
        db.session.add(pd)
        db.session.commit()

        flag, reason = pstorage.LocalStorage.check_node_is_locked(node1.id)
        self.assertFalse(flag)
        self.assertIsNone(reason)
        flag, reason = pstorage.LocalStorage.check_node_is_locked(node2.id)
        self.assertFalse(flag)

        pd = PersistentDisk(
            name='w', owner_id=user.id, size=1, node_id=node1.id
        )
        db.session.add(pd)
        db.session.commit()

        flag, reason = pstorage.LocalStorage.check_node_is_locked(node1.id)
        self.assertTrue(flag)
        self.assertIsNotNone(reason)

    def test_drive_can_be_deleted(self):
        """Test LocalStorage.drive_can_be_deleted method."""
        user, _ = self.fixtures.user_fixtures()
        pd = PersistentDisk(
            name='q', owner_id=user.id, size=1
        )
        db.session.add(pd)
        db.session.commit()

        flag, reason = pstorage.LocalStorage.drive_can_be_deleted(pd.id)
        self.assertTrue(flag)
        self.assertIsNone(reason)

        pod_id = str(uuid.uuid4())
        pdname = 'somename1'
        pod = Pod(
            id=pod_id, name='somename', owner_id=user.id,
            kube_id=Kube.get_default_kube_type(),
            config=json.dumps({
                "volumes_public": [
                    {
                        "persistentDisk": {"pdSize": 1, "pdName": pdname},
                    }
                ]

            })
        )
        db.session.add(pod)
        db.session.commit()

        flag, reason = pstorage.LocalStorage.drive_can_be_deleted(pd.id)
        self.assertTrue(flag)
        self.assertIsNone(reason)

        pd = PersistentDisk(
            name=pdname, owner_id=user.id, size=1
        )
        db.session.add(pd)
        db.session.commit()
        flag, reason = pstorage.LocalStorage.drive_can_be_deleted(pd.id)
        self.assertFalse(flag)
        self.assertIsNotNone(reason)

        # delete pod, drive must became deletable
        pod.status = 'deleted'
        db.session.query(Pod).update(
            {Pod.status: 'deleted'}, synchronize_session=False
        )
        db.session.commit()
        flag, reason = pstorage.LocalStorage.drive_can_be_deleted(pd.id)
        self.assertTrue(flag)
        self.assertIsNone(reason)


class TestCephStorage(DBTestCase):
    """Tests for kapi.CephStorage class."""
    def setUp(self):
        super(TestCephStorage, self).setUp()
        self.user, _ = self.fixtures.user_fixtures()


class TestCephUtils(TestCase):
    """Tests for CEPH not db-aware utils."""
    
    @mock.patch.object(pstorage, 'run_remote_command')
    @mock.patch.object(pstorage.ConnectionPool, 'get_connection')
    @mock.patch.object(pstorage, '_get_mapped_ceph_devices_for_node')
    def test_unmap_temporary_mapped_ceph_drives(
            self, get_mapped_mock, get_conn_mock, run_cmd_mock):
        """Test pstorage.unmap_temporary_mapped_ceph_drives function"""
        redis_mock = get_conn_mock.return_value
        redis_mock.hkeys.return_value = []
        pstorage.unmap_temporary_mapped_ceph_drives()
        redis_mock.hkeys.assert_called_once_with(
            pstorage.REDIS_TEMP_MAPPED_HASH)
        get_mapped_mock.assert_not_called()
        run_cmd_mock.assert_not_called()

        drive1 = 'd1'
        node1 = 'n1'
        dev1 = '/dev/rbd11'
        pool = 'somepool'
        drive_data = {'node': node1, 'dev': dev1}
        fulldrive = PD_NS_SEPARATOR.join([pool, drive1])
        redis_mock.hkeys.return_value = [fulldrive]
        redis_mock.hget.return_value = json.dumps(drive_data)
        get_mapped_mock.return_value = {}
        pstorage.unmap_temporary_mapped_ceph_drives()
        redis_mock.hget.assert_called_once_with(
            pstorage.REDIS_TEMP_MAPPED_HASH, fulldrive)
        get_mapped_mock.assert_called_once_with(node1)
        run_cmd_mock.assert_not_called()
        redis_mock.hdel.assert_called_once_with(
            pstorage.REDIS_TEMP_MAPPED_HASH, fulldrive)

        get_mapped_mock.return_value = {
            'unknown_device': {'name': drive1, 'pool': pool}
        }
        pstorage.unmap_temporary_mapped_ceph_drives()
        run_cmd_mock.assert_not_called()
        redis_mock.hdel.assert_called_with(
            pstorage.REDIS_TEMP_MAPPED_HASH, fulldrive)

        get_mapped_mock.return_value = {
            dev1: {'name': drive1, 'pool': pool}
        }
        pstorage.unmap_temporary_mapped_ceph_drives()
        run_cmd_mock.assert_called_once_with(node1, 'rbd unmap ' + dev1)
        redis_mock.hdel.assert_called_with(
            pstorage.REDIS_TEMP_MAPPED_HASH, fulldrive)


if __name__ == '__main__':
    unittest.main()
