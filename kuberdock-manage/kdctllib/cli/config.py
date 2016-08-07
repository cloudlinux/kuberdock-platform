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
