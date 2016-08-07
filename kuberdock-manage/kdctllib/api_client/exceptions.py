class APIError(Exception):
    """Raised on ordinal api error with expected structure."""
    def __init__(self, json):
        self.json = json
        super(APIError, self).__init__(json)


class UnknownAnswer(Exception):
    """Raised when answer cannot be parsed as json."""
    def __init__(self, text, status_code):
        self.text = text
        self.status_code = status_code
        super(UnknownAnswer, self).__init__(text, status_code)

    def as_dict(self):
        return {
            'text': self.text,
            'status_code': self.status_code
        }
