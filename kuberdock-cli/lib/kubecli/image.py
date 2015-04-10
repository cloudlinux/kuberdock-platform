import json
from .utils import kubeQuery

class Image(kubeQuery, object):
    
    def __init__(self, data=None, **kw):
        if data is None:
            data = {}
        super(Image, self).__setattr__('_data', data)
        for attr, value in kw.items():
            super(Image, self).__setattr__(attr, value)
        
    def __getattr__(self, name):
        return self._data.get(name)

    def __setattr__(self, name, value):
        self._data[name] = value
        
    def _conf_port(self, name, attr, index):
        if 'ports' not in self._data:
            self._data['ports'] = [{name: attr}]
        else:
            if not len(self._data['ports']):
                self._data['ports'].append({name: attr})
            else:
                self._data['ports'][index].update({name: attr})
            
        
    def set_container_port(self, port, index=0):
        self._conf_port('containerPort', port, index)
        
    def set_host_port(self, port, index=0):
        self._conf_port('hostPort', port, index)
        
    def set_protocol(self, proto, index=0):
        self._conf_port('protocol', proto, index)
        
    def _get_registry(self):
        if self.registry.startswith('http'):
            return self.registry
        return 'http://' + self.registry
        
    def search(self):
        try:
            payload={
                'url': self.registry,
                'searchkey': self.search_string,
                'page': self.page}

            data = self.get('/api/images/search', payload)['data']
            if self.json:
                print json.dumps(data)
            else:
                for i in data:
                    print i['name']
        except (ValueError, TypeError, KeyError), e:
            raise SystemExit(str(e))
        
    def do_nothing(self):
        pass
    
        
def main(**kw):
    i = Image(**kw)
    dispatcher = {
        'search': i.search,
        'nope': i.do_nothing}
    
    dispatcher.get(kw['i_action'], 'nope')()
