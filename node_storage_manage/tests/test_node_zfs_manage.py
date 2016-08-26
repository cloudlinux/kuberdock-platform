"""Unittests for node_storage_manage.node_zfs_manage"""

import unittest
import mock

from .. import node_zfs_manage


class TestZfsManageFuncs(unittest.TestCase):

    @mock.patch.object(node_zfs_manage.os, 'path')
    @mock.patch.object(node_zfs_manage, 'get_subprocess_result')
    def test_get_device_list(self, subp_result_mock, path_mock):
        subp_result_mock.return_value = (
            0,
            "  pool: kdstorage00\n"
            " state: ONLINE\n"
            "  scan: none requested\n"
            "config:\n"
            "\n"
            "	NAME        STATE     READ WRITE CKSUM\n"
            "	kdstorage00  ONLINE       0     0     0\n"
            "	  sdc       ONLINE       0     0     0\n"
            "	  sdd       ONLINE       0     0     0\n"
            "\n"
            "errors: No known data errors\n")
        path_mock.exists.return_value = True
        res = node_zfs_manage.get_device_list('kdstorage00')
        self.assertEqual(res, ['/dev/sdc', '/dev/sdd'])

        path_mock.exists.return_value = False
        res = node_zfs_manage.get_device_list('kdstorage00')
        self.assertEqual(res, [])

        path_mock.exists.return_value = True
        res = node_zfs_manage.get_device_list('qwerty')
        self.assertEqual(res, [])


if __name__ == '__main__':
    unittest.main()
