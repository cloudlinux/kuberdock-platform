# -*- coding: utf-8 -*-
import sys
import unittest
import mock
import random
import string

sys.modules['flask'] = mock.Mock()
sys.modules['sqlalchemy'] = mock.Mock()
sys.modules['kubedock.api'] = api_mock = mock.Mock()
sys.modules['kubedock.utils'] = mock.Mock()
sys.modules['kubedock.billing'] = mock.Mock()
sys.modules['kubedock.users.models'] = mock.Mock()

# TODO: Integration tests for _validate_unique_case_insensitive

class APIError(Exception):
    pass
api_mock.APIError = APIError

from kubedock.users.models import User
from ..validation import V, UserValidator


class TestV(unittest.TestCase):
    def test_validate_internal_only(self):
        """Allow field only if user is kuberdock-internal"""
        data = {'some_field': 3}
        schema = {'some_field': {'type': 'integer', 'internal_only': True}}
        errors = {'some_field': 'not allowed'}

        validator = V(user='test_user')
        self.assertFalse(validator.validate(data, schema))
        self.assertEqual(validator.errors, errors)
        validator = V()
        self.assertFalse(validator.validate(data, schema))
        self.assertEqual(validator.errors, errors)
        validator = V(user='kuberdock-internal')
        self.assertTrue(validator.validate(data, schema))
        self.assertEqual(validator.errors, {})


class TestUserCreateValidation(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(UserValidator, '_validate_unique_case_insensitive')
        self.addCleanup(patcher.stop)
        self.unique_validation_mock = patcher.start()

        self.validator = UserValidator().validate_user_create

    @staticmethod
    def randstr(length=10, symbols=string.ascii_letters):
        return ''.join(random.choice(symbols) for i in range(10))

    @classmethod
    def _template(cls, **fields):
        """ Generate unique valid user """
        temp = {
            'username': cls.randstr(20),
            'email': cls.randstr(10) + '@test.test',
            'password': 'a-3',
            'rolename': 'User',
            'package': 'Standard Package',
            'active': True,
        }
        temp.update(fields)
        return temp

    def assertValidList(self, validator, template, field, valid_values):
        for value in valid_values:
            data = template(**{field: value})
            try:
                validator(data)
            except APIError as e:
                self.fail('Test "{0}" is a valid {1}: {2}'
                          .format(value, field, e.message))

    def assertInvalidList(self, validator, template, field, invalid_values):
        for value in invalid_values:
            data = template(**{field: value})
            msg = 'Test "{0}" is a valid {1}'.format(value, field)
            with self.assertRaises(APIError, msg=msg):
                validator(data)

    def assertRequired(self, validator, template, field):
        data = template()
        data.pop(field, None)
        with self.assertRaises(APIError, msg='Test "{0}" is required'.format(field)):
            validator(data)

    def test_username(self):
        """
        Required field
        Unique value
        Maximum length is 25 symbols
        Contain letters of Latin alphabet only
        """
        valid_usernames = [
            'a',
            'w-n_c-m12345',
            'a' * 25,
            'test@example.com'
        ]

        invalid_usernames = [
            '',
            '-wncm',
            'wncm_',
            'a' * 26,
            'Joe Smith',
            '>aaaa<',
        ]

        self.assertRequired(self.validator, self._template, 'username')
        self.assertValidList(self.validator, self._template, 'username',
                             valid_usernames)
        self.assertInvalidList(self.validator, self._template, 'username',
                               invalid_usernames)

        data = self._template(username='test-user-f3j4f')
        self.validator(data)
        self.unique_validation_mock.assert_has_calls([
            mock.call(User.username, 'username', data['username'])])

    def test_email(self):
        """
        Required field
        Maximum length is 50 symbols
        """

        valid_emails = [
            'email@domain.com',
            'firstname.lastname@domain.com',
            'email@subdomain.domain.com',
            'firstname+lastname@domain.com',
            'email@[123.123.123.123]',
            '"email"@domain.com',
            '1234567890@domain.com',
            'email@domain-one.com',
            '_______@domain.com',
            'email@domain.name',
            'email@domain.co.jp',
            'firstname-lastname@domain.com',
        ]
        invalid_emails = [
            'Plainaddress',
            '#@%^%#$@#$@#.com',
            '@domain.com',
            'Joe Smith <email@domain.com>',
            'email.domain.com',
            'email@domain@domain.com',
            '.email@domain.com',
            'email.@domain.com',
            'email..email@domain.com',
            'あいうえお@domain.com',
            'email@domain.com (Joe Smith)',
            'email@domain',
            'email@-domain.com',
            'email@domain.web',
            'email@111.222.333.44444',
            'email@domain..com',
        ]

        self.assertRequired(self.validator, self._template, 'email')
        self.assertValidList(self.validator, self._template, 'email', valid_emails)
        self.assertInvalidList(self.validator, self._template, 'email', invalid_emails)

        data = self._template(email='wpfwj344d@test.test')
        self.validator(data)
        self.unique_validation_mock.assert_has_calls([
            mock.call(User.email, 'email', data['email'])])

    def test_password(self):
        """
        Required field
        Maximum length is 25 characters
        Contains alphanumerics and special symbols
        Case sensitive
        """

        valid_passwords = [
            'a-3',
            '12-34' + 'a' * 20,
            """~!@#$%^&*()_+\]'/.;<,|}"?""",
        ]
        invalid_passwords = [
            '',
            '12-34' + 'a' * 21,
        ]

        self.assertRequired(self.validator, self._template, 'password')
        self.assertValidList(self.validator, self._template, 'password',
                             valid_passwords)
        self.assertInvalidList(self.validator, self._template, 'password',
                               invalid_passwords)

    def test_name(self):
        """
        Maximum length is 25 characters
        Contain letters of Latin alphabet only
        """

        valid_names = [
            'a',
            'wncm',
            'John',
            'a' * 25,
            '',
        ]

        invalid_names = [
            'a' * 26,
            'Joe Smith',
            'Joe-Smith',
        ]

        for field in ('first_name', 'last_name', 'middle_initials'):
            self.assertValidList(self.validator, self._template, field, valid_names)
            self.assertInvalidList(self.validator, self._template, field, invalid_names)


class TestUserEditValidation(TestUserCreateValidation):
    _template = dict  # empty: partial update allowed

    def setUp(self):
        super(TestUserEditValidation, self).setUp()

        self.validator = UserValidator(id=1).validate_user_update

    def assertRequired(self, *args, **kwargs):  # partial update allowed
        pass

if __name__ == '__main__':
    test = unittest.main()
