import datetime
import unittest

import mock

from .. import es_logs

class TestESLogs(unittest.TestCase):
    """Tests for es_logs functions."""

    @mock.patch.object(es_logs, 'execute_es_query')
    def test_get_container_logs(self, es_query_mock):
        """Test es_logs.get_container_logs method."""
        size = 101
        host = 'abc'
        containerid = 'qwert'
        starttime = None
        endtime = None
        es_query_mock.return_value = 123
        res = es_logs.get_container_logs(
            host, containerid, size, starttime, endtime)
        self.assertEqual(res, 123)

        query = {'filtered': {'filter': {'and': [
            {'term': {'container_id': containerid}}
        ]}}}
        orderby = {'@timestamp': {'order': 'desc'}}
        es_query_mock.assert_called_once_with(
            host, 'docker-*', query, size, orderby)

        starttime = datetime.date(2015, 10, 1)
        endtime = datetime.date(2015, 10, 10)
        es_logs.get_container_logs(host, containerid, size, starttime, endtime)
        query = {'filtered': {'filter': {'and': [
            {'term': {'container_id': containerid}},
            {'range': {'@timestamp': {'gte': starttime, 'lt': endtime}}}
        ]}}}
        es_query_mock.assert_called_with(
            host, 'docker-*', query, size, orderby)

    @mock.patch.object(es_logs, 'execute_es_query')
    def test_get_node_logs(self, es_query_mock):
        host = '12345'
        size = 21
        date = datetime.date(2015, 10, 12)
        index = 'syslog-2015.10.12'
        hostname = ['q', 'w']
        es_query_mock.return_value = 321
        res = es_logs.get_node_logs(
            host, date, size, hostname)
        self.assertEqual(res, 321)
        query = {'filtered': {'filter': {'and': [
            {'terms': {'host': hostname}}
        ]}}}
        orderby = {'@timestamp': {'order': 'desc'}}
        es_query_mock.assert_called_once_with(
            host, index, query, size, orderby)

        hostname = None
        es_logs.get_node_logs(host, date, size, hostname)
        query = None
        es_query_mock.assert_called_with(
            host, index, query, size, orderby)


if __name__ == '__main__':
    unittest.main()
