class GenericPluginError(Exception):
    def __init__(self, message='Generic API error', response=None):
        super(GenericPluginError, self).__init__(message)
        self.response = response


class UnexpectedResponse(GenericPluginError):
    pass


class ZoneDoesNotExist(GenericPluginError):
    pass
