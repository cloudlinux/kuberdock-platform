
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

"""Unit tests for kapi.node_utils
"""
import os
import shutil
import tempfile
import unittest
import json

import mock
import responses

from kubedock.core import db
from kubedock.billing.models import Kube
from kubedock.exceptions import APIError
from kubedock.kapi import node_utils
from kubedock.testutils.testcases import DBTestCase
from kubedock import settings
from kubedock.nodes.models import Node
from kubedock.utils import NODE_STATUSES


class TestNodeUtils(DBTestCase):

    def setUp(self):
        super(TestNodeUtils, self).setUp()
        self.original_install_log_dir = settings.NODE_INSTALL_LOG_FILE
        self.tempdir = tempfile.mkdtemp()
        settings.NODE_INSTALL_LOG_FILE = os.path.join(
            self.tempdir,
            os.path.basename(settings.NODE_INSTALL_LOG_FILE)
        )
        self.cpu = 1
        self.mem_kb = 2 ** 20             # in kilobytes
        self.mem = self.mem_kb * 2 ** 10  # in bytes
        self.cpu_multiplier = 8
        self.mem_multiplier = 4
        self.multipliers = {
            'cpu_multiplier': self.cpu_multiplier,
            'memory_multiplier': self.mem_multiplier,
        }
        self.get_by_name = lambda x: str(self.multipliers.get(x, ''))

    def add_two_nodes(self):
        ip1 = '192.168.1.2'
        host1 = 'host1'
        ip2 = '192.168.1.3'
        host2 = 'host2'
        kube_type = Kube.get_default_kube_type()
        node1 = Node(ip=ip1, hostname=host1, kube_id=kube_type)
        node2 = Node(ip=ip2, hostname=host2, kube_id=kube_type)
        db.session.add_all((node1, node2))
        db.session.commit()
        self.node1 = node1
        self.node2 = node2
        return (node1, node2)

    def tearDown(self):
        super(TestNodeUtils, self).tearDown()
        shutil.rmtree(self.tempdir)
        settings.NODE_INSTALL_LOG_FILE = self.original_install_log_dir

    @mock.patch.object(node_utils, 'SystemSettings')
    @mock.patch.object(node_utils, '_fix_missed_nodes')
    @mock.patch.object(node_utils, 'get_all_nodes')
    def test_get_nodes_collection(self, get_all_nodes_mock,
                                  fix_missed_nodes_mock,
                                  system_settings_mock):
        """Test for kapi.node_utils.get_nodes_collection function."""
        node1, node2 = self.add_two_nodes()
        ip3 = '192.168.1.4'
        host3 = 'host3'
        kube_type = Kube.get_default_kube_type()
        node3 = Node(
            ip=ip3, hostname=host3, kube_id=kube_type,
            state=NODE_STATUSES.pending
        )
        db.session.add(node3)
        db.session.commit()
        get_all_nodes_mock.return_value = [
            {
                'metadata': {'name': node1.hostname},
                'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}
            },
            {
                'metadata': {'name': node2.hostname},
                'status': {'conditions': [{
                    'type': 'Unknown', 'status': 'True',
                    'reason': 'qwerty', 'lastTransitionTime': 'asdfg'
                }]}
            }
        ]
        fix_missed_nodes_mock.return_value = (node1, node2, node3)
        system_settings_mock.get_by_name = self.get_by_name
        res = node_utils.get_nodes_collection()
        get_all_nodes_mock.assert_called_once_with()
        # AC-3349 Fix. Not needed due to fix in 'get_nodes_collection'.
        # fix_missed_nodes_mock.assert_called_once_with(
        #     [node1, node2, node3],
        #     {x['metadata']['name']: x
        #      for x in get_all_nodes_mock.return_value})
        self.assertEqual(len(res), 3)
        self.assertEqual(
            res[0],
            {
                'id': node1.id,
                'ip': node1.ip,
                'hostname': node1.hostname,
                'kube_type': node1.kube_id,
                'status': NODE_STATUSES.running,
                'reason': '',
                'install_log': '',
                'resources': {}
            }
        )
        self.assertEqual(res[1]['id'], node2.id)
        self.assertEqual(res[1]['ip'], node2.ip)
        self.assertEqual(res[1]['hostname'], node2.hostname)
        self.assertTrue(res[1]['status'], NODE_STATUSES.troubles)
        self.assertTrue('qwerty' in res[1]['reason'])
        self.assertTrue('asdfg' in res[1]['reason'])

        self.assertEqual(res[2]['id'], node3.id)
        self.assertEqual(res[2]['ip'], node3.ip)
        self.assertEqual(res[2]['hostname'], node3.hostname)
        self.assertTrue(res[2]['status'], NODE_STATUSES.pending)

    @mock.patch.object(node_utils, 'SystemSettings')
    @mock.patch.object(node_utils, '_get_k8s_node_by_host')
    def test_get_one_node(self, get_k8s_node_mock, system_settings_mock):
        """Test for kapi.node_utils.get_one_node function."""
        with self.assertRaises(APIError) as err:
            node_utils.get_one_node(123)
        self.assertEqual(err.exception.status_code, 404)

        node1, node2 = self.add_two_nodes()

        get_k8s_node_mock.return_value = {
            "kind": "Status",
            "apiVersion": "v1",
            "metadata": {},
            "status": "Failure",
            "message": "node nodename not found",
            "reason": "NotFound",
            "code": 404
        }
        system_settings_mock.get_by_name = self.get_by_name
        node = node_utils.get_one_node(node1.id)
        self.assertDictContainsSubset({
            'id': node1.id,
            'ip': node1.ip,
            'hostname': node1.hostname,
            'kube_type': node1.kube_id,
            'status': NODE_STATUSES.troubles,
            'resources': {}
        }, node)
        get_k8s_node_mock.assert_called_once_with(node1.hostname)

        get_k8s_node_mock.return_value = {
            "status": {
                "capacity": {
                    "cpu": str(self.cpu * self.cpu_multiplier),
                    "memory": "{}Ki".format(self.mem_kb * self.mem_multiplier),
                    "pods": "40"
                },
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                    }
                ]
            }
        }
        node = node_utils.get_one_node(node1.id)
        self.assertEqual(
            node,
            {
                'id': node1.id,
                'ip': node1.ip,
                'install_log': '',
                'reason': '',
                'hostname': node1.hostname,
                'kube_type': node1.kube_id,
                'status': NODE_STATUSES.running,
                'resources': {
                    "cpu": str(float(self.cpu)),
                    "memory": float(self.mem),
                    "pods": "40"
                }
            }
        )

    @responses.activate
    def test__get_k8s_node_by_host(self):
        """Test for kapi.node_utils._get_k8s_node_by_host function."""
        host1 = 'host1'
        host2 = 'host2'
        url = node_utils.get_api_url('nodes', host1, namespace=False)
        responses.add(responses.GET, url, body='invalid json')
        res = node_utils._get_k8s_node_by_host(host1)
        self.assertEqual(res, {"status": "Failure"})

        url = node_utils.get_api_url('nodes', host2, namespace=False)
        valid_answer = {"status": {"key": "value"}}
        responses.add(responses.GET, url, body=json.dumps(valid_answer))
        res = node_utils._get_k8s_node_by_host(host2)
        self.assertEqual(res, valid_answer)

    @mock.patch.object(node_utils.socket, 'gethostbyname')
    def test__fix_missed_nodes(self, gethostbyname_mock):
        """Test for kapi.node_utils._fix_missed_nodes function."""
        node1, node2 = self.add_two_nodes()
        res = node_utils._fix_missed_nodes([node1, node2], {})
        self.assertEqual(res, [node1, node2])

        ip3 = '192.168.1.55'
        host3 = 'host3'
        gethostbyname_mock.return_value = ip3
        res = node_utils._fix_missed_nodes([node1, node2], {host3: {}})
        node3 = Node.query.filter(Node.hostname == host3).first()
        self.assertIsNotNone(node3)
        self.assertEqual(res, [node1, node2, node3])

    def test__node_is_active(self):
        """Test for kapi.node_utils._node_is_active function."""
        invalid_status = {}
        self.assertFalse(node_utils._node_is_active(invalid_status))

        invalid_status = ''
        self.assertFalse(node_utils._node_is_active(invalid_status))

        valid_status = {
            'status': {
                'conditions': [
                    {'type': 'Ready', 'status': 'True'}
                ]
            }
        }
        self.assertTrue(node_utils._node_is_active(valid_status))


class TestNodeUtilsFunctions(unittest.TestCase):
    """Tests for utilities which is independent from DB or other
    infrastructure.
    """

    @mock.patch.object(node_utils, '_exec_on_host')
    def test_get_block_device_list(self, exec_on_host_mock):
        name1 = 'sda'
        size1 = 424242
        type1 = 'disk'
        mp1 = ''
        name2 = 'sda1'
        size2 = 5353
        type2 = 'part'
        mp2 = '/boot\\ with\\ spaces'
        name3 = 'centos-root'
        size3 = 646464
        type3 = 'lvm'
        mp3 = '/'
        lsblk_result = (
            'NAME="{}" MAJ:MIN="8:0" RM="0" SIZE="{}" RO="0" TYPE="{}" '
            'MOUNTPOINT="{}"\n'
            'NAME="{}" MAJ:MIN="8:0" RM="0" SIZE="{}" RO="0" TYPE="{}" '
            'MOUNTPOINT="{}"\n'
            'NAME="{}" MAJ:MIN="253:0" RM="0" SIZE="{}" RO="0" TYPE="{}" '
            'MOUNTPOINT="{}"\n'
        ).format(
            name1, size1, type1, mp1,
            name2, size2, type2, mp2,
            name3, size3, type3, mp3,
        )

        exec_on_host_mock.return_value = lsblk_result
        hostname = 'qwerty'
        devices = node_utils.get_block_device_list(hostname)
        self.assertEqual({name1, name2}, set(devices))
        dev = devices[name1]
        self.assertEqual(
            dev,
            {
                'NAME': name1,
                'SIZE': size1,
                'TYPE': type1,
                'MOUNTPOINT': mp1,
                'DEVICE': '/dev/' + name1,
            }
        )
        dev = devices[name2]
        self.assertEqual(
            dev,
            {
                'NAME': name2,
                'SIZE': size2,
                'TYPE': type2,
                'MOUNTPOINT': mp2,
                'DEVICE': '/dev/' + name2,
            }
        )
        self.assertEqual(exec_on_host_mock.call_count, 1)


if __name__ == '__main__':
    unittest.main()
