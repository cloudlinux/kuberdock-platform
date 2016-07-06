"""
Defines and exports global kuberdock exceptions:
APIError, PermissionDenied, NotAuthorized
"""


class APIError(Exception):
    message = 'Unknown error'
    status_code = 400
    details = None

    def __init__(self, message=None, status_code=None, type=None,
                 details=None):
        if message is not None:
            self.message = message
        if status_code is not None:
            self.status_code = status_code
        if type is not None:
            self.type = type
        self.details = details

    def __str__(self):
        # Only message because this class may wrap other exception classes
        return str(self.message)

    def __repr__(self):
        return '<{0}: "{1}" ({2})>'.format(
            self.__class__.__name__, self.message, self.status_code)


class PermissionDenied(APIError):
    message = "Insufficient permissions for requested action"
    status_code = 403


class NotAuthorized(APIError):
    message = 'Not Authorized'
    status_code = 401


class NoFreeIPs(APIError):
    message = 'There are no free public IP-addresses, contact KuberDock ' \
              'administrator'
