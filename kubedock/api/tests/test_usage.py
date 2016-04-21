import unittest
from kubedock.testutils.testcases import APITestCase
from kubedock.testutils import fixtures

from uuid import uuid4
from time import sleep
from datetime import datetime
from ipaddress import ip_address

from kubedock.validation import V
from kubedock.usage.models import IpState, PersistentDiskState
from kubedock.users.models import User
from kubedock.pods.models import Pod

usage_per_user_schema = {
    'pods_usage': {
        'type': list, 'required': False,
        'schema': {
            'type': dict, 'required': True,
            'schema': {
                'id': {'type': str, 'required': True, 'empty': False},
                'kube_id': {'type': int, 'required': True},
                'kubes': {'type': int, 'required': True},
                'name': {'type': str, 'required': True, 'empty': False},
                'time': {
                    'type': dict, 'required': True,
                    'propertyschema': {'type': str, 'empty': False},
                    'valueschema': {
                        'type': list, 'required': True,
                        'schema': {
                            'type': dict, 'required': True,
                            'schema': {
                                'start': {'type': int, 'required': True},
                                'end': {'type': int, 'required': True},
                                'kubes': {'type': int, 'required': True
                                          }}}}}}}},
    'pd_usage': {
        'type': list, 'required': False,
        'schema': {
            'type': dict, 'required': True,
            'schema': {
                'start': {'type': int, 'required': True},
                'end': {'type': int, 'required': True},
                'pd_name': {'type': str, 'required': True, 'empty': False},
                'size': {'type': int, 'required': True}}}},
    'ip_usage': {
        'type': list, 'required': False,
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
        'data': {'type': dict, 'required': True,
                 'schema': usage_per_user_schema}
    }
    get_list_schema = {
        'status': {'type': str, 'required': True, 'allowed': ['OK', 'error']},
        'data': {'type': dict, 'required': True,
                 'propertyschema': {'type': str, 'empty': False},
                 'valueschema': {'type': dict, 'required': True,
                                 'schema': usage_per_user_schema}}}

    def validate_get(self, data):
        return self.validate(data, self.get_schema)

    def validate_get_list(self, data):
        return self.validate(data, self.get_list_schema)


class UsageTestCase(APITestCase):
    """Tests for /api/usage endpoint"""
    url = '/usage'

    def setUp(self):
        # create test data
        self.another_user, _ = fixtures.user_fixtures(
            username='another_user', email='another_user@test.test')
        config = '{"containers":[{"kubes":1}]}'
        self.ips = [(Pod(id=str(uuid4()), owner_id=self.user.id, name='pod1',
                         kube_id=0, config=config).save(), u'192.168.43.132'),
                    (Pod(id=str(uuid4()), owner_id=self.user.id, name='pod2',
                         kube_id=0, config=config).save(), u'192.168.43.133'),
                    (Pod(id=str(uuid4()), owner_id=self.another_user.id,
                         name='pod3',
                         kube_id=0, config=config).save(), u'192.168.43.134')]
        for pod, ip in self.ips:
            IpState.start(pod.id, int(ip_address(ip)))
        self.pds = [(self.user.id, 'first_disk', 2),
                    (self.user.id, 'second_disk', 16),
                    (self.another_user.id, 'third_disk', 3)]
        for user_id, name, size in self.pds:
            PersistentDiskState.start(user_id, name, size)
        sleep(1)
        IpState.end(self.ips[0][0].id, int(ip_address(self.ips[0][1])))
        PersistentDiskState.end(self.pds[0][0], self.pds[0][1])
        self.stop_date = datetime.utcnow()

    # @unittest.skip('')
    def test_get_by_user(self):
        response = self.admin_open(self.item_url('FooBarUser'))
        self.assertAPIError(response, 404, 'UserNotFound')

        response = self.admin_open(self.item_url(self.user.username))
        self.assert200(response)  # only Admin has permission

        validator = UsageResponseValidator()
        if not validator.validate_get(response.json):
            self.fail(validator.errors)

        # first user only
        self.assertEqual(len(response.json['data']['ip_usage']), 2)
        # first user only
        self.assertEqual(len(response.json['data']['pd_usage']), 2)

    # @unittest.skip('')
    def test_get_all(self):
        response = self.admin_open()
        self.assert200(response)  # only Admin has permission

        validator = UsageResponseValidator()
        if not validator.validate_get_list(response.json):
            self.fail(validator.errors)

        data = response.json['data']
        self.assertEqual(len(data[self.user.username]['ip_usage']), 2)
        self.assertEqual(len(data[self.another_user.username]['ip_usage']), 1)
        self.assertEqual(len(data[self.user.username]['pd_usage']), 2)
        self.assertEqual(len(data[self.another_user.username]['pd_usage']), 1)

    def test_date_filter(self):
        response = self.admin_open(
            query_string={'date_from': self.stop_date.isoformat()})
        data = response.json['data']
        self.assertEqual(len(data[self.user.username]['ip_usage']), 1)
        self.assertEqual(len(data[self.another_user.username]['ip_usage']), 1)
        self.assertEqual(len(data[self.user.username]['pd_usage']), 1)
        self.assertEqual(len(data[self.another_user.username]['pd_usage']), 1)

    def test_date_error(self):
        response = self.admin_open(
            query_string={'date_from': '2016-01-00T00:00:00'})
        self.assertAPIError(response, 400, 'APIError')


if __name__ == '__main__':
    unittest.main()
