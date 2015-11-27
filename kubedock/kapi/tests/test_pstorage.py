"""Tests for kapi.pstorage module."""

import unittest
from hashlib import md5

import mock

from kubedock.core import db
from kubedock.kapi import pstorage
from kubedock.settings import PD_SEPARATOR_USERID
from kubedock.testutils.testcases import DBTestCase
from kubedock.nodes.models import Node, NodeFlag, NodeFlagNames
from kubedock.billing.models import Kube


class TestPstorageFuncs(unittest.TestCase):
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

    @mock.patch.object(pstorage, 'execute_run')
    def test_get_mapped_ceph_drives_for_node(self, exec_run_mock):
        name1 = 'somevolume1'
        pool = 'somepool'
        name2 = 'somevolume2'
        device1 = '/dev/rbd0'
        device2 = '/dev/rbd1'
        exec_run_mock.return_value = {
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
        res = pstorage._get_mapped_ceph_drives_for_node()
        exec_run_mock.assert_called_once_with('rbd showmapped --format=json',
                                              jsonresult=True)
        self.assertEqual(
            res,
            {name1: {'pool': pool, 'device': device1},
             name2: {'pool': pool, 'device': device2}}
        )

        exec_run_mock.return_value = 'some unknown result'
        with self.assertRaises(pstorage.NodeCommandError):
            pstorage._get_mapped_ceph_drives_for_node()


class TestCephStorage(DBTestCase):
    """Tests for kapi.CephStorage class."""
    def setUp(self):
        super(TestCephStorage, self).setUp()
        self.user, _ = self.fixtures.user_fixtures()

    @mock.patch.object(pstorage.CephStorage, '_get_raw_drives')
    def test__get_drives(self, raw_drives_mock):
        """Test CephStorage._get_drives method."""
        raw_drives_mock.return_value = {}
        cs = pstorage.CephStorage()
        res = cs._get_drives()
        self.assertEqual(res, [])
        raw_drives_mock.assert_called_once_with(check_inuse=True)

        name1 = 'one'
        name2 = 'two'
        size1 = 2 * 1024 * 1024 * 1024  # 2 GB
        size2 = 3 * 1024 * 1024 * 1024  # 3 GB
        node = '192.168.1.13'
        user = self.user
        raw_drives_mock.return_value = {
            name1 + PD_SEPARATOR_USERID + str(user.id): {
               'size': size1,
               'in_use': False
            },
            name2 + PD_SEPARATOR_USERID + str(user.id): {
                'size': size2,
                'in_use': True,
                'device': '/dev/rbd0',
                'nodes': [node]
            },
            'someunknowndrive': {
                'size': size1,
                'in_use': False
            }
        }
        res = cs._get_drives()
        self.assertEqual(len(res), 2)
        self.assertEqual({item['owner'] for item in res}, {user.username})
        drive1 = [item for item in res if not item['in_use']][0]
        drive2 = [item for item in res if item['in_use']][0]
        self.assertEqual(drive1['name'], name1)
        self.assertEqual(drive1['drive_name'],
                         name1 + PD_SEPARATOR_USERID + str(user.id))
        self.assertEqual(
            drive1['id'],
            md5(name1 + PD_SEPARATOR_USERID + str(user.id)).hexdigest()
        )
        self.assertEqual(drive1['size'], size1 / (1024 * 1024 * 1024))
        self.assertEqual(drive2['name'], name2)
        self.assertEqual(drive2['node'], node)
        self.assertEqual(drive2['device'], '/dev/rbd0')

    @mock.patch.object(pstorage, 'get_all_ceph_drives')
    @mock.patch.object(pstorage, 'get_mapped_ceph_drives')
    def test_get_raw_drives(self, get_mapped_mock, get_all_mock):
        res = pstorage.CephStorage()._get_raw_drives()
        # there is no any nodes, so we haven't any ceph drives
        self.assertEqual(res, {})
        # add a node
        node = Node(
            id=1, ip='192.168.1.12', hostname='somehost',
            kube_id=Kube.get_default_kube_type()
        )
        db.session.add(node)
        db.session.commit()

        res = pstorage.CephStorage()._get_raw_drives()
        # there is still no nodes with ceph flag, so we haven't any ceph drives
        self.assertEqual(res, {})

        # add ceph flag to the node
        NodeFlag.save_flag(1, NodeFlagNames.CEPH_INSTALLED, 'true')
        name1 = 'a1'
        name2 = 'a2'
        size1 = 222
        size2 = 333
        all_drives = {
            name1: {'size': size1, 'in_use': False},
            name2: {'size': size2, 'in_use': False},
        }
        get_all_mock.return_value = all_drives
        # select drives without checking usage
        res = pstorage.CephStorage()._get_raw_drives(check_inuse=False)
        self.assertEqual(res, all_drives)

        mapped_drives = {
            node.ip: {
                name1: {'pool': 'somepool', 'device': '/dev/rbd1'},
                'unknown': {'pool': 'somepool', 'device': '/dev/rbd14'}
            }
        }
        get_mapped_mock.return_value = mapped_drives
        # select drives with usage check
        res = pstorage.CephStorage()._get_raw_drives()
        self.assertEqual(
            res,
            {
                name1: {'size': size1, 'in_use': True, 'pool': 'somepool',
                        'device': '/dev/rbd1', 'nodes': [node.ip]},
                name2: {'size': size2, 'in_use': False}
            }
        )


if __name__ == '__main__':
    unittest.main()
