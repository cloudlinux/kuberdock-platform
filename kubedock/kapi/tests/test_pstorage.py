"""Tests for kapi.pstorage module."""

import unittest
from hashlib import md5
import json

import mock

from kubedock.core import db
from kubedock.kapi import pstorage
from kubedock.settings import PD_SEPARATOR_USERID, PD_NS_SEPARATOR
from kubedock.testutils.testcases import DBTestCase, FlaskTestCase
from kubedock.nodes.models import Node, NodeFlag, NodeFlagNames
from kubedock.billing.models import Kube
from kubedock.pods.models import PersistentDisk, PersistentDiskStatuses

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
