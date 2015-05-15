def quantities_converter(value, suffix, return_type):
    """
    Read https://github.com/GoogleCloudPlatform/kubernetes/blob/master/docs/resources.md#resource-quantities
    :param value: original value from kubernetes, e.g.: 64Mi
    :param suffix:
    :param return_type:
    :return:
    """
    if isinstance(value, basestring):
        if suffix == 'Mi' and return_type == int:
            return return_type(int(value.replace(suffix, '')) * 1024 * 1024)
    return value


class PodEntity(object):
    uid = None
    id = None
    name = None
    status = None
    cluster = False
    replicas = 1
    servicename = None
    owner = None
    _images = None

    def __init__(self, data, replicas=None):
        self.data = data
        self._replicas = replicas
        self._proceed_data()

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __repr__(self):
        return self.to_dict().__repr__()

    def _proceed_data(self):
        # metadata
        metadata = self._metadata()
        self.uid = metadata['uid']
        self.id = metadata['name']
        self.name = metadata['labels']['name']
        self.labels = metadata['labels']
        self.namespace = metadata['namespace']
        # status
        status = self.data['status']
        self.status = status['phase']
        self.pod_ip = status.get('podIP', '')
        # spec
        spec = self._spec()
        self.host = spec['host']
        self.kube_type = spec['nodeSelector']['kuberdock-kube-type']
        self.dockers = self._dockers_wrapper()
        self.containers = self._containers_wrapper()
        self.volumes = self._volumes_wrapper()

    def _dockers_wrapper(self):
        if not self.is_running or 'status' not in self.data:
            return []
        dockers = []
        self._images = {}
        for container in self.data['status'].get('containerStatuses', []):
            if not container.get('name') or container['name'] == 'POD':
                continue
            self._images[container['name']] = container['imageID']
            dockers.append({
                'host': self.host,
                'info': container,
                'podIP': self.pod_ip
            })
        return dockers

    def _containers_wrapper(self):
        containers = self.data['spec']['containers']

        def container_wrapper(c):
            memory = c.get(
                'resources', {}).get(
                'limits', {}).get(
                'memory', '0Mi')
            data = dict(
                resources=c.get('resources', {}),
                terminationMessagePath=c.get('terminationMessagePath', ''),
                name=c.get('name', ''),
                imagePullPolicy=c.get('imagePullPolicy', ''),
                command=c.get('args', []),  # TODO: refactor
                image=c.get('image', ''),
                memory=quantities_converter(memory, 'Mi', int),
                volumeMounts=c.get('volumeMounts'),
                ports=c['ports'], capabilities=c['capabilities']
            )
            return data

        data = [container_wrapper(c) for c in containers]
        if self.is_running and self._images:
            for c in data:
                c['imageID'] = self._images.get(c['name'])
        return data

    def _volumes_wrapper(self):
        volumes = self.data['spec']['volumes']

        def volume_wrapper(v):
            data = dict(
                name=v.get('name', ''),
                source=dict(
                    glusterfs=v.get('glusterfs'),
                    gitRepo=v.get('gitRepo'),
                    hostDir=v.get('hostPath'),                  # TODO: refactor
                    persistentDisk=v.get('gcePersistentDisk'),  # TODO: refactor
                    emptyDir=v.get('emptyDir', {}),
                    nfs=v.get('nfs'),
                    iscsi=v.get('iscsi'),
                    awsElasticBlockStore=v.get('awsElasticBlockStore'),
                    secret=v.get('secret')
                )
            )
            return data

        return [volume_wrapper(v) for v in volumes]

    def _metadata(self, k=None):
        if k:
            return self.data['metadata'][k]
        return self.data['metadata']

    def _spec(self, k=None):
        if k:
            return self.data['spec'][k]
        return self.data['spec']

    @staticmethod
    def _is_related(one, two):
        if one is None or two is None:
            return False
        for k in two.keys():
            if k not in one:
                return False
            if one[k] != two[k]:
                return False
            return True

    @property
    def is_running(self):
        return self.data['status']['phase'] == 'Running'

    @property
    def is_pending(self):
        return self.data['status']['phase'] == 'Pending'

    def to_dict(self):
        pid = self.id
        pod_labels = self.labels

        data = dict(
            id=self.uid,
            name=self.name,
            sid=pid,
            cluster=self.cluster,
            replicas=self.replicas,
            status=self.status.lower(),
            dockers=self.dockers,
            containers=self.containers,
            volumes=self.volumes,
            labels=pod_labels
        )
        if self._replicas:
            for r in self._replicas:  # iterating through replicas list received earlier
                if self._is_related(r['replicaSelector'], pod_labels):
                    self.cluster = True
                    for f in 'id', 'sid', 'replicas':
                        setattr(self, f, r[f])
                    break

        return data


class ServiceEntity(object):
    def __init__(self, data):
        self.data = data
        self._proceed_data()

    def _proceed_data(self):
        metadata = self._metadata()
        self.uid = metadata['uid']
        self.id = metadata['name']
        self.labels = metadata['labels']
        self.service_name = metadata['labels'].get('name', '')
        self.namespace = metadata['namespace']
        # spec
        spec = self._spec()
        self.ports = spec['ports']
        self.portal_ip = spec['portalIP']
        self.selector = spec['selector']

    def _metadata(self, k=None):
        if k:
            return self.data['metadata'][k]
        return self.data['metadata']

    def _spec(self, k=None):
        if k:
            return self.data['spec'][k]
        return self.data['spec']
