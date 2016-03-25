import unittest

import mock
from requests import RequestException

from .. import elasticsearch_utils
from ...api import APIError


class TestElasticsearchUtils(unittest.TestCase):
    """Tests for elasticsearch_utils functions."""
    nodes = ['192.168.168.2', '192.168.168.3']

    @mock.patch('kubedock.kapi.elasticsearch_utils.Node')
    @mock.patch.object(elasticsearch_utils.elastic.Elasticsearch, 'search')
    def test_execute_es_query(self, search_mock, node_mock):
        """Test elasticsearch_utils.execute_es_query function."""
        node_query_values_mock = mock.Mock(
            return_value=[(n,) for n in self.nodes]
        )
        node_mock.query.values = node_query_values_mock
        size = 123
        index = '1234qwerty'
        query = None
        sort = None
        search_result = {
            'hits': {
                'total': 333,
                'hits': [1, 2, 3]
            }
        }
        search_mock.return_value = search_result
        res = elasticsearch_utils.execute_es_query(index, query, size, sort)
        self.assertEqual(
            res,
            {
                'total': search_result['hits']['total'],
                'hits': search_result['hits']['hits'],
            }
        )
        search_mock.assert_called_once_with(
            index=index,
            body={'size': size}
        )

        query = {'a': 1}
        sort = {'b': 2}
        elasticsearch_utils.execute_es_query(index, query, size, sort)
        search_mock.assert_called_with(
            index=index,
            body={
                'size': size,
                'sort': sort,
                'query': query
            }
        )
        search_mock.side_effect = RequestException('!!!')
        with self.assertRaises(APIError):
            elasticsearch_utils.execute_es_query(index, query, size, sort)
        self.assertEqual(node_query_values_mock.call_count, 3)


if __name__ == '__main__':
    unittest.main()
