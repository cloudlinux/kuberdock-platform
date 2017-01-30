
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

from endpoints.allowed_ports import AllowedPortsClient
from endpoints.auth import AuthClient
from endpoints.domains import DomainsClient
from endpoints.ippool import IPPoolClient
from endpoints.images import ImagesClient
from endpoints.nodes import NodesClient
from endpoints.pods import PodsClient
from endpoints.predefined_apps import PredefinedAppsClient
from endpoints.pricing import PricingClient
from endpoints.pstorage import PStorageClient
from endpoints.restricted_ports import RestrictedPortsClient
from endpoints.stats import StatsClient
from endpoints.system_settings import SystemSettingsClient
from endpoints.users import UsersClient
from transport import Transport


class KDClient(object):
    endpoint = '/api'

    def __init__(self, url, user=None, password=None, token=None):
        """
        Use 'user/password' for access to auth.token and auth.token2,
        otherwise use 'token'.

        Args:
            url: Url
            user: User
            password: Password
            token: Token
        """
        self.transport = Transport(url, user, password, token)
        self.allowed_ports = AllowedPortsClient(self)
        self.auth = AuthClient(self)
        self.domains = DomainsClient(self)
        self.images = ImagesClient(self)
        self.ippool = IPPoolClient(self)
        self.nodes = NodesClient(self)
        self.pstorage = PStorageClient(self)
        self.pods = PodsClient(self)
        self.predefined_apps = PredefinedAppsClient(self)
        self.pricing = PricingClient(self)
        self.restricted_ports = RestrictedPortsClient(self)
        self.stats = StatsClient(self)
        self.system_settings = SystemSettingsClient(self)
        self.users = UsersClient(self)

    @property
    def token(self):
        return self.transport.token

    @token.setter
    def token(self, value):
        self.transport.token = value
