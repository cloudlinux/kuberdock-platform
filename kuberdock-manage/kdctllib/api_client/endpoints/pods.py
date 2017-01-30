
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

from ..base import ClientBase


class PodsClient(ClientBase):
    endpoint = '/podapi'

    def list(self, owner=None):
        return self.transport.get(
            self._url(),
            params={'owner': owner}
        )

    def get(self, id, owner=None):
        return self.transport.get(
            self._url(id),
            params={'owner': owner}
        )

    def create(self, data, owner=None):
        return self.transport.post(
            self._url(),
            params={'owner': owner},
            json=data
        )

    def update(self, id, data):
        # todo: add parameter "owner" in api/v2
        return self.transport.put(
            self._url(id),
            json=data
        )

    def delete(self, id, owner=None):
        return self.transport.delete(
            self._url(id),
            params={'owner': owner}
        )

    def dump(self, pod_id):
        return self.transport.get(
            self._url(pod_id, 'dump')
        )

    def batch_dump(self, owner=None):
        return self.transport.get(
            self._url('dump'),
            params={'owner': owner}
        )

    def restore(self, pod_dump, owner, pv_backups_location=None,
                pv_backups_path_template=None):
        return self.transport.post(
            self._url('restore'),
            json={
                'pod_dump': pod_dump,
                'owner': owner,
                'pv_backups_location': pv_backups_location,
                'pv_backups_path_template': pv_backups_path_template,
            }
        )
