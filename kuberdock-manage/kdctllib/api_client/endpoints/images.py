
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


class ImagesClient(ClientBase):
    endpoint = '/images'

    def search(self, search_key, page=None, per_page=None, refresh_key=None,
               registry=None):
        params = {'searchkey': search_key}
        params.update(_filter_not_none(
            page=page, per_page=per_page, refresh_key=refresh_key,
            url=registry))

        return self.transport.get(
            self._url(),
            params=params
        )


def _filter_not_none(**kwargs):
    return {k: v for k, v in kwargs.items() if v is not None}
