
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

from ..api_common import (PODAPI_PATH, IMAGES_PATH)
from ..helper import KubeQuery, PrintOut


class Image(object):
    def __init__(self, data=None, **kw):
        self.as_json = kw.get('json', False)
        self.data = data or {}
        self.query = KubeQuery(jsonify_errors=self.as_json, **kw)
        for attr, value in kw.iteritems():
            setattr(self, attr, value)

    def _get_registry(self):
        registry = self.data.get('registry', '')
        if registry.startswith('http'):
            return registry
        return 'http://' + registry

    def search(self):
        payload = {
            'url': self._get_registry(),
            'searchkey': self.data.get('search_string', ''),
            'page': self.data.get('page', 1)
        }
        data = self.query.unwrap(self.query.get(IMAGES_PATH, payload))
        fields = (('name', 24), ('description', 76))
        printout = PrintOut(as_json=self.as_json, fields=fields)
        if not self.as_json:
            data = [dict((k, v) for k, v in i.items()
                         if k in ['name', 'description'])
                    for i in data]
        printout.show_list(data)

    def ps(self):
        data = self.query.unwrap(self.query.get(PODAPI_PATH))[0]
        containers = data.get('containers', [])
        printout = PrintOut(as_json=self.as_json, fields=(('image', 32),))
        printout.show_list(containers)

    def get(self):
        try:
            data = self.query.unwrap(self.query.post(
                IMAGES_PATH + 'new', {'image': self.data.get('image', '')}))
        except (AttributeError, TypeError):
            data = {'volumeMounts': [], 'command': [], 'env': [], 'ports': []}
        printout = PrintOut(as_json=self.as_json)
        printout.show(data)
