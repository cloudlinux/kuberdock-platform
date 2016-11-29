import json


class ConfigMapClient(object):
    def __init__(self, k8s_query):
        self._k8s_query = k8s_query

    def get(self, name, namespace='default'):
        return self._process_response(
            self._k8s_query.get(['configmaps', name], ns=namespace))

    def patch(self, name, data, metadata=None, namespace='default'):
        config = self._prepare_config(data, metadata)

        return self._process_response(self._k8s_query.patch(
            ['configmaps', name], json.dumps(config), ns=namespace))

    def create(self, data, metadata=None, namespace='default'):
        config = self._prepare_config(data, metadata)

        return self._process_response(self._k8s_query.post(
            ['configmaps'], json.dumps(config), ns=namespace, rest=True))

    @staticmethod
    def _prepare_config(data, metadata):
        config = {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'data': {},
            'metadata': {}
        }

        if data is not None:
            config['data'] = data
        if metadata is not None:
            config['metadata'] = metadata

        return config

    @classmethod
    def _process_response(cls, resp):
        if resp['kind'] != 'Status':
            return resp

        if resp['kind'] == 'Status' and resp['status'] == 'Failure':
            if resp['code'] == 404:
                raise ConfigMapNotFound()
            elif resp['code'] == 409:
                raise ConfigMapAlreadyExists()
            raise K8sApiError(resp)

        raise UnexpectedResponse(resp)


class UnexpectedResponse(Exception):
    pass


class ConfigMapNotFound(KeyError):
    pass


class ConfigMapAlreadyExists(Exception):
    pass


class K8sApiError(Exception):
    pass
