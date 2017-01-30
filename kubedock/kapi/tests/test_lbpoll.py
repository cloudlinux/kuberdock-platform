
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
from kubedock.kapi.helpers import Services
from kubedock.kapi.lbpoll import ExternalIPsService


class TestLoadBalancer(unittest.TestCase):

    def test_get_publicIP(self):
        conf = Services().get_template(
            'pod_id', [{"name": "port", "port": 80, "targetPort": 80}])
        publicIP = '10.0.0.1'
        self.assertEqual(None, ExternalIPsService().get_publicIP(conf))
        conf['spec']['externalIPs'] = [publicIP]
        self.assertEqual(publicIP, ExternalIPsService().get_publicIP(conf))
        self.assertEqual(
            {'pod_id': publicIP},
            ExternalIPsService().get_pods_publicIP({'pod_id': conf}))
