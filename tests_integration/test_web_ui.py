
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

from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.utils import local_exec


@pipeline('web_ui')
def test_web_ui(cluster):
    master_ip = cluster.get_host_ip("master")
    env = {
        'ROBOT_ARGS': (" -v SERVER:{0}"
                       " -v ADMIN_PASSWORD:admin"
                       # " -v BROWSER:firefox"
                       " /tests").format(master_ip)
    }
    local_exec(["tox", "-e", "webui"], env)
