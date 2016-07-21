import os

import yaml


def resolve_path(path, wd=None):
    if os.path.isabs(path):
        return path
    else:
        if wd is not None:
            return os.path.join(wd, path)
        else:
            return os.path.expanduser(path)


def read_yaml(filename):
    with open(filename) as f:
        d = yaml.load(f)
    return d


def save_yaml(d, filename):
    dir_name = os.path.dirname(os.path.abspath(filename))
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    with open(filename, 'w') as f:
        yaml.safe_dump(d, f, default_flow_style=False)


def chmod(filename, mode):
    os.chmod(filename, mode)


def ensure_dir(path):
    if os.path.isdir(path):
        return
    os.makedirs(path)
