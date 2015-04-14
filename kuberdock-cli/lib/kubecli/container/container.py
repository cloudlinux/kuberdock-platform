from ..helper import KubeQuery, PrintOut

    
class Container(KubeQuery, PrintOut, object):
    """
    Class for creating JSON structure for passing to KuberDock API
    """
    
    def __init__(self, **args):
        """
        Constructor
        """
        for key, val in args.items():
            setattr(self, key, val)
    
    @staticmethod
    def _transform(data):
        ready = ['name', 'status']
        out = dict([(k, v) for k, v in data.items() if k in ready])
        out['labels'] = ','.join(
            ['{0}={1}'.format(k, v) for k, v in data.get('labels', {}).items()])
        out['images'] = ','.join(
            [i.get('image', 'imageless') for i in data.get('containers', [])])
        return out
    
    def get(self):
        """
        Gets a list of user pods and prints either all or one
        """
        self._WANTS_HEADER = True
        self._FIELDS = (('name', 32), ('images', 32), ('labels', 64), ('status', 10))
        data = self._unwrap(self._get('/api/pods/'))
        if hasattr(self, 'name'):
            self._list([self._transform(i) for i in data if i['name'] == self.name])
        else:
            self._list([self._transform(i) for i in data])
            
    def describe(self):
        """
        Gets a list of user pods, filter out one of them by name and prints it
        """
        data = self._unwrap(self._get('/api/pods/'))
        try:
            self._show([i for i in data if i['name'] == self.name][0])
        except IndexError:
            print "No such item"
    
    def delete(self):
        """
        Gets a list of user pods, filter out one of them by name and prints it
        """
        data = self._unwrap(self._get('/api/pods/'))
        try:
            item = [i for i in data if i['name'] == self.name][0]
            self._delete('/api/pods/' + item['id'])
        except (IndexError, KeyError):
            print "No such item"
        