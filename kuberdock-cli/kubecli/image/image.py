from ..api_common import (PODAPI_PATH, IMAGES_PATH)
from ..helper import KubeQuery, PrintOut


class Image(object):
    def __init__(self, data=None, **kw):
        self.as_json = kw.get('json', False)
        self.data = data or {}
        self.query = KubeQuery(jsonify_errors=self.as_json, **kw)
        for attr, value in kw.iteritems():
            setattr(self, attr, value)

    def _get_registry(self):
        registry = self.data.get('registry', '')
        if registry.startswith('http'):
            return registry
        return 'http://' + registry

    def search(self):
        payload = {
            'url': self._get_registry(),
            'searchkey': self.data.get('search_string', ''),
            'page': self.data.get('page', 1)
        }
        data = self.query.unwrap(self.query.get(IMAGES_PATH, payload))
        fields = (('name', 24), ('description', 76))
        printout = PrintOut(as_json=self.as_json, fields=fields)
        if not self.as_json:
            data = [dict((k, v) for k, v in i.items()
                         if k in ['name', 'description'])
                    for i in data]
        printout.show_list(data)

    def ps(self):
        data = self.query.unwrap(self.query.get(PODAPI_PATH))[0]
        containers = data.get('containers', [])
        printout = PrintOut(as_json=self.as_json, fields=(('image', 32),))
        printout.show_list(containers)

    def get(self):
        try:
            data = self.query.unwrap(self.query.post(
                IMAGES_PATH + 'new', {'image': self.data.get('image', '')}))
        except (AttributeError, TypeError):
            data = {'volumeMounts': [], 'command': [], 'env': [], 'ports': []}
        printout = PrintOut(as_json=self.as_json)
        printout.show(data)
