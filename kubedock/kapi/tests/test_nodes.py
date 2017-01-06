"""Unit tests for kapi.nodes
"""
import os
import shutil
import tempfile
import unittest

import mock
from flask import current_app

from kubedock import settings
from kubedock.billing.models import Kube
from kubedock.core import db
from kubedock.exceptions import APIError
from kubedock.kapi import nodes, network_policies
from kubedock.nodes.models import Node
from kubedock.users.models import User
from kubedock.pods.models import IPPool
from kubedock.testutils.testcases import DBTestCase
from kubedock.utils import NODE_STATUSES


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

    @mock.patch.object(nodes, 'get_current_host_ips')
    @mock.patch.object(nodes, '_check_node_ip')
    @mock.patch.object(nodes, 'PodIP')
    @mock.patch.object(nodes, 'create_logs_pod')
    @mock.patch.object(nodes, 'Etcd')
    @mock.patch.object(nodes, 'get_node_token')
    @mock.patch.object(nodes, '_check_node_hostname')
    @mock.patch.object(nodes, '_deploy_node')
    @mock.patch.object(nodes, 'PodCollection')
    @mock.patch.object(nodes.socket, 'gethostbyname')
    def test_create_node(self, gethostbyname_mock, podcollection_mock,
                         deploy_node_mock,
                         check_node_hostname_mock,
                         get_node_token_mock,
                         etcd_mock,
                         create_logs_pod_mock,
                         pod_ip_mock,
                         check_node_ip_mock,
                         get_current_host_ips_mock):
        """Test for kapi.nodes.create_node function."""
        fake_master_ips = ('127.0.0.1', nodes.MASTER_IP,)
        ip = '192.168.1.2'
        hostname = 'testhost1'
        default_kube_type = Kube.get_default_kube_type()
        kube_id = default_kube_type

        gethostbyname_mock.return_value = ip
        get_current_host_ips_mock.return_value = fake_master_ips
        podcollection_mock.return_value.add.return_value = {'id': 1}
        get_node_token_mock.return_value = 'some-token'
        log_pod_ip = '123.123.123.123'
        create_logs_pod_mock.return_value = {'podIP': log_pod_ip}

        nodes.CALICO = True

        # add a Node with Pod IP
        pod_ip = mock.Mock()
        pod_ip.ip_address = 3232235778  # '192.168.1.2'
        pod_ip.pod.name = 'pod'
        pod_ip_mock.query.filter_by.return_value.first.return_value = pod_ip
        with self.assertRaises(APIError):
            nodes.create_node(None, hostname, kube_id)

        pod_ip_mock.query.filter_by.return_value.first.return_value = None
        gethostbyname_mock.reset_mock()

        # add a Node
        res = nodes.create_node(None, hostname, kube_id)
        self.assertEqual(res.ip, ip)
        self.assertEqual(res.hostname, hostname)

        deploy_node_mock.assert_called_once_with(
            res, log_pod_ip, True, False, ebs_volume=None, ls_devices=None,
            options=None
        )
        gethostbyname_mock.assert_called_once_with(hostname)
        node = Node.get_by_name(hostname)
        self.assertIsNotNone(node)
        self.assertEqual(node.ip, ip)
        self.assertEqual(node.kube_id, default_kube_type)
        check_node_hostname_mock.assert_called_once_with(node.ip, hostname)
        check_node_ip_mock.assert_called_once_with(node.ip, hostname)
        get_node_token_mock.assert_called_once_with()
        # one call for dns pod
        self.assertEqual(etcd_mock.call_count, 1)

        # add a node with the same IP
        with self.assertRaises(APIError):
            nodes.create_node(None, hostname, kube_id)

        # add a node with master IP
        ip = nodes.MASTER_IP
        gethostbyname_mock.return_value = ip
        with self.assertRaises(APIError):
            nodes.create_node(None, 'anotherhost', kube_id)

    @mock.patch.object(network_policies, 'get_calico_ip_tunnel_address')
    @mock.patch.object(nodes, 'Etcd')
    @mock.patch.object(nodes, 'PodCollection')
    def test_create_logs_pod(self, podcollection_mock, etcd_mock,
                             get_calico_ip_mock):
        hostname = 'qwerty'
        test_result = 3131313
        pod_id = '424242'
        podcollection_mock.return_value.add.return_value = {'id': pod_id}
        podcollection_mock.return_value.get.return_value = test_result
        get_calico_ip_mock.return_value = '12.12.12.12'
        nodes.CALICO = True
        owner = User.get_internal()
        res = nodes.create_logs_pod(hostname, owner)
        self.assertEqual(res, test_result)
        self.assertEqual(etcd_mock.call_count, 1)
        get_calico_ip_mock.assert_called_once_with()
        podcollection_mock.return_value.update.assert_called_once_with(
            pod_id, {'command': 'synchronous_start'}
        )

    @mock.patch.object(nodes, 'remove_ls_storage')
    @mock.patch.object(nodes.tasks, 'remove_node_by_host')
    def test_delete_node(self, remove_by_host_mock, remove_ls_storage_mock):
        """Test for kapi.nodes.delete_node function."""
        node1, node2 = self.add_two_nodes()
        id1 = node1.id

        remove_ls_storage_mock.return_value = ''

        nodes.delete_node(id1)
        nodes_ = Node.get_all()
        remove_by_host_mock.assert_called_once_with(node1.hostname)
        remove_ls_storage_mock.assert_called_once_with(
            node1.hostname, raise_on_error=False)
        self.assertEqual(nodes_, [node2])

        with self.assertRaises(APIError):
            nodes.delete_node(id1)

    @mock.patch.object(nodes, 'remove_ls_storage')
    @mock.patch.object(nodes.tasks, 'remove_node_by_host')
    def test_node_cant_be_deleted_in_fixed_ip_pools_mode_with_active_ip_pools(
            self, remove_by_host_mock, remove_ls_storage_mock):
        remove_ls_storage_mock.return_value = ''
        current_app.config['FIXED_IP_POOLS'] = True

        node1, node2 = self.add_two_nodes()
        pool = IPPool(network='192.168.1.0/24', node=node2)
        db.session.add(pool)
        db.session.commit()

        # Has no IP pools, removed successfully
        nodes.delete_node(node1.id)
        # Has 1 active IP pool, should raise APIError
        with self.assertRaisesRegexp(APIError, 'active pools'):
            nodes.delete_node(node2.id)

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
        add_new_node_mock.apply_async.assert_called_once_with(
            node1.id, redeploy=True,
            task_id=settings.NODE_INSTALL_TASK_ID.format(
                node1.hostname, node1.id
            ))

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

    @mock.patch.object(nodes.tasks, 'add_node_to_k8s')
    @mock.patch.object(nodes.tasks, 'add_new_node')
    @mock.patch.object(nodes.tasks, 'is_ceph_installed_on_node')
    def test__deploy_node(self, is_ceph_mock, add_node_mock,
                          add_node_to_k8s_mock):
        """Test for kapi.nodes._deploy_node function."""
        node1, node2 = self.add_two_nodes()
        with_testing = True
        do_deploy = True
        logpod_ip = '123.123.123.123'
        nodes._deploy_node(node1, logpod_ip, do_deploy, with_testing)
        add_node_mock.apply_async.assert_called_once_with(
            [node1.id, logpod_ip],
            dict(
                with_testing=with_testing,
                ebs_volume=None, ls_devices=None,
                deploy_options=None,
            ),
            task_id=settings.NODE_INSTALL_TASK_ID.format(
                node1.hostname, node1.id
            )
        )

        self.assertFalse(is_ceph_mock.called)
        self.assertFalse(add_node_to_k8s_mock.called)

        add_node_mock.apply_async.reset_mock()

        with_testing = True
        do_deploy = False
        is_ceph_mock.return_value = False
        add_node_to_k8s_mock.return_value = None
        nodes._deploy_node(node1, logpod_ip, do_deploy, with_testing)
        is_ceph_mock.assert_called_once_with(node1.hostname)
        add_node_to_k8s_mock.assert_called_once_with(
            node1.hostname, node1.kube_id, False)
        self.assertEqual(node1.state, NODE_STATUSES.completed)
        self.assertFalse(add_node_mock.apply_async.called)


if __name__ == '__main__':
    unittest.main()
