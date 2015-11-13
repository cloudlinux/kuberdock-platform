import unittest
from datetime import date, datetime
from uuid import uuid4

from kubedock.core import db
from kubedock.testutils import fixtures
from kubedock.testutils.testcases import APITestCase
from kubedock.pods import models as pod_models
from kubedock.usage import models as usage_models
from kubedock.billing import models as bill_models

import mock

from .. import es_logs


class TestContainerLogs(APITestCase):
    """Tests for container logs (kapi.es_logs.get_container_logs)."""
    def setUp(self):
        self.user, user_password = fixtures.user_fixtures()
        self.pod_id = str(uuid4())
        self.index = 'docker-*'
        self.container_name = 'igewfh9whe3'
        self.host = '12.13.14.15'
        self.pod = pod_models.Pod(
            id=self.pod_id,
            name='p1',
            owner_id=self.user.id,
            kube_id=bill_models.Kube.get_default_kube_type(),
            config='',
            status='RUNNING'
        )
        self.pod_state = usage_models.PodState(
            pod_id=self.pod_id,
            start_time=datetime(2015, 2, 5),
            last_event_time=datetime(2015, 2, 6),
            last_event='MODIFIED',
            hostname='kdnode1',
        )
        self.container_state_1 = usage_models.ContainerState(
            pod_state_id=1,
            container_name=self.container_name,
            docker_id='p93urmqahdeef',
            start_time=datetime(2015, 2, 5),
            end_time=datetime(2015, 2, 6),
            exit_code=2,
            reason='SomeError: smth went wrong',
        )
        self.container_state_2 = usage_models.ContainerState(
            pod_state_id=1,
            container_name=self.container_name,
            docker_id='1wlsj2enhdfo4838',
            start_time=datetime(2015, 2, 6),
        )
        db.session.add_all([self.pod, self.pod_state,
                            self.container_state_1, self.container_state_2])

        patcher = mock.patch.object(es_logs, 'log_query')
        self.addCleanup(patcher.stop)
        self.log_query_mock = patcher.start()
        self.log_query_mock.return_value = {'hits': [{'_source': {'log': '321'}},
                                                     {'_source': {'log': '654'}},
                                                     {'_source': {'log': '987'}}],
                                            'total': 3}

        patcher = mock.patch.object(es_logs.Node, 'get_by_name')
        self.addCleanup(patcher.stop)
        self.get_by_name_mock = patcher.start()
        self.get_by_name_mock.return_value = type('Node', (), {'ip': self.host})

        self.default_result = [{
            'total': 3,
            'hits': [{'log': '321'}, {'log': '654'}, {'log': '987'}],
            'exit_code': None,
            'reason': None,
            'end': None,
            'start': self.container_state_2.start_time,
        }, {
            'total': 3,
            'hits': [{'log': '321'}, {'log': '654'}, {'log': '987'}],
            'exit_code': self.container_state_1.exit_code,
            'reason': self.container_state_1.reason,
            'end': self.container_state_1.end_time,
            'start': self.container_state_1.start_time,
        }]

    def get_filters(self, docker_id):
        return [{'term': {'container_id': docker_id}}]

    def test_without_range(self):
        """Test method call without time restrictions."""
        size, start, end = 101, None, None
        res = es_logs.get_container_logs(self.container_name, self.user.id, size,
                                         start, end)

        self.log_query_mock.assert_has_calls([
            mock.call(self.index, self.get_filters(self.container_state_2.docker_id),
                      self.host, size, start, end),
            mock.call(self.index, self.get_filters(self.container_state_1.docker_id),
                      self.host, size - 3, start, end),
        ])
        self.get_by_name_mock.assert_has_calls([mock.call(self.pod_state.hostname)] * 2)
        self.assertEqual(res, self.default_result)

    def test_with_range(self):
        """Test time restrictions."""
        size = 101
        start, end = datetime(2015, 2, 5, 6), datetime(2015, 2, 5, 18)
        res = es_logs.get_container_logs(self.container_name, self.user.id, size,
                                         start, end)

        self.log_query_mock.assert_called_once_with(
            self.index, self.get_filters(self.container_state_1.docker_id),
            self.host, size, start, end
        )
        self.get_by_name_mock.assert_called_once_with(self.pod_state.hostname)
        self.assertEqual(res, self.default_result[-1:])

    def test_size(self):
        """Test size restrictions."""
        size, start, end = 3, None, None  # last 3 lines
        res = es_logs.get_container_logs(self.container_name, self.user.id, size,
                                         start, end)

        self.log_query_mock.assert_called_once_with(
            self.index, self.get_filters(self.container_state_2.docker_id),
            self.host, size, start, end
        )
        self.get_by_name_mock.assert_called_once_with(self.pod_state.hostname)
        self.assertEqual(res, self.default_result[:1])


class TestLogQuery(unittest.TestCase):
    """Tests for log query generator (kapi.es_logs.log_query)."""
    def setUp(self):
        self.default_result = {'hits': [{'_source': {'log': '321'}},
                                        {'_source': {'log': '654'}},
                                        {'_source': {'log': '987'}}],
                               'total': 1000}

        patcher = mock.patch.object(es_logs, 'execute_es_query')
        self.addCleanup(patcher.stop)
        self.es_query_mock = patcher.start()
        self.es_query_mock.return_value = self.default_result

    def test_time_restrictions(self):
        """Test time restrictions."""
        filters = ['some_filter', 'some_other_filter']
        index, host = 'oi2nh23', '12.13.14.15'
        size = 101

        def check(start, end, time_filters):
            self.es_query_mock.reset_mock()
            res = es_logs.log_query(index, filters, host, size, start, end)

            self.assertEqual(res, self.default_result)
            self.es_query_mock.assert_called_once_with(
                index, {'filtered': {'filter': {'and': filters + time_filters}}},
                size, {'time_nano': {'order': 'desc'}}, host
            )

        start, end = datetime(2015, 2, 5, 6), datetime(2015, 2, 5, 18)
        check(start, end, [{'range': {'@timestamp': {'gte': start, 'lt': end}}}])

        start, end = datetime(2015, 2, 5, 6), None
        check(start, end, [{'range': {'@timestamp': {'gte': start}}}])

        start, end = None, datetime(2015, 2, 5, 18)
        check(start, end, [{'range': {'@timestamp': {'lt': end}}}])

        start, end = None, None
        check(start, end, [])


class TestNodeLogs(unittest.TestCase):
    """Tests for node logs."""
    @mock.patch.object(es_logs, 'log_query')
    def test_get_node_logs(self, log_query_mock):
        """Test kapi.es_logs.get_node_logs method."""
        hostname = '12345'
        size = 21
        date_ = date(2015, 10, 12)
        index = 'syslog-2015.10.12'
        es_response = {'hits': [{'_source': {'log': '321'}},
                                {'_source': {'log': '654'}},
                                {'_source': {'log': '987'}}]}
        log_query_mock.return_value = es_response
        res = es_logs.get_node_logs(hostname, date_, size)
        self.assertEqual(res, dict(es_response, total=3))
        log_query_mock.assert_called_once_with(
            index, [{'term': {'host': hostname}}], None, size
        )


if __name__ == '__main__':
    unittest.main()
