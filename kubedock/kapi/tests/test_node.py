import json
import responses

from flask import current_app

from kubedock.exceptions import APIError
from kubedock.kapi.node import Node, NodeExceptionUpdateFailure
from kubedock.testutils.fixtures import K8SAPIStubs
from kubedock.testutils.testcases import DBTestCase


class TestNode(DBTestCase):
    def setUp(self):
        self.node = Node(hostname='node1')
        self.stubs = K8SAPIStubs()
        self.stubs.node_info_in_k8s_api(self.node.hostname)
        current_app.config['NONFLOATING_PUBLIC_IPS'] = True

    @responses.activate
    def test_public_ip_counter_update_sends_correct_request_to_api(self):
        self.stubs.node_info_update_in_k8s_api(self.node.hostname)

        count = 999
        self.node.update_free_public_ip_count(count)

        self.assertGreater(len(responses.calls), 0)

        request = json.loads(responses.calls[1].request.body)
        self.assertEqual(request['metadata']['annotations'][
                             Node.FREE_PUBLIC_IP_COUNTER_FIELD], str(count))

    @responses.activate
    def test_increment_free_public_ip_count_updates_k8s_data(self):
        self.stubs.node_info_update_in_k8s_api(self.node.hostname)

        delta = 5
        initial_ip_count = self.node.free_public_ip_count
        self.node.increment_free_public_ip_count(delta)
        expected_count = initial_ip_count + delta

        self.assertEqual(self.node.free_public_ip_count, expected_count)
        actual_count = self.stubs.nodes[self.node.hostname]['metadata'][
            'annotations'][
            Node.FREE_PUBLIC_IP_COUNTER_FIELD]

        self.assertEqual(actual_count, str(expected_count))

    @responses.activate
    def test_increment_free_public_ip_fails_if_unable_update_max_retry_times(
            self):
        self.stubs.node_info_update_in_k8s_api(self.node.hostname, True)

        with self.assertRaises(NodeExceptionUpdateFailure):
            self.node.increment_free_public_ip_count(1)

    @responses.activate
    def test_update_data_on_k8s_succeeds_if_update_succeeded(self):
        expected_value, hostname = 1, self.node.hostname
        self.stubs.node_info_update_in_k8s_api(hostname)
        self.node.k8s_data['metadata']['annotations']['foo'] = expected_value
        self.node.update_data_on_k8s()

        input = self.stubs.nodes[hostname]['metadata']['annotations']['foo']
        self.assertEqual(input, expected_value)

    @responses.activate
    def test_update_data_on_k8s_fails_if_update_fails(self):
        hostname = self.node.hostname
        self.stubs.node_info_update_in_k8s_api(hostname,
                                               always_raise_failure=True)
        with self.assertRaises(APIError):
            self.node.update_data_on_k8s()
