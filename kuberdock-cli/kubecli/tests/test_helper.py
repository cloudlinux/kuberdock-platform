"""Tests for helper.py classes"""
import unittest
import requests
import json

import responses

from kubecli.helper import KubeQuery


TEST_URL = 'http://localhost'
TEST_USER = 'user1'
TEST_PASSWORD = 'password1'

class TestHelperKubeQuery(unittest.TestCase):
    """Tests for KubeQuery class."""

    def _get_default_query(self):
        return KubeQuery(url=TEST_URL, user=TEST_USER, password=TEST_PASSWORD,
                         jsonify_errors=True)

    @responses.activate
    def test_get(self):
        """Test KubeQuery.get method"""
        query = self._get_default_query()
        path1 = '/path1/to/some/api'
        path2 = '/path2/to/some/api'
        responses.add(responses.GET, TEST_URL + path1,
                      body='{"error": "not found"}', status=404,
                      content_type='application/json')
        with self.assertRaises(SystemExit) as err:
            query.get(path1)
        exc = err.exception
        json_message = json.loads(exc.message)
        self.assertEqual(json_message['status'], 'ERROR')
        self.assertTrue(json_message['message'].startswith('404'))

        body = '{"data": [1,2,3]}'
        responses.add(responses.GET, TEST_URL + path2,
                      body=body, status=200,
                      content_type='application/json',
                      match_querystring=True)
        res = query.get(path2)
        self.assertEqual(res, {u'data': [1,2,3]})

        token = 'qwerty'
        query.token = token
        body = '{"data": [3,4,5]}'
        responses.add(responses.GET, TEST_URL + path2 + '?token=' + token,
                      body=body, status=200,
                      content_type='application/json',
                      match_querystring=True)
        res = query.get(path2)
        self.assertEqual(res, {u'data': [3,4,5]})

    @responses.activate
    def test_post(self):
        """Test KubeQuery.post method"""
        query = self._get_default_query()
        token = '1324qewr'
        query.token = token
        path1 = '/path1/to/some/api'
        resp_body = '{"data": [1,2,3]}'
        req_data = '{"somekey": "somevalue"}'
        responses.add(responses.POST, TEST_URL + path1 + '?token=' + token,
                      body=resp_body, status=200,
                      content_type='application/json',
                      match_querystring=True)
        res = query.post(path1, req_data)
        self.assertEqual(res, {u'data': [1,2,3]})
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(responses.calls[0].request.body, req_data)

    @responses.activate
    def test_put(self):
        """Test KubeQuery.put method"""
        query = self._get_default_query()
        token = '1324qewrty'
        query.token = token
        path1 = '/path1/to/some/api'
        resp_body = '{"data": [1,2,3]}'
        req_data = '{"somekey": "somevalue"}'
        responses.add(responses.PUT, TEST_URL + path1 + '?token=' + token,
                      body=resp_body, status=200,
                      content_type='application/json',
                      match_querystring=True)
        res = query.put(path1, req_data)
        self.assertEqual(res, {u'data': [1,2,3]})
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(responses.calls[0].request.body, req_data)

    @responses.activate
    def test_delete(self):
        """Test KubeQuery.delete method"""
        query = self._get_default_query()
        token = '1324qewrtyui'
        query.token = token
        path1 = '/path1/to/some/api'
        resp_body = '{"data": [1,2,3]}'
        responses.add(responses.DELETE, TEST_URL + path1 + '?token=' + token,
                      body=resp_body, status=200,
                      content_type='application/json',
                      match_querystring=True)
        res = query.delete(path1)
        self.assertEqual(res, {u'data': [1,2,3]})


if __name__ == '__main__':
    unittest.main()
