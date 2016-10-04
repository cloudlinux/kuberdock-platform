import datetime
import json
import os
import unittest
from tempfile import NamedTemporaryFile

import mock
import pytz

from .. import licensing


class TestLicenseValidation(unittest.TestCase):
    def setUp(self):
        self.license = {
            u'installationID': u'123456789',
            u'updated': u'2016-04-28T11:49:25.594006+00:00',
            u'data': {
                u'license': {
                    u'status': u'ok', u'pods': 0,
                    u'sign': '',  # Signature is omitted for now
                    u'expiration': u'-999999999-01-01T00:00:00+18:00',
                    u'memory': 0, u'cores': -1, u'type': u'none',
                    u'containers': 0
                }
            },
            u'auth_key': u'a6182baebfff481aa450eae9cd718bfc'
        }
        self._move_license_expiration(1)

    def test_is_valid_correctly_validates_correct_license(self):
        with mocked_license(self.license):
            self.assertTrue(licensing.is_valid())

    def test_license_is_not_valid_if_expired_more_than_1_days_ago(self):
        self.license[u'data'][u'license'][u'status'] = 'expired'
        self._move_license_expiration(-4)
        with mocked_license(self.license):
            self.assertFalse(licensing.is_valid())

    def test_new_but_incorrect_license_is_valid(self):
        self.license[u'data'][u'license'][u'status'] = None
        with mocked_license(self.license):
            self.assertTrue(licensing.is_valid())

    def test_timestamp_check_passes_if_expiration_date_is_in_a_future(self):
        self._move_license_expiration(99)
        self.assertTrue(licensing.is_timestamp_ok(self.license))

    def test_timestamp_check_fails_if_expiration_date_is_in_a_past(self):
        self._move_license_expiration(-99)
        self.assertFalse(licensing.is_timestamp_ok(self.license))

    def _move_license_expiration(self, days_delta):
        new_exp = (datetime.datetime.utcnow() +
                   datetime.timedelta(days=days_delta))
        self.license[u'data'][u'license'][u'expiration'] = new_exp.replace(
            tzinfo=pytz.UTC).isoformat()


class mocked_license(object):
    def __init__(self, lic):
        self.lic, self.lic_path, self.patcher = lic, None, None

    def clean_up(self):
        if self.lic_path:
            os.unlink(self.lic_path)
        if self.patcher:
            self.patcher.stop()

    def __enter__(self):
        with NamedTemporaryFile('w', delete=False) as f:
            f.write(json.dumps(self.lic))
            self.lic_path = f.name
            self.patcher = mock.patch.object(licensing, 'LICENSE_PATH', f.name)
        self.patcher.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.clean_up()
