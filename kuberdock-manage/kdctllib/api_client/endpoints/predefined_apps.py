
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


class PredefinedAppsClient(ClientBase):
    endpoint = '/predefined-apps'

    def list(self, file_only=False):
        params = {'file-only': file_only}

        return self.transport.get(
            self._url(),
            params=params
        )

    def get(self, id, file_only=False):
        params = {'file-only': file_only}

        return self.transport.get(
            self._url(id),
            params=params
        )

    def create(self, name, origin, template, validate=None):
        json = {
            'name': name,
            'origin': origin,
            'template': template,
            'validate': validate,
        }
        return self.transport.post(
            self._url(),
            json=json
        )

    def update(self, id, template=None, validate=None):
        json = {
            'template': template,
            'validate': validate,
        }
        return self.transport.put(
            self._url(id),
            json=json
        )

    def delete(self, id):
        return self.transport.delete(
            self._url(id)
        )

    def validate_template(self, template):
        endpoint = 'validate-template'

        json = {'template': template}
        return self.transport.post(
            self._url(endpoint),
            json=json
        )

    def create_pod(self, template_id, plan_id, data, owner=None):
        # redirect to yaml_api
        return self._YamlClient(self.client) \
            .create_pod(template_id, plan_id, data, owner)

    class _YamlClient(ClientBase):
        endpoint = '/yamlapi'

        def create_pod(self, template_id, plan_id, data, owner=None):
            if owner:
                data.update(owner=owner)
            return self.transport.post(
                self._url('create', template_id, plan_id),
                json=data
            )
