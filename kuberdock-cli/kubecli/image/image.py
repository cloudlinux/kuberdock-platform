from ..helper import KubeQuery, PrintOut

class Image(KubeQuery, PrintOut, object):

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
                try:
                    self._data['ports'][index].update({name: attr})
                except IndexError:
                    self._data['ports'].append({name: attr})

    def _conf_mount_point(self, name, attr, index):
        if 'volumeMounts' not in self._data:
            self._data['volumeMounts'] = [{name: attr}]
        else:
            if not len(self._data['volumeMounts']):
                self._data['volumeMounts'].append({name: attr})
            else:
                try:
                    self._data['volumeMounts'][index].update({name: attr})
                except IndexError:
                    self._data['volumeMounts'].append({name: attr})


    def set_container_port(self, port, index=0):
        self._conf_port('containerPort', port, index)

    def set_host_port(self, port, index=0):
        self._conf_port('hostPort', port, index)

    def set_protocol(self, proto, index=0):
        self._conf_port('protocol', proto, index)

    def set_public(self, public, index=0):
        self._conf_port('isPublic', public, index)

    def set_mount_path(self, path, index=0):
        self._conf_mount_point('mountPath', path, index)

    def _get_registry(self):
        if self.registry.startswith('http'):
            return self.registry
        return 'http://' + self.registry

    def search(self):
        payload={
            'url': self._get_registry(),
            'searchkey': self.search_string,
            'page': self.page}
        data = self._unwrap(self._get('/api/images/search', payload))
        self._list(data)

    def ps(self):
        super(Image, self).__setattr__('_FIELDS', (('image', 32),))
        data = self._unwrap(self._get('/api/podapi'))[0]
        containers = data.get('containers', [])
        self._list(containers)

    def get(self):
        try:
            data = self._unwrap(self._post('/api/images/new', {'image': self.image}))
        except (AttributeError, TypeError):
            data = {'volumeMounts': [], 'command': [], 'env': [], 'ports': []}
        self._list(data)