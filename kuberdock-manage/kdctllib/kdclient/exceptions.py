class APIError(Exception):
    def __init__(self, json):
        self.json = json


class UnknownAnswer(Exception):
    def __init__(self, text, status_code):
        self.text = text
        self.status_code = status_code

    def as_dict(self):
        return {
            'text': self.text,
            'status_code': self.status_code
        }
