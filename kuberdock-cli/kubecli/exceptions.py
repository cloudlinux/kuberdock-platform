import json


class NotApplicable(SystemExit):
    def __init__(self, message, **kw):
        if kw.get('as_json', False):
            message = json.dumps({'status': 'ERROR', 'message': message})
        super(NotApplicable, self).__init__(message)