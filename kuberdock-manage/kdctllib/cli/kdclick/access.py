import collections

ADMIN = 'admin'
USER = 'user'
ALL = '__all__'

CURRENT_ROLE = ADMIN


def available_for(roles):
    if isinstance(roles, basestring):
        roles = (roles,)
    elif isinstance(roles, collections.Iterable):
        pass
    elif roles is None:
        return False
    else:
        raise ValueError('Roles must be instance of basestring '
                         'or collections.Iterable')

    return CURRENT_ROLE in roles or ALL in roles
