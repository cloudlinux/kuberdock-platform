
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import json


class ConfigMapClient(object):
    def __init__(self, k8s_query):
        """:type k8s_query: kubedock.kapi.helpers.KubeQuery"""
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

    def delete(self, name, namespace):
        resp = self._k8s_query.delete(['configmaps', name], ns=namespace)
        return self._process_response(resp)

    @classmethod
    def _process_response(cls, resp):
        if resp['kind'] != 'Status':
            return resp

        if resp['kind'] == 'Status':
            if resp['status'] == 'Success':
                return resp

            if resp['status'] == 'Failure':
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
