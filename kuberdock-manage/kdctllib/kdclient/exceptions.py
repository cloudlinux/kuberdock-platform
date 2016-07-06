class APIError(Exception):
    def __init__(self, message, type_='Unknown', details=None):
        super(APIError, self).__init__(message)
        self.type = type_
        self.details = details
