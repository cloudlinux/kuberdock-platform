import unittest
from kubedock.testutils.testcases import APITestCase
from kubedock.testutils import fixtures

from uuid import uuid4
from time import sleep
from ipaddress import ip_address

from kubedock.validation import V
from kubedock.usage.models import IpState, PersistentDiskState
from kubedock.users.models import User
from kubedock.pods.models import Pod

usage_per_user_schema = {
    'pods_usage': {
        'type': list, 'required': True,
        'schema': {
            'type': dict, 'required': True,
            'schema': {
                'id': {'type': str, 'required': True, 'empty': False},
                'kube_id': {'type': int, 'required': True},
                'kubes': {'type': int, 'required': True},
                'name': {'type': str, 'required': True, 'empty': False},
                'time': {
                    'type': dict, 'required': True,
                    'keyschema': {
                        'type': list, 'required': True,
                        'schema': {
                            'type': dict, 'required': True,
                            'schema': {
                                'start': {'type': int, 'required': True},
                                'end': {'type': int, 'required': True},
                                'kubes': {'type': int, 'required': True}}}}}}}},
    'pd_usage': {
        'type': list, 'required': True,
        'schema': {
            'type': dict, 'required': True,
            'schema': {
                'start': {'type': int, 'required': True},
                'end': {'type': int, 'required': True},
                'pd_name': {'type': str, 'required': True, 'empty': False},
                'size': {'type': int, 'required': True}}}},
    'ip_usage': {
        'type': list, 'required': True,
        'schema': {
            'type': dict, 'required': True,
            'schema': {
                'start': {'type': int, 'required': True},
                'end': {'type': int, 'required': True},
                'ip_address': {'type': str, 'required': True, 'empty': False},
                'pod_id': {'type': str, 'required': True, 'empty': False}}}}}


class UsageResponseValidator(V):
    """Validator for testing usage api"""
    get_schema = {
        'status': {'type': str, 'required': True, 'allowed': ['OK', 'error']},
        'data': {'type': dict, 'required': True, 'schema': usage_per_user_schema}
    }
    get_list_schema = {
        'status': {'type': str, 'required': True, 'allowed': ['OK', 'error']},
        'data': {'type': dict, 'required': True,
                 'keyschema': {'type': dict, 'required': True,
                               'schema': usage_per_user_schema}}}

    def validate_get(self, data):
        return self.validate(data, self.get_schema)

    def validate_get_list(self, data):
        return self.validate(data, self.get_list_schema)


class UsageTestCase(APITestCase):
    """Tests for /api/usage endpoint"""
    url = '/usage'

    def setUp(self):
        super(UsageTestCase, self).setUp()
        user, user_password = fixtures.user_fixtures()
        self.admin, admin_password = fixtures.admin_fixtures()
        self.userauth = (user.username, user_password)
        self.adminauth = (self.admin.username, admin_password)

        # create test data
        another_user = User(username='another_user', password='p-0',
                            email='another_user@test.test').save()
        config = '{"containers":[{"kubes":1}]}'
        self.ips = [(Pod(id=str(uuid4()), owner_id=user.id, name='pod1',
                         kube_id=0, config=config).save(), u'192.168.43.132'),
                    (Pod(id=str(uuid4()), owner_id=user.id, name='pod2',
                         kube_id=0, config=config).save(), u'192.168.43.133'),
                    (Pod(id=str(uuid4()), owner_id=another_user.id, name='pod3',
                         kube_id=0, config=config).save(), u'192.168.43.134')]
        for pod, ip in self.ips:
            IpState.start(pod.id, int(ip_address(ip)))
        self.pds = [(user.id, 'first_disk', 2), (user.id, 'second_disk', 16),
                    (another_user.id, 'third_disk', 3)]
        for user_id, name, size in self.pds:
            PersistentDiskState.start(user_id, name, size)
        sleep(1)
        IpState.end(self.ips[0][0].id, int(ip_address(self.ips[0][1])))
        PersistentDiskState.end(self.pds[0][0], self.pds[0][1])
        self.user, self.another_user = user, another_user

    # @unittest.skip('')
    def test_get_by_user(self):
        url = '{0}/{1}'.format(self.url, self.user.username)
        self.assert401(self.open(url))
        self.assert403(self.open(url, auth=self.userauth))
        response = self.open(url, auth=self.adminauth)
        self.assert200(response)  # only Admin has permission

        validator = UsageResponseValidator()
        if not validator.validate_get(response.json):
            self.fail(validator.errors)

        self.assertEqual(len(response.json['data']['ip_usage']), 2)  # first user only
        self.assertEqual(len(response.json['data']['pd_usage']), 2)  # first user only

    # @unittest.skip('')
    def test_get_all(self):
        self.assert401(self.open())
        self.assert403(self.open(auth=self.userauth))
        response = self.open(auth=self.adminauth)
        self.assert200(response)  # only Admin has permission

        validator = UsageResponseValidator()
        if not validator.validate_get_list(response.json):
            self.fail(validator.errors)

        data = response.json['data']
        self.assertEqual(len(data[self.user.username]['ip_usage']), 2)
        self.assertEqual(len(data[self.another_user.username]['ip_usage']), 1)
        self.assertEqual(len(data[self.user.username]['pd_usage']), 2)
        self.assertEqual(len(data[self.another_user.username]['pd_usage']), 1)


if __name__ == '__main__':
    unittest.main()
