"""Unit tests for kapi.nodes
"""
import os
import shutil
import tempfile
import unittest

import mock

from kubedock.core import db
from kubedock.billing.models import Kube
from kubedock.kapi import nodes
from kubedock.testutils.testcases import DBTestCase
from kubedock.testutils import fixtures
from kubedock import settings
from kubedock.nodes.models import Node
from kubedock.api import APIError


class TestNodes(DBTestCase):

    def setUp(self):
        self.testhost = 'testhost1'
        super(TestNodes, self).setUp()
        fixtures.initial_fixtures()
        self.original_install_log_dir = settings.NODE_INSTALL_LOG_FILE
        self.tempdir = tempfile.mkdtemp()
        settings.NODE_INSTALL_LOG_FILE = os.path.join(
            self.tempdir,
            os.path.basename(settings.NODE_INSTALL_LOG_FILE)
        )
        nodes.MASTER_IP = '192.168.1.1'

    def tearDown(self):
        super(TestNodes, self).tearDown()
        shutil.rmtree(self.tempdir)
        settings.NODE_INSTALL_LOG_FILE = self.original_install_log_dir

    @mock.patch.object(nodes, 'send_event')
    @mock.patch.object(nodes, '_deploy_node')
    @mock.patch.object(nodes, 'PodCollection')
    @mock.patch.object(nodes.socket, 'gethostbyname')
    def test_create_node(self, gethostbyname_mock, podcollection_mock,
                         deploy_node_mock, send_event_mock):
        """Test for kapi.nodes.create_node function."""
        ip = '192.168.1.2'
        hostname = 'testhost1'
        default_kube_type = Kube.get_default_kube_type()
        kube_id = default_kube_type

        gethostbyname_mock.return_value = ip
        podcollection_mock.add.return_value = {'id': 1}

        res = nodes.create_node(None, hostname, kube_id)
        self.assertEqual(res.ip, ip)
        self.assertEqual(res.hostname, hostname)

        deploy_node_mock.assert_called_once_with(
            res, True, False
        )
        send_event_mock.assert_called_once_with('pull_nodes_state', 'ping')
        gethostbyname_mock.assert_called_once_with(hostname)
        node = Node.get_by_name(hostname)
        self.assertIsNotNone(node)
        self.assertEqual(node.ip, ip)
        self.assertEqual(node.kube_id, default_kube_type)

        # add a node with the same IP
        with self.assertRaises(APIError):
            nodes.create_node(None, hostname, kube_id)

        # add a node with master IP
        ip = nodes.MASTER_IP
        gethostbyname_mock.return_value = ip
        with self.assertRaises(APIError):
            nodes.create_node(None, 'anotherhost', kube_id)

    @mock.patch.object(nodes.tasks, 'remove_node_by_host')
    @mock.patch.object(nodes, 'handle_nodes')
    def test_delete_node(self, handle_nodes_mock, remove_by_host_mock):
        """Test for kapi.nodes.delete_node function."""
        ip1 = '192.168.1.2'
        host1 = 'host1'
        ip2 = '192.168.1.3'
        host2 = 'host2'
        kube_type = Kube.get_default_kube_type()
        node1 = Node(ip=ip1, hostname=host1, kube_id=kube_type)
        node2 = Node(ip=ip2, hostname=host2, kube_id=kube_type)
        db.session.add_all((node1, node2))
        db.session.commit()
        id1 = node1.id

        nodes.delete_node(id1)
        for port in nodes.PORTS_TO_RESTRICT:
            handle_nodes_mock.assert_any_call(
                nodes.process_rule, nodes=[ip2], action='delete',
                port=port, target='ACCEPT', source=ip1, append_reject=False)
        nodes_ = Node.get_all()
        remove_by_host_mock.assert_called_once_with(host1)
        self.assertEqual(nodes_, [node2])

        with self.assertRaises(APIError):
            nodes.delete_node(id1)

    @mock.patch.object(nodes, '_fix_missed_nodes')
    @mock.patch.object(nodes.tasks, 'get_all_nodes')
    def test_get_nodes_collection(self, get_all_nodes_mock,
                                  fix_missed_nodes_mock):
        """Test for kapi.nodes.get_nodes_collection function."""
        ip1 = '192.168.1.2'
        host1 = 'host1'
        ip2 = '192.168.1.3'
        host2 = 'host2'
        ip3 = '192.168.1.4'
        host3 = 'host3'
        kube_type = Kube.get_default_kube_type()
        node1 = Node(ip=ip1, hostname=host1, kube_id=kube_type)
        node2 = Node(ip=ip2, hostname=host2, kube_id=kube_type)
        node3 = Node(ip=ip3, hostname=host3, kube_id=kube_type, state='pending')
        db.session.add_all((node1, node2, node3))
        db.session.commit()
        get_all_nodes_mock.return_value = [
            {
                'metadata': {'name': host1},
                'status': {'conditions':[{'type': 'Ready', 'status': 'True'}]}
            },
            {
                'metadata': {'name': host2},
                'status': {'conditions':[{
                    'type': 'Unknown', 'status': 'True',
                    'reason': 'qwerty', 'lastTransitionTime': 'asdfg'
                }]}
            }
        ]
        fix_missed_nodes_mock.return_value = (node1, node2, node3)
        res = nodes.get_nodes_collection()
        get_all_nodes_mock.assert_called_once_with()
        fix_missed_nodes_mock.assert_called_once_with(
            [node1, node2, node3],
            {x['metadata']['name']: x for x in get_all_nodes_mock.return_value})
        self.assertEqual(len(res), 3)
        self.assertEqual(
            res[0],
            {
                'id': node1.id,
                'ip': node1.ip,
                'hostname': node1.hostname,
                'kube_type': node1.kube_id,
                'status': 'running',
                'reason': '',
                'install_log': '',
                'resources': {}
            }
        )
        self.assertEqual(res[1]['id'], node2.id)
        self.assertEqual(res[1]['ip'], node2.ip)
        self.assertEqual(res[1]['hostname'], node2.hostname)
        self.assertTrue(res[1]['status'], 'troubles')
        self.assertTrue('qwerty' in res[1]['reason'])
        self.assertTrue('asdfg' in res[1]['reason'])

        self.assertEqual(res[2]['id'], node3.id)
        self.assertEqual(res[2]['ip'], node3.ip)
        self.assertEqual(res[2]['hostname'], node3.hostname)
        self.assertTrue(res[2]['status'], 'pending')


if __name__ == '__main__':
    unittest.main()
