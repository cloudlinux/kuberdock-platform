"""Tests for kapi.pd_utils"""
import unittest
from collections import namedtuple

import mock

from kubedock import settings
from kubedock.kapi import pd_utils


class TestPdUtils(unittest.TestCase):
    """Tests for pd_utils functions."""

    def test_parse_pd_name(self):
        """Test pd_utils.parse_pd_name function."""
        res = pd_utils.parse_pd_name('')
        self.assertIsNone(res)

        res = pd_utils.parse_pd_name('qwerty')
        self.assertIsNone(res)

        name = 'adsfg1324'
        uid = 2233
        drive_name = name + pd_utils.PD_SEPARATOR_USERID + str(uid)
        res = pd_utils.parse_pd_name(drive_name)
        self.assertEqual(res.drive, name)
        self.assertEqual(res.uid, uid)
        self.assertIsNone(res.uname)

        name = 'zxcvb2323'
        uname = 'qaz'
        drive_name = name + pd_utils.PD_SEPARATOR_USERNAME + uname
        res = pd_utils.parse_pd_name(drive_name)
        self.assertEqual(res.drive, name)
        self.assertIsNone(res.uid)
        self.assertEqual(res.uname, uname)

    @mock.patch.object(pd_utils, 'User')
    def test_get_drive_and_user(self, user_mock):
        """Test pd_utils.parse_pd_name function."""
        name = 'adsfg1324'
        uid = 2233
        drive_name = name + pd_utils.PD_SEPARATOR_USERID + str(uid)
        test_user_obj = 'trtrtrt'
        user_mock.query.filter.return_value.first.return_value = test_user_obj
        res = pd_utils.get_drive_and_user(drive_name)
        self.assertEqual(res[0], name)
        self.assertEqual(res[1], test_user_obj)
        user_mock.query.filter.assert_called_once_with(pd_utils.User.id == uid)

        name = 'zxcvb2323'
        uname = 'qaz'
        drive_name = name + pd_utils.PD_SEPARATOR_USERNAME + uname
        res = pd_utils.get_drive_and_user(drive_name)
        self.assertEqual(res[0], name)
        self.assertEqual(res[1], test_user_obj)
        user_mock.query.filter.assert_called_with(
            pd_utils.User.username == uname)

        res = pd_utils.get_drive_and_user('')
        self.assertEqual(res, (None, None))

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

        expected1 = 'gfgfgf__sep_uid__776'
        expected2 = 'gfgfgf__sep_uid__111'
        res1 = pd_utils.compose_pdname(name, uid1)
        res2 = pd_utils.compose_pdname(name, uobject)

        self.assertEqual(expected1, res1)
        self.assertEqual(expected2, res2)

        # local with set namespace. Namespace must be omit
        settings.PD_NAMESPACE = 'asd'
        reload(pd_utils)

        expected1 = 'gfgfgf__sep_uid__776'
        expected2 = 'gfgfgf__sep_uid__111'
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
