from endpoints.allowed_ports import AllowedPortsClient
from endpoints.auth import AuthClient
from endpoints.ippool import IPPoolClient
from endpoints.images import ImagesClient
from endpoints.nodes import NodesClient
from endpoints.pods import PodsClient
from endpoints.predefined_apps import PredefinedAppsClient
from endpoints.pricing import PricingClient
from endpoints.pstorage import PStorageClient
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
        self.images = ImagesClient(self)
        self.ippool = IPPoolClient(self)
        self.nodes = NodesClient(self)
        self.pstorage = PStorageClient(self)
        self.pods = PodsClient(self)
        self.predefined_apps = PredefinedAppsClient(self)
        self.pricing = PricingClient(self)
        self.system_settings = SystemSettingsClient(self)
        self.users = UsersClient(self)

    @property
    def token(self):
        return self.transport.token

    @token.setter
    def token(self, value):
        self.transport.token = value
