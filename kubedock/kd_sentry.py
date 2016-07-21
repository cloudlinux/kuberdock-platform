"""Module for all sentry related code"""
from raven.processors import SanitizePasswordsProcessor


class KuberDockSanitize(SanitizePasswordsProcessor):
    """Beside from default SanitizePasswordsProcessor algorith, also
    search key-values in query-like strings.
    Sanitize 'email' and 'token' in additional to default fields.

    """
    FIELDS = frozenset([
        'password',
        'secret',
        'passwd',
        'authorization',
        'api_key',
        'apikey',
        'sentry_dsn',
        'access_token',
        'email',
        'token'
    ])

    def sanitize(self, key, value):
        new_value = super(KuberDockSanitize, self).sanitize(key, value)
        if new_value == value and isinstance(value, str) and '=' in value:
            new_value = self._sanitize_keyvals(value, '&')
        return new_value
