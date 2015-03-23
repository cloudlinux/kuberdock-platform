class Image(object):
    
    def __init__(self, data):
        super(Image, self).__setattr__('_data', data)
        
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
        
def main(**kw):
    pass