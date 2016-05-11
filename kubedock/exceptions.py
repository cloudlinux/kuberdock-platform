"""
Defines and exports global kuberdock exceptions:
APIError, PermissionDenied, NotAuthorized
"""


class APIError(Exception):
    message = 'Unknown error'
    status_code = 400

    def __init__(self, message=None, status_code=None, type=None):
        if message is not None:
            self.message = message
        if status_code is not None:
            self.status_code = status_code
        if type is not None:
            self.type = type

    def __str__(self):
        # Only message because this class may wrap other exception classes
        return self.message

    def __repr__(self):
        return '<{0}: "{1}" ({2})>'.format(
            self.__class__.__name__, self.message, self.status_code)


class PermissionDenied(APIError):
    status_code = 403

    def __init__(self, message=None, status_code=None, type=None):
        if message is None:
            message = "Insufficient permissions for requested action"
        super(PermissionDenied, self).__init__(message, status_code, type)


class NotAuthorized(APIError):
    message = 'Not Authorized'
    status_code = 401