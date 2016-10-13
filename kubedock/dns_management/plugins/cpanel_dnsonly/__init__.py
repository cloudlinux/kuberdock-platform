from . import entry  # noqa

ALLOWED_ARGS = ['host', 'user', 'token']


def is_valid_arg(name, value):
    """Checks if given argument is valid.
    """
    if name not in ALLOWED_ARGS:
        return False, u'Unknown parameter "{}"'.format(name)
    if not value:
        return False, u'Empty parameter value "{}"'.format(value)
    return True, None
