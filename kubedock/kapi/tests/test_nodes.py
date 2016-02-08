"""Unit tests for kapi.nodes
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
from kubedock.kapi import nodes
from kubedock.testutils.testcases import DBTestCase
from kubedock import settings
from kubedock.nodes.models import Node
from kubedock.api import APIError


class TestNodes(DBTestCase):

    def setUp(self):
        self.testhost = 'testhost1'
        super(TestNodes, self).setUp()
        self.original_install_log_dir = settings.NODE_INSTALL_LOG_FILE
        self.tempdir = tempfile.mkdtemp()
        settings.NODE_INSTALL_LOG_FILE = os.path.join(
            self.tempdir,
            os.path.basename(settings.NODE_INSTALL_LOG_FILE)
        )
        nodes.MASTER_IP = '192.168.1.1'

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
        super(TestNodes, self).tearDown()
        shutil.rmtree(self.tempdir)
        settings.NODE_INSTALL_LOG_FILE = self.original_install_log_dir

    @mock.patch.object(nodes, '_check_node_hostname')
    @mock.patch.object(nodes, '_deploy_node')
    @mock.patch.object(nodes, 'PodCollection')
    @mock.patch.object(nodes.socket, 'gethostbyname')
    def test_create_node(self, gethostbyname_mock, podcollection_mock,
                         deploy_node_mock,
                         check_node_hostname_mock):
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
        gethostbyname_mock.assert_called_once_with(hostname)
        node = Node.get_by_name(hostname)
        self.assertIsNotNone(node)
        self.assertEqual(node.ip, ip)
        self.assertEqual(node.kube_id, default_kube_type)
        check_node_hostname_mock.assert_called_once_with(node.ip, hostname)

        # add a node with the same IP
        with self.assertRaises(APIError):
            nodes.create_node(None, hostname, kube_id)

        # add a node with master IP
        ip = nodes.MASTER_IP
        gethostbyname_mock.return_value = ip
        with self.assertRaises(APIError):
            nodes.create_node(None, 'anotherhost', kube_id)

    @mock.patch.object(nodes.tasks, 'remove_node_by_host')
    def test_delete_node(self, remove_by_host_mock):
        """Test for kapi.nodes.delete_node function."""
        node1, node2 = self.add_two_nodes()
        id1 = node1.id

        nodes.delete_node(id1)
        nodes_ = Node.get_all()
        remove_by_host_mock.assert_called_once_with(node1.hostname)
        self.assertEqual(nodes_, [node2])

        with self.assertRaises(APIError):
            nodes.delete_node(id1)

    @mock.patch.object(nodes, '_fix_missed_nodes')
    @mock.patch.object(nodes.tasks, 'get_all_nodes')
    def test_get_nodes_collection(self, get_all_nodes_mock,
                                  fix_missed_nodes_mock):
        """Test for kapi.nodes.get_nodes_collection function."""
        node1, node2 = self.add_two_nodes()
        ip3 = '192.168.1.4'
        host3 = 'host3'
        kube_type = Kube.get_default_kube_type()
        node3 = Node(ip=ip3, hostname=host3, kube_id=kube_type, state='pending')
        db.session.add(node3)
        db.session.commit()
        get_all_nodes_mock.return_value = [
            {
                'metadata': {'name': node1.hostname},
                'status': {'conditions':[{'type': 'Ready', 'status': 'True'}]}
            },
            {
                'metadata': {'name': node2.hostname},
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

    @mock.patch.object(nodes, '_get_k8s_node_by_host')
    def test_get_one_node(self, get_k8s_node_mock):
        """Test for kapi.nodes.get_one_node function."""
        with self.assertRaises(APIError) as err:
            nodes.get_one_node(123)
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
        with self.assertRaises(APIError):
            nodes.get_one_node(node1.id)
        get_k8s_node_mock.assert_called_once_with(node1.hostname)

        get_k8s_node_mock.return_value = {
            "status": {
                "capacity": {
                    "cpu": "1",
                    "memory": "{}Ki".format(2 * 1024 * 1024),
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
        node = nodes.get_one_node(node1.id)
        self.assertEqual(
            node,
            {
                'id': node1.id,
                'ip': node1.ip,
                'install_log': '',
                'reason': '',
                'hostname': node1.hostname,
                'kube_type': node1.kube_id,
                'status': 'running',
                'resources': {
                    "cpu": "1",
                    "memory": 2 * 1024 * 1024 * 1024,
                    "pods": "40"
                }
            }
        )

    @mock.patch.object(nodes.socket, 'gethostbyname')
    def test_edit_node_hostname(self, gethostbyname_mock):
        """Test for kapi.nodes.edit_node_hostname function."""
        node1, _ = self.add_two_nodes()

        with self.assertRaises(APIError):
            nodes.edit_node_hostname(node1.id, 'invalidip', 'newhost')

        gethostbyname_mock.return_value = 'invalidip'
        with self.assertRaises(APIError):
            nodes.edit_node_hostname(node1.id, node1.ip, 'newhost')

        gethostbyname_mock.return_value = node1.ip
        node = nodes.edit_node_hostname(node1.id, node1.ip, 'newhost')
        self.assertEqual(node.hostname, 'newhost')
        node = Node.get_by_id(node.id)
        self.assertEqual(node.hostname, 'newhost')

    @mock.patch.object(nodes.tasks, 'add_new_node')
    def test_redeploy_node(self, add_new_node_mock):
        """Test for kapi.nodes.redeploy_node function."""
        with self.assertRaises(APIError) as err:
            nodes.redeploy_node(1234)
        self.assertEqual(err.exception.status_code, 404)

        ip1 = '192.168.1.2'
        host1 = 'host1'
        kube_type = Kube.get_default_kube_type()
        node1 = Node(ip=ip1, hostname=host1, kube_id=kube_type)
        db.session.add(node1)
        db.session.commit()

        nodes.redeploy_node(node1.id)
        add_new_node_mock.delay.assert_called_once_with(node1.id, redeploy=True)

    @responses.activate
    def test__get_k8s_node_by_host(self):
        """Test for kapi.nodes._get_k8s_node_by_host function."""
        host1 = 'host1'
        host2 = 'host2'
        url = nodes.get_api_url('nodes', host1, namespace=False)
        responses.add(responses.GET, url, body='invalid json')
        res = nodes._get_k8s_node_by_host(host1)
        self.assertEqual(res, {"status": "Failure"})

        url = nodes.get_api_url('nodes', host2, namespace=False)
        valid_answer = {"status": {"key": "value"}}
        responses.add(responses.GET, url,
            body=json.dumps(valid_answer))
        res = nodes._get_k8s_node_by_host(host2)
        self.assertEqual(res, valid_answer)

    @mock.patch.object(nodes.socket, 'gethostbyname')
    def test__fix_missed_nodes(self, gethostbyname_mock):
        """Test for kapi.nodes._fix_missed_nodes function."""
        node1, node2 = self.add_two_nodes()
        res = nodes._fix_missed_nodes([node1, node2], {})
        self.assertEqual(res, [node1, node2])

        ip3 = '192.168.1.55'
        host3 = 'host3'
        gethostbyname_mock.return_value = ip3
        res = nodes._fix_missed_nodes([node1, node2], {host3: {}})
        node3 = Node.query.filter(Node.hostname == host3).first()
        self.assertIsNotNone(node3)
        self.assertEqual(res, [node1, node2, node3])

    @mock.patch.object(nodes, 'run_ssh_command')
    def test__check_node_hostname(self, run_cmd_mock):
        """Test for kapi.nodes._check_node_hostname function."""
        ip = '192.168.1.12'
        host = 'qwerty21'
        run_cmd_mock.return_value = (1, 'error')

        with self.assertRaises(APIError):
            nodes._check_node_hostname(ip, host)
        run_cmd_mock.assert_called_once_with(ip, 'uname -n')

        run_cmd_mock.return_value = (0, 'invalidhost')
        with self.assertRaises(APIError):
            nodes._check_node_hostname(ip, host)

        run_cmd_mock.return_value = (0, host + '  ')
        nodes._check_node_hostname(ip, host)

    def test__node_is_active(self):
        """Test for kapi.nodes._node_is_active function."""
        invalid_status = {}
        self.assertFalse(nodes._node_is_active(invalid_status))

        invalid_status = ''
        self.assertFalse(nodes._node_is_active(invalid_status))

        valid_status = {
            'status': {
                'conditions': [
                    {'type': 'Ready', 'status': 'True'}
                ]
            }
        }
        self.assertTrue(nodes._node_is_active(valid_status))

    @mock.patch.object(nodes.tasks, 'add_node_to_k8s')
    @mock.patch.object(nodes.tasks, 'add_new_node')
    @mock.patch.object(nodes.tasks, 'is_ceph_installed_on_node')
    def test__deploy_node(self, is_ceph_mock, add_node_mock,
                          add_node_to_k8s_mock):
        """Test for kapi.nodes._deploy_node function."""
        node1, node2 = self.add_two_nodes()
        with_testing = True
        do_deploy = True
        nodes._deploy_node(node1, do_deploy, with_testing)
        add_node_mock.delay.assert_called_once_with(
            node1.id, with_testing, [node2.ip])

        self.assertFalse(is_ceph_mock.called)
        self.assertFalse(add_node_to_k8s_mock.called)

        add_node_mock.delay.reset_mock()

        with_testing = True
        do_deploy = False
        is_ceph_mock.return_value = False
        add_node_to_k8s_mock.return_value = None
        nodes._deploy_node(node1, do_deploy, with_testing)
        is_ceph_mock.assert_called_once_with(node1.hostname)
        add_node_to_k8s_mock.assert_called_once_with(
            node1.hostname, node1.kube_id, False)
        self.assertEqual(node1.state, 'completed')
        self.assertFalse(add_node_mock.delay.called)


if __name__ == '__main__':
    unittest.main()
