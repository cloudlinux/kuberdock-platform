from requests import RequestException
import elasticsearch as elastic

from ..settings import ELASTICSEARCH_REST_PORT
from ..api import APIError


def execute_es_query(host, index, query, size, sort):
    """Composes and executes elasticsearch query.
    Answer will be converted to standard API answer structure.
    Exceptions will be correctly handled.
    :param host: address of ES server
    :param index: elasticsearch index name
    :param size: restrict output to this number of records
    :param query: dict with query parameters (optional)
    :param sort: dict with sorting parameters (optional)

    """
    es = elastic.Elasticsearch(
        [{'host': host, 'port': ELASTICSEARCH_REST_PORT}]
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

    return convert_elastic_result_to_answer(res)


def convert_elastic_result_to_answer(elastic_result):
    """Converts elasticsearch answer to standard API answer structure."""
    hits = elastic_result.get('hits', {})
    return {
        'status': 'OK',
        'data': {
            'total': hits.get('total', 0),
            'hits': hits.get('hits', [])
        }
    }
