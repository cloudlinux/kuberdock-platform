"""Tests for kapi.pd_utils"""
import unittest
from collections import namedtuple

import mock

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
