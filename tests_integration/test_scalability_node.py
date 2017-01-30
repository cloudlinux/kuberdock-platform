
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


import logging

from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.utils import assert_eq
from tests_integration.lib.cluster_utils import (set_kubelet_multipliers,
                                                 add_pa_from_url)
from tests_integration.lib.load_testing_utils import fill_with_pa, gen_workload


LOG = logging.getLogger(__name__)

CPU_MULT = 15
MEMORY_MULT = 10
REQUESTS_NUMBER = 1
REQUESTED_PODS = 0.1


@pipeline('scalability_node')
@pipeline('scalability_node_aws')
def test_fill_node_and_add_another(cluster):
    LOG.debug("Modifying multipliers.")
    set_kubelet_multipliers(cluster, CPU_MULT, MEMORY_MULT)
    LOG.debug("Temporary remove the second node.")
    cluster.nodes.get_node('node2').delete()
    LOG.debug("Create, start and install density wordpress pods till it "
              "is possible.")
    pa_url = "https://raw.githubusercontent.com/cloudlinux/" \
             "kuberdock_predefined_apps/1.5.0-beta/wordpress.yaml"
    pa_name = add_pa_from_url(cluster, pa_url)
    pods = fill_with_pa(cluster, pa_name)
    not_started_pod = pods.pop()
    sample_size = int(len(pods) * REQUESTED_PODS)
    with gen_workload(pods, sample_size, REQUESTS_NUMBER):
        LOG.debug("Adding a new node.")
        cluster.nodes.add('node2')
        LOG.debug("Starting failed pod.")
        not_started_pod.start()
        not_started_pod.wait_for_status('running')
        LOG.debug("Create, start and install density wordpress pods till it "
                  "is possible.")
        second_pods = fill_with_pa(cluster, pa_name)
        second_pods.pop()
        # It should be able to fit twice more pods.
    assert_eq(len(pods) - 1, len(second_pods))
    # All pods should be accessible via their public IPs.
    for pa in pods + [not_started_pod, ] + second_pods:
        pa.healthcheck()
