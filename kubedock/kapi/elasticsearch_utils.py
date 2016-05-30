import elasticsearch as elastic
from requests import RequestException

from ..nodes.models import Node
from ..settings import ELASTICSEARCH_REST_PORT


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
