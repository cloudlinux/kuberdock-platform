
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

import elasticsearch as elastic
from requests import RequestException

from flask import current_app

from ..nodes.models import Node
from ..pods.models import Pod
from ..users.models import User
from .service_pods import get_kuberdock_logs_pod_name
from ..settings import (
    ELASTICSEARCH_REST_PORT, KUBE_API_PORT, KUBE_API_HOST, KUBE_API_VERSION)

K8S_PROXY_PREFIX = 'api/{version}/proxy'.format(version=KUBE_API_VERSION)


class LogsError(Exception):
    CONNECTION_ERROR = 503
    INTERNAL_ERROR = 500
    NO_LOGS = 404
    POD_ERROR = 502
    UNKNOWN_ERROR = -1

    def __init__(self, message, error_code=UNKNOWN_ERROR):
        self.message = message
        self.error_code = error_code

    def __repr__(self):
        return 'LogsError("{0}", error_code={1})'.format(
            self.message, self.error_code,
        )


def execute_es_query(index, query, size, sort, host=None):
    """Composes and executes elasticsearch query.
    Answer will be converted to standard API answer structure.
    Exceptions will be correctly handled.
    :param index: elasticsearch index name
    :param size: restrict output to this number of records
    :param query: dict with query parameters (optional)
    :param sort: dict with sorting parameters (optional)
    :param host: node ip to use or None to search all nodes

    """
    if host is None:
        hosts = [item.hostname for item in Node.query.all()]
    else:
        node = Node.query.filter(Node.ip == host).first()
        if node:
            hosts = [node.hostname]
        else:
            hosts = []

    internal_user = User.get_internal()
    log_pods = Pod.query.filter(
        Pod.status != 'deleted',
        Pod.name.in_(get_kuberdock_logs_pod_name(item) for item in hosts),
        Pod.owner_id == internal_user.id
    ).all()

    # current_app.logger.debug('ES query. Hosts: {}'.format(hosts))
    # current_app.logger.debug(
    #     'ES query. log pods: {}'.format([pod.name for pod in log_pods])
    # )

    es_service_hosts = []
    # Access to logs service via k8s proxy.
    # The final url will be like:
    # 'http://localhost:8080/api/v1/proxy/namespaces/
    #       008d1a30-1a79-473d-964a-5418f3f6d238/services/service-h0qc4:9200/'
    # It may be tested via curl from master host (with actual namespace and
    # service name).
    # It makes unnecessary to install and configure kube-proxy service on
    # master host to access k8s services.
    for pod in log_pods:
        config = pod.get_dbconfig()
        try:
            service = config['service']
            namespace = config['namespace']
        except KeyError:
            current_app.logger.exception('Invalid log pod: {}'.format(pod.id))
            continue
        k8s_service_proxy = \
            K8S_PROXY_PREFIX +\
            '/namespaces/{ns}/services/{service}:{port}/'.format(
                ns=namespace, service=service, port=ELASTICSEARCH_REST_PORT
            )
        es_service_hosts.append({
            'host': KUBE_API_HOST,
            'port': KUBE_API_PORT,
            'url_prefix': k8s_service_proxy
        })

    # current_app.logger.debug('ES init hosts: {}'.format(es_service_hosts))
    es = elastic.Elasticsearch(es_service_hosts)
    body = {'size': size}
    if sort:
        body['sort'] = sort
    if query:
        body['query'] = query

    try:
        res = es.search(
            index=index,
            body=body
        )
    except (RequestException,
            elastic.ConnectionTimeout,
            elastic.ConnectionError) as err:
        raise LogsError(repr(err), error_code=LogsError.CONNECTION_ERROR)
    except elastic.TransportError as err:
        if err.status_code == 404:
            raise LogsError('Logs not found', error_code=LogsError.NO_LOGS)
        elif err.status_code == 503:
            raise LogsError(repr(err), error_code=LogsError.INTERNAL_ERROR)
        raise LogsError(repr(err))
    except (elastic.ImproperlyConfigured,
            elastic.ElasticsearchException) as err:
        raise LogsError(repr(err), error_code=LogsError.INTERNAL_ERROR)
    except Exception as err:
        raise LogsError(repr(err))

    hits = res.get('hits', {})

    if hits.get('total', 0) == 0 or not hits.get('hits', []):
        raise LogsError('Empty logs', error_code=LogsError.NO_LOGS)

    return hits
