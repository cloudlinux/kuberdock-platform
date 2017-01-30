
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

from kubedock.usage.models import db, ContainerState


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Filling "kubes" field in old container states...')

    for cs in ContainerState.query.all():
        containers = cs.pod.get_dbconfig('containers')
        try:
            cs.kubes = (container.get('kubes', 1) for container in containers
                        if container['name'] == cs.container_name).next()
        except StopIteration:
            upd.print_log('Container not found: {0}'.format(cs.container_name))
    db.session.commit()


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('No downgrade needed')
