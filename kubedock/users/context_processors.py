from flask import session
from flask.ext.login import current_user as u


def users_helpers():
    context = dict(
        auth_by_id=session.get('auth_by_another'),
        username=u.username if u.is_authenticated() else 'Anonymous',
        user_settings=u.get_settings() if u.is_authenticated() else {},
        user_profile=\
            u.to_dict(for_profile=True) if u.is_authenticated() else {},
    )
    return context
