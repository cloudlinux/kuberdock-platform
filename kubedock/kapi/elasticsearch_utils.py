from requests import RequestException
import elasticsearch as elastic

from ..settings import ELASTICSEARCH_REST_PORT
from ..api import APIError
from ..nodes.models import Node


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
        hosts = [ip for ip, in Node.query.values(Node.ip)]
    else:
        hosts = [host]

    es = elastic.Elasticsearch(
        [{'host': n, 'port': ELASTICSEARCH_REST_PORT} for n in hosts]
    )
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
    except (RequestException, elastic.TransportError) as err:
        raise APIError(u'Failed to get logs from elasticsearch: {}'.format(err),
                       status_code=404)
    except (elastic.ImproperlyConfigured,
            elastic.ElasticsearchException) as err:
        raise APIError(u'Failed to execute elasticsearch query: {}'.format(err),
                       status_code=500)

    return res.get('hits', {})
