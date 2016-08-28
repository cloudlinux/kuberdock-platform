"""
DNS Management Plugin for Amazon Route 53

Usage of this plugin is not restricted to KuberDock on AWS and can be used on
  any kind of KuberDock setup

API reference: http://boto.cloudhackers.com/en/latest/ref/route53.html
"""

from . import entry

ALLOWED_ARGS = ['id', 'secret']


def is_valid_arg(name, value):
    """Checks if given argument is valid.
    """
    if name not in ALLOWED_ARGS:
        return False, u'Unknown parameter "{}"'.format(name)
    if not value:
        return False, u'Empty parameter value "{}"'.format(value)
    return True, None
