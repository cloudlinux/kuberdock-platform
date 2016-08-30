"""
Defines and exports global kuberdock exceptions
"""
import sys
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
        return unicode(self.message_template).format(**self.details)

    def __str__(self):
        # Only message because this class may wrap other exception classes
        return str(self.message)

    def __repr__(self):
        return '<{0}: "{1}" ({2})>'.format(
            self.__class__.__name__, self.message, self.status_code)


class InternalAPIError(APIError):
    """Message of this type is not shown to user, but to admin only."""
    __metaclass__ = ABCMeta
    status_code = 500
    response_message = 'Internal error, please contact administrator'
    message_template = '{excType}: {excValue}'

    def __init__(self, message=None, status_code=None, type=None,
                 details=None, response_message=None, exc_info=None):
        """Here is one additional parameter 'response_message'.
        If it is defined, then APIError will contain this message, instead
        of one defined on class level.
        """
        super(InternalAPIError, self).__init__(
            message=message, status_code=status_code, type=type,
            details=details)

        if response_message:
            self.response_message = response_message
        self.exc_info = exc_info
        if self.exc_info:
            self.details['excType'] = exc_info[0].__name__
            self.details['excValue'] = exc_info[1].message

    @classmethod
    def from_exc(cls, exc_type, exc_value, traceback):
        return cls(exc_info=(exc_type, exc_value, traceback))


class SubsystemtIsNotReadyError(InternalAPIError):
    """Raise this exception if some subsystemt did not properly configured."""
    pass


class PermissionDenied(APIError):
    message_template = 'Insufficient permissions for requested action'
    status_code = 403


class NotAuthorized(APIError):
    message_template = 'Not Authorized'
    status_code = 401


class NotFound(APIError):
    message_template = 'Not found'
    status_code = 404


class DomainNotFound(NotFound):
    message_template = 'Domain not found'


class NoFreeIPs(APIError):
    message_template = ('There are no free public IP-addresses, contact '
                        'KuberDock administrator')


class NoSuitableNode(APIError):
    message_template = ('There are no suitable nodes for the pod. Please try '
                        'again later or contact KuberDock administrator')


class PodStartFailure(APIError):
    message_template = 'Could not start pod'


class InsufficientData(APIError):
    message_template = 'Supplied data are incomplete'


class PredefinedAppExc(object):

    class NoSuchPredefinedApp(APIError):
        message_template = 'No such predefined app'
        status_code = 404

    class NoSuchAppPackage(APIError):
        message_template = 'No such app package'
        status_code = 404

    class UnparseableTemplate(APIError):
        message_template = 'Unable to parse template'

    class InvalidTemplate(APIError):
        message_template = 'Invalid template structure'

    class NotPredefinedAppPod(APIError):
        message_template = 'Pod not created from predefined app'

    class InternalPredefinedAppError(InternalAPIError):
        message_template = 'An internal error occurred: {message}'

    class AppPackageChangeImpossible(APIError):
        message_template = 'Unable to change app package: {message}'


class BillingExc(object):

    class BillingError(APIError):
        message_template = 'Billing could not process request'

    class InternalBillingError(InternalAPIError):
        message_template = 'An internal error occurred: {message}'


class AlreadyExistsError(APIError):
    message_template = 'Resource already exists'
    status_code = 409


class CannotBeDeletedError(APIError):
    message_template = 'Resource cannot be deleted'
    status_code = 409
