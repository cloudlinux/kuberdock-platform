
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

class APIError(Exception):
    """Raised on ordinal api error with expected structure."""
    def __init__(self, json):
        self.json = json
        super(APIError, self).__init__(json)


class UnknownAnswer(Exception):
    """Raised when answer cannot be parsed as json."""
    def __init__(self, text, status_code):
        self.text = text
        self.status_code = status_code
        super(UnknownAnswer, self).__init__(text, status_code)

    def as_dict(self):
        return {
            'text': self.text,
            'status_code': self.status_code
        }
