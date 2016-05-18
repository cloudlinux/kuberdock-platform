import os
from copy import copy

import yaml

from ..kdclient import KDClient


class KDCtlError(Exception):
    message = 'Some error occurred.'

    def __init__(self, message=None):
        if message:
            self.message = message

    def __str__(self):
        return self.message


class TokenNotFound(KDCtlError):
    message = 'Token not found. Probably you need authorize first.'


class LoginRequired(KDCtlError):
    message = 'Login required.'


class ConfigManager(object):
    TOKEN_FILE_MODE = 0o600
    TOKEN_FILE_NAME = 'token.yaml'
    CONFIG_FILE_NAME = 'config.yaml'
    DEFAULT_CONFIG_DIR = '~/.kuberdock-manage'
    DEFAULT_CONFIG = {
        'url': 'http://127.0.0.1'
    }

    def __init__(self, config_dir=None):
        config_dir = config_dir or self.DEFAULT_CONFIG_DIR
        self.config_dir = os.path.expanduser(config_dir)

    def get_config(self):
        conf = copy(self.DEFAULT_CONFIG)
        conf.update(self._read_yaml(
            self._resolve_path(self.CONFIG_FILE_NAME)
        ))
        return conf

    def save_config(self, config):
        path = self._resolve_path(self.CONFIG_FILE_NAME)
        self._save_yaml(config, path)

    def get_token(self):
        d = self._read_yaml(
            self._resolve_path(self.TOKEN_FILE_NAME)
        )
        if 'user' not in d or 'token' not in d:
            raise TokenNotFound
        return d['user'], d['token']

    def save_token(self, user, token):
        d = {
            'user': user,
            'token': token
        }
        filename = self._resolve_path(self.TOKEN_FILE_NAME)
        self._save_yaml(d, filename)
        self._chmod(filename, self.TOKEN_FILE_MODE)

    def _resolve_path(self, filename):
        if os.path.isabs(filename):
            return filename
        else:
            return os.path.join(self.config_dir, filename)

    @staticmethod
    def _read_yaml(filename):
        try:
            with open(filename) as f:
                d = yaml.load(f)
            return d
        except IOError:
            return {}

    @staticmethod
    def _save_yaml(d, filename):
        dir_name = os.path.dirname(os.path.abspath(filename))
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
        with open(filename, 'w') as f:
            yaml.safe_dump(d, f, default_flow_style=False)

    @staticmethod
    def _chmod(filename, mode):
        os.chmod(filename, mode)


class KDCtl(object):
    def __init__(self, config_dir):
        self.cm = ConfigManager(config_dir)
        self._config = None
        self._client = None
        self._token = None

    @property
    def config(self):
        if not self._config:
            self._config = self.cm.get_config()
        return self._config

    @property
    def client(self):
        if not self._client:
            self._client = KDClient(self.config['url'], token=self.token)
        return self._client

    @property
    def token(self):
        if not self._token:
            try:
                _, self._token = self.cm.get_token()
            except TokenNotFound:
                raise LoginRequired
        return self._token

    def login(self, username, password):
        config = self.config
        client = KDClient(config['url'], username, password)
        token = client.auth.token()['token']
        self.cm.save_token(username, token)
        self._token = token

    def update_config(self, **kwargs):
        self.config.update(**kwargs)
        self.cm.save_config(self.config)
        return self.config
