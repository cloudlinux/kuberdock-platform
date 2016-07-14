from flask import g, has_request_context
from kubedock.exceptions import APIError
from kubedock.utils import API_VERSIONS


class ValidationError(APIError):
    message_template = 'Invalid schema'

    def __init__(self, data=None, **kwargs):
        # in api-v1 we have non-strings in `data`,
        # in api-v2 all that stuff should be in `details`
        self.legacy = data is not None and not isinstance(data, basestring)
        if data is not None:
            if self.legacy:
                kwargs['details'] = dict(data, **kwargs)
            else:
                self.message_template = data
        super(ValidationError, self).__init__(**kwargs)

    @property
    def message(self):
        if (self.legacy and has_request_context() and g.get('api_version') and
                g.api_version == API_VERSIONS.v1):
            return self.details
        return super(ValidationError, self).message
