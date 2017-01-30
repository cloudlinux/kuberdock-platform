
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

from flask import g, has_request_context
from kubedock.exceptions import APIError
from kubedock.utils import API_VERSIONS


class ValidationError(APIError):
    # TODO: change all ValidationError(message) calls to
    #   ValidationError(*details) or use different exception

    def __init__(self, data=None, **kwargs):
        # in api-v1 we have non-strings in `data`,
        # in api-v2 all that stuff should be in `details`
        self.legacy = data is not None and not isinstance(data, basestring)
        if data is not None:
            if self.legacy:
                kwargs['details'] = dict(data, **kwargs)
            else:
                self.error_message = data
        super(ValidationError, self).__init__(**kwargs)

    @property
    def message(self):
        if (self.legacy and has_request_context() and g.get('api_version') and
                g.api_version == API_VERSIONS.v1):
            return self.details  # legacy for v1: return dict in message
        if getattr(self, 'error_message', None) is not None:
            return self.error_message  # raise ValidateError('error message')
        if self.details:  # raise ValidateError(details={'smth': 'wrong'})
            return u'Invalid data: {0}'.format(
                json.dumps(self.details, ensure_ascii=False))
        return u'Invalid data'  # raise ValidateError()
