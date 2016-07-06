from .auth import AuthClient
from .backup import BackupClient
from .ippool import IPPoolClient
from .nodes import NodesClient
from .pstorage import PStorageClient
from .podapi import PodAPIClient
from .predefined_apps import PredefinedAppsClient
from .restore import RestoreClient
from .system_settings import SystemSettingsClient
from .users import UsersClient
from .utils import Transport
from .license import LicenseClient


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
        self.auth = AuthClient(self)
        self.backup = BackupClient(self)
        self.ippool = IPPoolClient(self)
        self.nodes = NodesClient(self)
        self.pstorage = PStorageClient(self)
        self.pods = PodAPIClient(self)
        self.predefined_apps = PredefinedAppsClient(self)
        self.restore = RestoreClient(self)
        self.system_settings = SystemSettingsClient(self)
        self.users = UsersClient(self)
        self.license = LicenseClient(self)
