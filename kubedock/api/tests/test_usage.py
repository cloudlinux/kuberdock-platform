
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

import unittest
from kubedock.testutils.testcases import APITestCase
from kubedock.testutils import fixtures

from uuid import uuid4
from time import sleep
from datetime import datetime
from ipaddress import ip_address

from kubedock.validation import V
from kubedock.usage.models import IpState, PersistentDiskState
from kubedock.pods.models import Pod

usage_per_user_schema = {
    'pods_usage': {
        'type': 'list', 'required': False,
        'schema': {
            'type': 'dict', 'required': True,
            'schema': {
                'id': {'type': 'string', 'required': True, 'empty': False},
                'kube_id': {'type': 'integer', 'required': True},
                'kubes': {'type': 'integer', 'required': True},
                'name': {'type': 'string', 'required': True, 'empty': False},
                'time': {
                    'type': 'dict', 'required': True,
                    'propertyschema': {'type': 'string', 'empty': False},
                    'valueschema': {
                        'type': 'list', 'required': True,
                        'schema': {
                            'type': 'dict', 'required': True,
                            'schema': {
                                'start': {'type': 'integer', 'required': True},
                                'end': {'type': 'integer', 'required': True},
                                'kubes': {'type': 'integer', 'required': True
                                          }}}}}}}},
    'pd_usage': {
        'type': 'list', 'required': False,
        'schema': {
            'type': 'dict', 'required': True,
            'schema': {
                'start': {'type': 'integer', 'required': True},
                'end': {'type': 'integer', 'required': True},
                'pd_name': {'type': 'string', 'required': True,
                            'empty': False},
                'size': {'type': 'integer', 'required': True}}}},
    'ip_usage': {
        'type': 'list', 'required': False,
        'schema': {
            'type': 'dict', 'required': True,
            'schema': {
                'start': {'type': 'integer', 'required': True},
                'end': {'type': 'integer', 'required': True},
                'ip_address': {'type': 'string', 'required': True,
                               'empty': False},
                'pod_id': {'type': 'string', 'required': True,
                           'empty': False}}}}}


class UsageResponseValidator(V):
    """Validator for testing usage api"""
    get_schema = {
        'status': {'type': 'string', 'required': True,
                   'allowed': ['OK', 'error']},
        'data': {'type': 'dict', 'required': True,
                 'schema': usage_per_user_schema}
    }
    get_list_schema = {
        'status': {'type': 'string', 'required': True,
                   'allowed': ['OK', 'error']},
        'data': {'type': 'dict', 'required': True,
                 'propertyschema': {'type': 'string', 'empty': False},
                 'valueschema': {'type': 'dict', 'required': True,
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
