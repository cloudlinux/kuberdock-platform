"""Tests for kapi.pd_utils"""
import unittest
from collections import namedtuple

import mock

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
        uid = 776
        res = pd_utils.compose_pdname(name, uid)
        self.assertEqual(res, name + pd_utils.PD_SEPARATOR_USERID + str(uid))

        test_user_cls = namedtuple('test_user_cls', 'id')
        uid = 111
        uobject = test_user_cls(uid)
        res = pd_utils.compose_pdname(name, uobject)
        self.assertEqual(res, name + pd_utils.PD_SEPARATOR_USERID + str(uid))

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
