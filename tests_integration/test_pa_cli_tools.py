
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


@pipeline('predefined_apps')
@pipeline('predefined_apps_aws')
def test_add_run_delete_pa(cluster):
    """
    Testing workflow of PA's
    """
    pa_test = "dokuwiki_test"

    # Add PA to list of PA's
    cluster.pas.add(name=pa_test,
                    file_path="/tmp/kuberdock_predefined_apps/dokuwiki.yaml")

    pa_id = cluster.pas.get_by_name(pa_test)['id']

    # Create pod and delete PA from list
    cluster.pods.create_pa(template_name=pa_test, plan_id=1)
    cluster.pas.delete(pa_id)
