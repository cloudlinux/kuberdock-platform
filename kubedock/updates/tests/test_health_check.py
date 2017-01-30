
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

import mock
import unittest
import subprocess

from kubedock.updates import health_check
from kubedock.kapi import node_utils
from kubedock.utils import NODE_STATUSES


class TestHealthCheck(unittest.TestCase):

    @mock.patch.object(health_check, 'check_nodes')
    @mock.patch.object(health_check, 'check_master')
    def test_check_cluster(self, mock_check_master, mock_check_nodes):
        return
        mock_check_master.return_value = ''
        mock_check_nodes.return_value = ''
        msg = health_check.check_cluster()
        self.assertEqual(len(msg), 0)
        mock_check_master.return_value = 'some status'
        mock_check_nodes.return_value = ''
        msg = health_check.check_cluster()
        self.assertGreater(len(msg), 0)
        mock_check_master.return_value = ''
        mock_check_nodes.return_value = 'some status'
        msg = health_check.check_cluster()
        self.assertGreater(len(msg), 0)

    @mock.patch.object(health_check, 'get_internal_pods_state')
    @mock.patch.object(health_check, 'get_nodes_state')
    def test_check_nodes(self, mock_get_nodes_state, mock_get_pods_state):
        mock_get_nodes_state.return_value = {
            'node1': {
                'ssh': True,
                NODE_STATUSES.running: True,
                'ntp': True,
                'disk': True
            }
        }
        mock_get_pods_state.return_value = {'logs': True}
        msg = health_check.check_nodes()
        self.assertEquals(len(msg), 0)
        mock_get_nodes_state.return_value = {
            'node1': {
                'ssh': True,
                NODE_STATUSES.running: True,
                'ntp': False,
                'disk': True
            }
        }
        mock_get_pods_state.return_value = {'logs': True}
        msg = health_check.check_nodes()
        self.assertGreater(len(msg), 0)
        mock_get_nodes_state.return_value = {
            'node1': {
                'ssh': True,
                NODE_STATUSES.running: True,
                'ntp': True,
                'disk': True
            }
        }
        mock_get_pods_state.return_value = {'logs': False}
        msg = health_check.check_nodes()
        self.assertGreater(len(msg), 0)

    @mock.patch.object(health_check, 'check_tunl')
    @mock.patch.object(health_check, 'check_calico_node')
    @mock.patch.object(health_check, 'get_services_state')
    @mock.patch.object(health_check, 'check_disk_space')
    def test_check_master(self, mock_check_disk, mock_get_services,
                          mock_cn, mock_tunl):
        mock_check_disk.return_value = True
        mock_cn.return_value = True
        mock_tunl.return_value = True
        mock_get_services.return_value = {
            'ntpd': True,
            'etcd': True
        }
        msg = health_check.check_master()
        print msg
        self.assertEqual(len(msg), 0)
        mock_check_disk.return_value = 'disk state'
        mock_get_services.return_value = {
            'ntpd': True,
            'etcd': True
        }
        msg = health_check.check_master()
        self.assertGreater(len(msg), 0)
        mock_check_disk.return_value = True
        mock_get_services.return_value = {
            'ntpd': False,
            'etcd': True
        }
        msg = health_check.check_master()
        self.assertGreater(len(msg), 0)

    @mock.patch.object(health_check, 'get_disk_usage')
    def test_check_disk_space(self, mock_get_disk_usage):
        mock_get_disk_usage.return_value = [['/dev/sda1', '36%']]
        msg = health_check.check_disk_space()
        self.assertEquals(msg, True)
        health_check.MAX_DISK_PERCENTAGE = 50
        mock_get_disk_usage.return_value = [['/dev/sda1', '55%']]
        msg = health_check.check_disk_space()
        self.assertGreater(len(msg), 0)

    @mock.patch.object(subprocess, 'check_output')
    def test_get_disk_usage(self, mock_check_output):
        df_output = """Filesystem      Size  Used Avail Use% Mounted on
        /dev/sda3       13% /
        devtmpfs        0% /dev
        tmpfs           0% /dev/shm
        tmpfs           11% /run
        tmpfs           0% /sys/fs/cgroup
        /dev/sda1       34% /boot
        tmpfs           0% /run/user/0
        /dev/rbd0      25% /var/lib/kubelet/plugins/kubernetes.io/rbd/rbd/136.243.221.231-image-joomla_mysql_xvptye29__SEPID__4
        /dev/rbd1      8% /var/lib/kubelet/plugins/kubernetes.io/rbd/rbd/136.243.221.231-image-joomla_www_xvptye29__SEPID__4"""
        mock_check_output.return_value = df_output
        usage = health_check.get_disk_usage()
        self.assertEqual(usage, [['/dev/sda3', '13%'], ['/dev/sda1', '34%']])

    @mock.patch.object(health_check, 'get_nodes_collection')
    @mock.patch.object(health_check, 'get_node_state')
    def test_get_nodes_state(self, mock_get_node_state, mock_node_utils):
        mock_get_node_state.return_value = {
            'ssh': True,
            'ntp': True,
            'disk': True,
            NODE_STATUSES.running: True
        }
        mock_node_utils.return_value = [{'hostname': 'node1'},
                                        {'hostname': 'node2'}]
        nodes_state = health_check.get_nodes_state()
        self.assertEquals(len(nodes_state), 2)
        self.assertEquals(nodes_state['node1'], nodes_state['node2'])

    @mock.patch.object(health_check.subprocess, 'check_output')
    def test_get_services_state(self, mock_check_output):
        services = ['etcd', 'ntpd']
        mock_check_output.return_value = 'active\nactive\n'
        services_state = health_check.get_services_state(services)
        self.assertEquals(services_state['etcd'], services_state['ntpd'])
        self.assertEquals(services_state['etcd'], True)

    @mock.patch.object(subprocess, 'check_call')
    def test_get_service_state(self, mock_check_call):
        state = health_check.get_service_state('ntpd')
        self.assertTrue(state)
        mock_check_call.side_effect = subprocess.CalledProcessError(1, '')
        state = health_check.get_service_state('ntpd')
        self.assertFalse(state)
