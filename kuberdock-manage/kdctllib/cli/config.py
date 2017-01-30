
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

from utils import file_utils


class ConfigManager(object):
    config_file_name = 'config.yaml'

    def __init__(self, config_dir, default_config):
        self.config_dir = file_utils.resolve_path(config_dir)
        self.default_config = default_config

    def get_config(self):
        config_path = file_utils.resolve_path(self.config_file_name,
                                              self.config_dir)
        try:
            conf = file_utils.read_yaml(config_path)
        except IOError:
            conf = self.default_config
        else:
            if not conf:
                conf = self.default_config
        return conf

    def save_config(self, config):
        path = file_utils.resolve_path(self.config_file_name, self.config_dir)
        file_utils.save_yaml(config, path)


class TokenManager(object):
    token_file_mode = 0o600
    token_file_name = 'token.yaml'

    def __init__(self, token_dir):
        self.token_dir = file_utils.resolve_path(token_dir)

    def get_token(self):
        try:
            d = file_utils.read_yaml(
                file_utils.resolve_path(self.token_file_name, self.token_dir))
        except IOError:
            raise self.TokenNotFound
        if 'token' not in d:
            raise self.TokenNotFound
        return d['token']

    def save_token(self, token):
        d = {'token': token}
        filename = file_utils.resolve_path(self.token_file_name,
                                           self.token_dir)
        file_utils.save_yaml(d, filename)
        file_utils.chmod(filename, self.token_file_mode)

    class TokenNotFound(Exception):
        pass
