
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

from random import randint
import unittest

import mock
from mock import Mock

from kubedock.testutils.testcases import APITestCase
from kubedock.utils import NODE_STATUSES


class NodesUrl(object):
    list = '/nodes/'.format
    one = '/nodes/{0}'.format
    create = '/nodes/'.format
    edit = '/nodes/{0}'.format
    patch = '/nodes/{0}'.format
    delete = '/nodes/{0}'.format

    check_host = '/nodes/checkhost/{0}'.format
    redeploy = '/nodes/redeploy/{0}'.format


class TestNodeCRUD(APITestCase):
    @mock.patch('kubedock.kapi.node_utils.get_nodes_collection')
    def test_list(self, get_nodes_collection):
        get_nodes_collection.return_value = []

        response = self.admin_open(
            NodesUrl.list(), 'GET')

        self.assert200(response)
        get_nodes_collection.assert_called_once_with()

    @mock.patch('kubedock.kapi.node_utils.get_one_node')
    def test_one(self, get_one_node):
        get_one_node.return_value = {
            'id': randint(1, 1000)
        }

        response = self.admin_open(
            NodesUrl.one(123), 'GET')

        self.assert200(response)

    def test_not_found(self):
        response = self.admin_open(NodesUrl.one(12345))
        self.assertAPIError(response, 404, 'APIError')

    def test_create_invalid_type(self):
        response = self.admin_open(
            NodesUrl.create(), 'POST', {
                'hostname': 'localhost',
                'kube_type': 12345
            })
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'kube_type': u'No such kube_type: "12345"'})

        response = self.admin_open(
            NodesUrl.create(), 'POST', {
                'hostname': 'localhost',
                'kube_type': 12345
            })
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'kube_type': u'No such kube_type: "12345"'})

    def test_create_invalid_hostname(self):
        response = self.admin_open(
            NodesUrl.create(), 'POST', {'hostname': '127.0.0.1'})
        self.assertAPIError(response, 400, 'ValidationError')

    @mock.patch('kubedock.kapi.nodes.create_node')
    def test_create(self, create_node):
        create_node.return_value = Mock(id=randint(1, 10000))

        response = self.admin_open(
            NodesUrl.create(), 'POST', {
                'hostname': 'localhost'
            })
        self.assert200(response)

    def test_edit_invalid_id(self):
        response = self.admin_open(
            NodesUrl.edit('abc'), 'PUT', {
                'hostname': 'localhost'
            })
        self.assertAPIError(response, 400, 'APIError')

    @mock.patch('kubedock.kapi.nodes.edit_node_hostname')
    def test_edit(self, *_):
        response = self.admin_open(
            NodesUrl.edit(123), 'PUT', {
                'ip': '127.0.0.1',
                'hostname': 'localhost'
            })
        self.assert200(response)

    def test_patch_without_command(self):
        response = self.admin_open(
            NodesUrl.patch(123), 'PATCH', {})
        self.assertAPIError(response, 400, 'APIError')

    def test_patch_unsupported_command(self):
        response = self.admin_open(
            NodesUrl.patch(123), 'PATCH', {
                'command': 'create'
            })

        self.assertAPIError(response, 400, 'APIError')

    @mock.patch('kubedock.kapi.nodes.mark_node_as_being_deleted')
    @mock.patch('kubedock.kapi.nodes.delete_node')
    def test_patch(self, *_):
        response = self.admin_open(
            NodesUrl.patch(123), 'PATCH', {
                'command': 'delete'
            })

        self.assert200(response)
        self.assertTrue(response.json['data']['status'] == NODE_STATUSES.deletion)

    @mock.patch('kubedock.kapi.nodes.delete_node')
    def test_delete(self, *_):
        response = self.admin_open(
            NodesUrl.patch(123), 'DELETE')

        self.assert200(response)

    def test_checkhostname(self):
        response = self.admin_open(
            NodesUrl.check_host('localhost'), 'GET')

        self.assert200(response)

    def test_checkhostname_invalid_hostname(self):
        response = self.admin_open(
            NodesUrl.check_host('127.0.0.1'), 'GET')

        self.assertAPIError(response, 400, 'ValidationError')

        response = self.admin_open(
            NodesUrl.check_host(''), 'GET')

        self.assertAPIError(response, 400, 'ValidationError',
                            {u'Hostname': [u'invalid hostname',
                                           u'empty values not allowed']})

    # The functionality is commented out
    # @mock.patch('kubedock.kapi.nodes.redeploy_node')
    # def test_redeploy(self, *_):
    #     response = self.admin_open(
    #         NodesUrl.redeploy(123), 'GET')
    #
    #     self.assert200(response)


if __name__ == '__main__':
    unittest.main()
