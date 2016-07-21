"""
Defines and exports global kuberdock exceptions
"""
from abc import ABCMeta


class APIError(Exception):
    """
    Base API error class. DO NOT USE IT DIRECTLY. Create inheritors.

    :param message_template: Template for human-readable `message`.
        Will be filled with `details` by `str.format`.
    :param status_code: HTTP status code
    :param type: Error type. Do not use this unless you really have to.
        Create inheritors.
    :param details: Object with data for machines. Use camelCase here.

    """
    message_template = 'Unknown error'
    status_code = 400

    def __init__(self, message=None, status_code=None, type=None,
                 details=None):
        if message is not None:
            self._message = message

        if status_code is not None:
            self.status_code = status_code

        if type is not None:
            self.type = type
        elif not hasattr(self, 'type'):
            self.type = self.__class__.__name__

        if details is not None:
            self.details = details
        elif not hasattr(self, 'details'):
            self.details = {}

    @property
    def message(self):
        """Human-readable message"""
        if hasattr(self, '_message'):
            return self._message
        return self.message_template.format(**self.details)

    def __str__(self):
        # Only message because this class may wrap other exception classes
        return str(self.message)

    def __repr__(self):
        return '<{0}: "{1}" ({2})>'.format(
            self.__class__.__name__, self.message, self.status_code)


class InternalAPIError(APIError):
    """Message of this type is not shown to user, but to admin only.

    Do not use it directly. Create inheritors.
    """
    __metaclass__ = ABCMeta
    status_code = 500


class PermissionDenied(APIError):
    message_template = 'Insufficient permissions for requested action'
    status_code = 403


class NotAuthorized(APIError):
    message_template = 'Not Authorized'
    status_code = 401


class NotFound(APIError):
    message_template = 'Not found'
    status_code = 404


class NoFreeIPs(APIError):
    message_template = ('There are no free public IP-addresses, contact '
                        'KuberDock administrator')


class NoSuitableNode(APIError):
    message_template = ('There are no suitable nodes for the pod. Please try '
                        'again later or contact KuberDock administrator')
