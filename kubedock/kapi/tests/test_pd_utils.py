
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

"""Tests for kapi.pd_utils"""
import unittest
from collections import namedtuple

from kubedock import settings
from kubedock.kapi import pd_utils


class TestPdUtils(unittest.TestCase):
    """Tests for pd_utils functions."""

    def test_compose_pd_name(self):
        """Test pd_utils.compose_pdname function."""
        name = 'gfgfgf'
        uid1 = 776

        test_user_cls = namedtuple('test_user_cls', 'id')
        uid2 = 111
        uobject = test_user_cls(uid2)

        # patch settings
        settings.PD_SEPARATOR_USERID = '__sep_uid__'
        settings.PD_NS_SEPARATOR = '__sep_ns__'

        # local empty namespace
        settings.CEPH = False
        settings.AWS = False
        settings.PD_NAMESPACE = ''
        reload(pd_utils)

        expected1 = '{}/{}'.format(uid1, name)
        expected2 = '{}/{}'.format(uid2, name)
        res1 = pd_utils.compose_pdname(name, uid1)
        res2 = pd_utils.compose_pdname(name, uobject)

        self.assertEqual(expected1, res1)
        self.assertEqual(expected2, res2)

        # local with set namespace. Namespace must be omit
        settings.PD_NAMESPACE = 'asd'
        reload(pd_utils)

        expected1 = '{}/{}'.format(uid1, name)
        expected2 = '{}/{}'.format(uid2, name)
        res1 = pd_utils.compose_pdname(name, uid1)
        res2 = pd_utils.compose_pdname(name, uobject)

        self.assertEqual(expected1, res1)
        self.assertEqual(expected2, res2)

        # ceph or aws with empty namespace
        settings.CEPH = True
        settings.PD_NAMESPACE = ''
        reload(pd_utils)

        expected1 = 'gfgfgf__sep_uid__776'
        expected2 = 'gfgfgf__sep_uid__111'
        res1 = pd_utils.compose_pdname(name, uid1)
        res2 = pd_utils.compose_pdname(name, uobject)

        self.assertEqual(expected1, res1)
        self.assertEqual(expected2, res2)

        # ceph or aws with set namespace
        settings.CEPH = True
        settings.PD_NAMESPACE = 'asd'
        reload(pd_utils)

        expected1 = 'asd__sep_ns__gfgfgf__sep_uid__776'
        expected2 = 'asd__sep_ns__gfgfgf__sep_uid__111'
        res1 = pd_utils.compose_pdname(name, uid1)
        res2 = pd_utils.compose_pdname(name, uobject)

        self.assertEqual(expected1, res1)
        self.assertEqual(expected2, res2)

        # revert settings and pd_utils
        reload(settings)
        reload(pd_utils)

    def test_compose_pd_name_legacy(self):
        """Test pd_utils.compose_pdname function."""
        name = 'gfgfgf'
        uname = 'vcvcvcv'
        test_user_cls = namedtuple('test_user_cls', 'username')
        uobject = test_user_cls(uname)
        res = pd_utils.compose_pdname_legacy(name, uobject)
        self.assertEqual(res, name + pd_utils.PD_SEPARATOR_USERNAME + uname)


if __name__ == '__main__':
    unittest.main()
