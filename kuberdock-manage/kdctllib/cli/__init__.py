import json
import os
from copy import copy

import click
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
        'url': 'https://127.0.0.1'
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
    def __init__(self, config_dir, debug):
        self.cm = ConfigManager(config_dir)
        self._config = None
        self._client = None
        self._token = None
        self.debug = debug

        if debug:
            self._set_requests_logging()

    @classmethod
    def _set_requests_logging(cls):
        import logging
        logging.getLogger('requests_logger').setLevel(logging.DEBUG)

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

    def __getattr__(self, item):
        """Redirect to kdclient if method is not defined here"""
        m = getattr(self.client, item)
        if m:
            return m

        raise AttributeError


class IO(object):
    def __init__(self, json_only):
        self.json_only = json_only

    def out_text(self, text, **kwargs):
        """Print text. If `self.json_only` == True,
        then text will not be printed.
        :param text: Text to be prompted.
        :param kwargs: Is passed to `click.echo()`.
        """
        if not self.json_only:
            click.echo(text, **kwargs)

    def out_json(self, d, **kwargs):
        """Print dictionary as json.
        :param d: Dictionary to be printed.
        :param kwargs: Is passed to `click.echo()`.
        """
        assert isinstance(d, dict)

        message = json.dumps(d, indent=4, sort_keys=True)
        click.echo(message, **kwargs)

    def confirm(self, text, **kwargs):
        """Prompts for confirmation (yes/no question).
        Parameter `self.json_only` must be set to False, otherwise
        `click.UsageError` will be raised.
        :param text: Text to be prompted.
        :param kwargs: Is passed to `click.confirm()`.
        :return: True or False.
        """
        if self.json_only:
            raise click.UsageError(
                'Cannot perform confirmation in json-only mode')
        return click.confirm(text, **kwargs)

    def prompt(self, text, **kwargs):
        """Prompts a user for input.
        Parameter `self.json_only` must be set to False, otherwise
        `click.UsageError` will be raised.
        :param text: Text to be prompted.
        :param kwargs: Is passed to `click.prompt()`.
        :return: User input.
        """
        if self.json_only:
            raise click.UsageError(
                'Cannot perform user input in json-only mode')
        return click.prompt(text, **kwargs)
