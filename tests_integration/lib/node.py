
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

import time

from tests_integration.lib.exceptions import NodeWasNotRemoved, \
    StatusWaitException
from tests_integration.lib.utils import wait_for_status, \
    wait_for_status_not_equal


class KDNode(object):
    def __init__(self, cluster, node_data):
        self.cluster = cluster
        self.name = node_data["hostname"]
        self.ip = node_data["ip"]
        self.kube_type = node_data["kube_type"]

    @classmethod
    def add(cls, cluster, node_name, kube_type):
        docker_options = \
            '--insecure-registry=192.168.115.165:5001 ' \
            '--registry-mirror=http://192.168.115.165:5001 '

        add_cmd = 'add-node --hostname {} --kube-type {} --do-deploy -t ' \
                  '--docker-options="{}" --wait ' \
                  '--verbose'.format(node_name, kube_type, docker_options)
        cluster.manage(add_cmd)
        node_data = cluster.nodes.get_node_data(node_name)
        return cls(cluster, node_data)

    def delete(self, timeout=60):
        self.cluster.kdctl("nodes delete --hostname {}".format(self.name))
        end = time.time() + timeout
        while time.time() < end:
            if not self.exists():
                return
        raise NodeWasNotRemoved("Node {} failed to be removed in past {} "
                                "seconds".format(self.name, timeout))

    def exists(self):
        _, out, _ = self.cluster.kdctl("nodes list", out_as_dict=True)
        data = out['data']
        for node in data:
            if node['hostname'] == self.name:
                return True
        return False

    def power_off(self):
        self.cluster.power_off(self.name)

    def power_on(self):
        self.cluster.power_on(self.name)

    def reboot(self):
        """
        Reboot the node, wait till it get "pending" state, wait till is
        available again
        """
        self.cluster.ssh_exec(self.name, "reboot", check_retcode=False,
                              sudo=True)

        try:
            wait_for_status_not_equal(self, "running", tries=24, interval=5)
        except StatusWaitException:
            # If rebooted, node sometimes goes into "Troubles" and "Pending"
            # states, however sometimes Kuberdock doesn't "notice" that node
            # has rebooted
            pass

        wait_for_status(self, "running", tries=24, interval=10)

    @property
    def info(self):
        return self.cluster.nodes.get_node_data(self.name)

    @property
    def status(self):
        return self.info["status"]
