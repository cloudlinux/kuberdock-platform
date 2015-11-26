import datetime
import unittest
from uuid import uuid4

import mock

from kubedock.testutils.testcases import APITestCase
from kubedock.testutils import fixtures
from kubedock.billing.models import Kube
from kubedock.core import db
from kubedock.nodes.models import Node
from kubedock.pods import models as pod_models

from kubedock.api import logs as api_logs


class TestLogsAPI(APITestCase):
    """Tests for /api/logs endpoint"""
    url = '/logs'

    def setUp(self):
        super(TestLogsAPI, self).setUp()
        self.admin, admin_password = fixtures.admin_fixtures()
        self.user, self.user_password = fixtures.user_fixtures()
        self.adminauth = (self.admin.username, admin_password)
        self.userauth = (self.user.username, self.user_password)

    @mock.patch.object(api_logs.es_logs, 'get_container_logs')
    def test_get_container_log(self, es_logs_mock):
        es_logs_mock.return_value = {'1': 2}
        response = self.open(
            self.url + '/container/123',
            auth=self.userauth
        )
        es_logs_mock.assert_called_once_with(
            u'123', self.user.id, 100, None, None)
        self.assert200(response)
        self.assertEqual(response.json, {u'status': u'OK', u'data': {u'1': 2}})

        starttime = '2015-01-01T12:12:12'
        endtime = '2015-01-02T12:12:12'
        size = 233
        params = {'starttime': starttime, 'endtime': endtime, 'size': size}
        response = self.open(
            self.url + '/container/123?{}'.format(
                '&'.join(str(key) + '=' + str(value)
                         for key, value in params.iteritems())
            ),
            auth=self.userauth
        )
        es_logs_mock.assert_called_with(
            u'123', self.user.id, size,
            datetime.datetime(2015, 1, 1, 12, 12, 12),
            datetime.datetime(2015, 1, 2, 12, 12, 12))
        self.assert200(response)

        response = self.open(self.url + '/container/123')
        self.assert401(response)

    @mock.patch.object(api_logs.es_logs, 'get_node_logs')
    def test_api_get_node_logs(self, get_logs_mock):
        hostname = 'qwerty'
        ip1 = '192.168.1.2'
        host1 = 'host1'
        ip2 = '192.168.1.3'
        host2 = 'host2'
        kube_type = Kube.get_default_kube_type()
        node1 = Node(ip=ip1, hostname=host1, kube_id=kube_type)
        node2 = Node(ip=ip2, hostname=host2, kube_id=kube_type)
        db.session.add_all((node1, node2))
        db.session.commit()

        url = self.url + '/node/' + hostname
        response = self.open(url)
        self.assert401(response)
        response = self.open(url, auth=self.userauth)
        self.assert403(response)
        # unknown hostname
        response = self.open(url, auth=self.adminauth)
        self.assert404(response)

        url = self.url + '/node/' + host2
        get_logs_mock.return_value = {'2': 3}
        response = self.open(url, auth=self.adminauth)
        self.assert200(response)
        self.assertEqual(
            response.json,
            {u'status': u'OK', u'data': get_logs_mock.return_value}
        )
        get_logs_mock.assert_called_once_with(host2, None, 100, host=ip2)

    @mock.patch.object(api_logs.usage, 'select_pod_states_history')
    def test_api_get_pod_states(self, sel_pod_states_mock):
        missing_podid = str(uuid4())
        endpoint = self.url + '/pod-states/'
        url = endpoint + missing_podid + '/0'
        response = self.open(url)
        # no auth information
        self.assert401(response)

        response = self.open(url, auth=self.userauth)
        # pod not found
        self.assert404(response)

        # add one more user and a pod
        user2, user2_password = fixtures.user_fixtures()

        pod1 = pod_models.Pod(
            id=str(uuid4()),
            name='p1',
            owner_id=self.user.id,
            kube_id=Kube.get_default_kube_type(),
            config='',
            status='RUNNING'
        )
        pod2 = pod_models.Pod(
            id=str(uuid4()),
            name='p2',
            owner_id=user2.id,
            kube_id=Kube.get_default_kube_type(),
            config='',
            status='RUNNING'
        )
        db.session.add_all([pod1, pod2])
        db.session.commit()
        url = endpoint + pod2.id + '/0'
        response = self.open(url, auth=self.userauth)
        # pod belongs to another user
        self.assert403(response)

        sel_pod_states_mock.return_value = {'a': [1, 2, 3]}
        response = self.open(url, auth=(user2.username, user2_password))
        self.assert200(response)
        sel_pod_states_mock.assert_called_once_with(pod2.id, 0)
        self.assertEqual(
            response.json,
            {u'status': 'OK', 'data': sel_pod_states_mock.return_value}
        )

        response = self.open(url, auth=self.adminauth)
        self.assert200(response)

        # check depth conversion
        url = endpoint + pod2.id + '/qwerty'
        response = self.open(url, auth=(user2.username, user2_password))
        self.assert200(response)
        sel_pod_states_mock.assert_called_with(pod2.id, 1)

        url = endpoint + pod2.id + '/123'
        response = self.open(url, auth=(user2.username, user2_password))
        self.assert200(response)
        sel_pod_states_mock.assert_called_with(pod2.id, 123)


if __name__ == '__main__':
    unittest.main()
