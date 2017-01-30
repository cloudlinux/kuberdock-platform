
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

import unittest

import mock
from requests import RequestException
from uuid import uuid4
import json

from .. import elasticsearch_utils
from kubedock.testutils.testcases import DBTestCase
from kubedock.pods.models import Pod
from kubedock.users.models import User
from kubedock.core import db
from kubedock.settings import KUBE_API_HOST, KUBE_API_PORT
from kubedock.billing.models import Kube
from kubedock.nodes.models import Node
from kubedock.kapi.nodes import get_kuberdock_logs_pod_name


class TestElasticsearchUtils(DBTestCase):
    """Tests for elasticsearch_utils functions."""

    @mock.patch.object(elasticsearch_utils.elastic, 'Elasticsearch')
    def test_execute_es_query(self, es_mock):
        """Test elasticsearch_utils.execute_es_query function."""

        # Add two log pods config + two approprate nodes
        internal_user = User.get_internal()
        pod_id1 = str(uuid4())
        service1 = 'srv1'
        namespace1 = 'ns1'
        pod_id2 = str(uuid4())
        service2 = 'srv2'
        namespace2 = 'ns2'

        host1 = 'h1'
        host2 = 'h2'

        kube_id = Kube.get_default_kube_type()

        pod1 = Pod(
            id=pod_id1,
            name=get_kuberdock_logs_pod_name(host1),
            owner_id=internal_user.id,
            kube_id=kube_id,
            config=json.dumps({"service": service1, "namespace": namespace1}),
            status='RUNNING'
        )
        pod2 = Pod(
            id=pod_id2,
            name=get_kuberdock_logs_pod_name(host2),
            owner_id=internal_user.id,
            kube_id=kube_id,
            config=json.dumps({"service": service2, "namespace": namespace2}),
            status='RUNNING'
        )
        db.session.add_all([pod1, pod2])
        db.session.commit()

        node1 = Node(
            ip='123.123.123',
            hostname=host1,
            kube_id=kube_id,
            state='completed',
            upgrade_status='applied'
        )
        node2 = Node(
            ip='123.123.124',
            hostname=host2,
            kube_id=kube_id,
            state='completed',
            upgrade_status='applied'
        )
        db.session.add_all([node1, node2])
        db.session.commit()

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
        search_mock = es_mock.return_value.search
        search_mock.return_value = search_result
        res = elasticsearch_utils.execute_es_query(index, query, size, sort)
        self.assertEqual(
            res,
            {
                'total': search_result['hits']['total'],
                'hits': search_result['hits']['hits'],
            }
        )
        prefix1 = elasticsearch_utils.K8S_PROXY_PREFIX + \
            '/namespaces/' + namespace1 + '/services/' + service1 + ':9200/'
        prefix2 = elasticsearch_utils.K8S_PROXY_PREFIX + \
            '/namespaces/' + namespace2 + '/services/' + service2 + ':9200/'
        es_mock.assert_called_once_with([
            {
                'host': KUBE_API_HOST,
                'port': KUBE_API_PORT,
                'url_prefix': prefix1,
            },
            {
                'host': KUBE_API_HOST,
                'port': KUBE_API_PORT,
                'url_prefix': prefix2,
            },
        ])
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
        with self.assertRaises(elasticsearch_utils.LogsError):
            elasticsearch_utils.execute_es_query(index, query, size, sort)


if __name__ == '__main__':
    unittest.main()
