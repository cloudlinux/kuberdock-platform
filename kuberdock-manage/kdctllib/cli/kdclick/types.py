import json as _json

import yaml as _yaml


def json(string):
    return _json.loads(string)


def text(string):
    return str(string)


def yaml(string):
    return _yaml.load(string)
