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
        containerid = 'qwert'
        starttime = None
        endtime = None
        es_query_mock.return_value = 123
        res = es_logs.get_container_logs(containerid, size, starttime, endtime)
        self.assertEqual(res, 123)

        query = {'filtered': {'filter': {'and': [
            {'term': {'container_id': containerid}}
        ]}}}
        orderby = {'@timestamp': {'order': 'desc'}}
        es_query_mock.assert_called_once_with('docker-*', query, size, orderby)

        starttime = datetime.date(2015, 10, 1)
        endtime = datetime.date(2015, 10, 10)
        es_logs.get_container_logs(containerid, size, starttime, endtime)
        query = {'filtered': {'filter': {'and': [
            {'term': {'container_id': containerid}},
            {'range': {'@timestamp': {'gte': starttime, 'lt': endtime}}}
        ]}}}
        es_query_mock.assert_called_with('docker-*', query, size, orderby)

    @mock.patch.object(es_logs, 'execute_es_query')
    def test_get_node_logs(self, es_query_mock):
        hostname = '12345'
        size = 21
        date = datetime.date(2015, 10, 12)
        index = 'syslog-2015.10.12'
        es_query_mock.return_value = 321
        res = es_logs.get_node_logs(hostname, date, size)
        self.assertEqual(res, 321)
        query = {'filtered': {'filter': {'term': {'host': hostname}}}}
        orderby = {'@timestamp': {'order': 'desc'}}
        es_query_mock.assert_called_once_with(index, query, size, orderby)


if __name__ == '__main__':
    unittest.main()
