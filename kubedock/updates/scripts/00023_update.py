
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

from kubedock.core import db


PREFIX = 'docker://'


def upgrade(upd, with_testing, *args, **kwargs):
    from kubedock.usage.models import ContainerState
    upd.print_log('Cut off "{0}" from ContainerState.docker_id'.format(PREFIX))

    for cs in ContainerState.query.all():

        if cs.docker_id.startswith(PREFIX):
            docker_id = cs.docker_id.split(PREFIX)[-1]

            ContainerState.query.filter_by(
                pod_id=cs.pod_id,
                container_name=cs.container_name,
                docker_id=docker_id,
                kubes=cs.kubes,
                start_time=cs.start_time,
            ).delete()

            cs.docker_id = docker_id

    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    from kubedock.usage.models import ContainerState
    upd.print_log('Add "{0}" to ContainerState.docker_id'.format(PREFIX))

    for cs in ContainerState.query.all():

        if not cs.docker_id.startswith(PREFIX):
            docker_id = PREFIX + cs.docker_id

            ContainerState.query.filter_by(
                pod_id=cs.pod_id,
                container_name=cs.container_name,
                docker_id=docker_id,
                kubes=cs.kubes,
                start_time=cs.start_time,
            ).delete()

            cs.docker_id = docker_id

    db.session.commit()
