
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
