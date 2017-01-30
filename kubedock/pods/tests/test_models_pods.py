
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

import json

from uuid import uuid4
from ..models import Pod as DBPod, PodIP
from .. import models
from ...testutils.testcases import DBTestCase
from ...kapi.tests.test_podcollection import TestCaseMixin
from ...users.models import User


class TestPod(DBTestCase, TestCaseMixin):
    def setUp(self):
        self.user, _ = self.fixtures.user_fixtures()
        self.internal_user = User.get_internal()
        self.mock_methods(models, 'current_app')
        models.current_app.config = {'FIXED_IP_POOLS': False}

        # Service pod
        service_config = {
            'name': 'service-pod',
            'containers': []
        }
        self.service_pod = self.make_pod(
            name=service_config['name'], config=service_config,
            owner=self.internal_user)

        # Local storage pod
        ls_config = {
            'name': 'pod-with-LS',
            'node': 'mock-node',
            'volumes': [{
                'annotation': {
                    'localStorage': {'path': 'mock/path', 'size': 1}},
                'hostPath': 'mock/host/path',
                'name': 'mock-name'
            }],
            'containers': []
        }
        self.pod_with_ls = self.make_pod(name=ls_config['name'],
                                         config=ls_config)

        # Public IP pod
        ip_config = {
            'name': 'pod-with-IP',
            'node': 'mock-node',
            'volumes': [],
            'public_ip': '127.0.0.1',
            'containers': [{
                'image': 'alexcheng/magento', 'kubes': 1,
                'ports': [{
                    'containerPort': 80,
                    'isPublic': True,
                    'protocol': 'tcp'
                }]
            }]
        }
        self.pod_with_ip = self.make_pod(
            name=ip_config['name'], config=ip_config, ip=1234567890)

        self.node = self.pod_with_ls.get_dbconfig('node', None)

    def make_pod(self, name='mock-name', config={}, owner=None, ip=None):
        pod = DBPod(name=name, config=json.dumps(config),
                    owner=owner if owner is not None else self.user,
                    id=str(uuid4()), kube_id=1)
        if ip is not None:
            # Set PodIP
            PodIP(pod=pod, network='some-network', ip_address=ip)
        return pod

    def test_has_local_storage(self):
        """
        Test pod.has_local_storage
        """
        res = self.service_pod.has_local_storage
        self.assertFalse(res)

        res = self.pod_with_ls.has_local_storage
        self.assertTrue(res)

        res = self.pod_with_ip.has_local_storage
        self.assertFalse(res)

    def test_is_service_pod(self):
        """
        Test pod.is_service_pod
        """
        res = self.service_pod.is_service_pod
        self.assertTrue(res)

        res = self.pod_with_ls.is_service_pod
        self.assertFalse(res)

        res = self.pod_with_ip.is_service_pod
        self.assertFalse(res)

    def test_has_fixed_public_ip(self):
        """
        Test pod.has_fixed_public_ip
        """
        models.current_app.config = {'FIXED_IP_POOLS': True}

        res = self.service_pod.has_fixed_public_ip
        self.assertFalse(res)

        res = self.pod_with_ls.has_fixed_public_ip
        self.assertFalse(res)

        res = self.pod_with_ip.has_fixed_public_ip
        self.assertTrue(res)

        models.current_app.config = {'FIXED_IP_POOLS': False}
        res = self.pod_with_ip.has_fixed_public_ip
        self.assertFalse(res)

    def test_pinned_node(self):
        """
        Test pod.pinned_node
        """
        models.current_app.config = {'FIXED_IP_POOLS': True}
        res = self.pod_with_ip.pinned_node
        self.assertEqual(res, self.node)

        models.current_app.config = {'FIXED_IP_POOLS': False}
        res = self.service_pod.pinned_node
        self.assertEqual(res, None)

        res = self.pod_with_ls.pinned_node
        self.assertEqual(res, self.node)

        res = self.pod_with_ip.pinned_node
        self.assertEqual(res, None)
