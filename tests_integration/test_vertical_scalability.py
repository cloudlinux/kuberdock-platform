
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
import logging

from time import sleep

from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.utils import log_debug, retry, POD_STATUSES

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

K8S_CPU_LACK_ERROR = "Node didn't have enough resource: CPU"


@pipeline('vertical_scalability')
def test_cant_start_resized_pod_if_cpu_is_low(cluster):
    cluster.set_system_setting("2", name="cpu_multiplier")
    cluster.set_system_setting("20", name="memory_multiplier")
    template = "wordpress.yaml"

    log_debug("Starting first pod")
    # TODO: remove sleep after fixing AC-5403
    sleep(10)
    pod = cluster.pods.create_pa(
        template, wait_for_status=POD_STATUSES.running, pod_name="wordpress1")

    log_debug("Starting second pod")
    cluster.pods.create_pa(template, wait_for_status=POD_STATUSES.running,
                           pod_name="wordpress2")
    log_debug("Starting third pod")
    cluster.pods.create_pa(template, wait_for_status=POD_STATUSES.running,
                           pod_name="wordpress3")

    pod.change_kubes(kubes=9, container_name="wordpress")

    log_debug("Make sure there is warning about lack of CPUs in k8s")
    cmd = 'get events --namespace {} -o json'.format(pod.pod_id)

    def _check_presence_of_cpu_warning():
        _, out, _ = cluster.true_kubectl(cmd)
        try:
            next(e for e in json.loads(out)['items']
                 if e["reason"] == "FailedScheduling" and
                 K8S_CPU_LACK_ERROR in e["message"])
        except StopIteration:
            raise _NoResourseLackErrorInK8s("There aren't event with warning "
                                            "about lack of CPU in k8s")

    retry(_check_presence_of_cpu_warning, tries=10, interval=3)


class _NoResourseLackErrorInK8s(Exception):
    pass
