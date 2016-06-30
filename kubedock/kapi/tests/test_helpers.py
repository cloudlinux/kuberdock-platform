import mock
import unittest
from kubedock.kapi import helpers


class TestServices(unittest.TestCase):

    SERVICES = {
        "kind": "List",
        "apiVersion": "v1",
        "metadata": {},
        "items": [
            {
                "kind": "Service",
                "apiVersion": "v1",
                "metadata": {
                    "uid": "b63ae17c-2653-11e6-ad8f-02005fa444ab",
                    "resourceVersion": "48145",
                    "creationTimestamp": "2016-05-30T10:46:06Z"},
                "spec": {
                },
                "status": {
                    "loadBalancer": {}
                }
            },
            {
                "kind": "Service",
                "apiVersion": "v1",
                "metadata": {
                    "uid": "68783519-2273-11e6-90a7-02005fa444ab",
                    "resourceVersion": "443",
                    "creationTimestamp": "2016-05-25T12:22:55Z"
                },
                "spec": {
                },
                "status": {
                    "loadBalancer": {}
                }
            }
        ]
    }

    def test_get_label_selector(self):
        services = helpers.Services()
        conditions = ['test1, test2']
        rv = services._get_label_selector(conditions)
        self.assertEqual(rv, 'test1, test2')
        self.assertEqual('', services._get_label_selector([]))

    @mock.patch.object(helpers.KubeQuery, 'get')
    def test_get(self, mock_get):
        services = helpers.Services()
        mock_get.return_value = self.SERVICES
        svc = services._get()
        self.assertEqual(svc, self.SERVICES['items'])

    @mock.patch.object(helpers.Services, '_get')
    def test_get_all(self, mock_get):
        services = helpers.Services()
        services.get_all()
        mock_get.assert_called_once_with([])

    @mock.patch.object(helpers.Services, '_get')
    def test_get_by_type(self, mock_get):
        services = helpers.Services('public')
        services.get_by_type()
        mock_get.assert_called_once_with(
            [helpers.LABEL_SELECTOR_TYPE.format('public')])

    @mock.patch.object(helpers.Services, '_get')
    def test_get_by_type_with_condition(self, mock_get):
        services = helpers.Services('public')
        services.get_by_type(conditions='condition1')
        mock_get.assert_called_once_with(
            ['condition1', helpers.LABEL_SELECTOR_TYPE.format('public')])

    @mock.patch.object(helpers.Services, '_get')
    def test_get_by_type_with_condition_list(self, mock_get):
        services = helpers.Services('public')
        services.get_by_type(conditions=['condition1'])
        mock_get.assert_called_once_with(
            ['condition1', helpers.LABEL_SELECTOR_TYPE.format('public')])

    @mock.patch.object(helpers.Services, '_get')
    def test_get_by_pod(self, mock_get):
        services = helpers.Services()
        services.get_by_pods('pod_id')
        mock_get.assert_called_once_with(
            [helpers.LABEL_SELECTOR_PODS.format('pod_id')])

    @mock.patch.object(helpers.Services, '_get')
    def test_get_by_pod_list(self, mock_get):
        services = helpers.Services()
        services.get_by_pods(('pod_id', 'pod_id2'))
        mock_get.assert_called_once_with(
            [helpers.LABEL_SELECTOR_PODS.format('pod_id, pod_id2')])

    @mock.patch.object(helpers.Services, '_get')
    def test_get_by_pods_with_type(self, mock_get):
        services = helpers.Services('public')
        services.get_by_pods('pod_id')
        mock_get.assert_called_once_with(
            [helpers.LABEL_SELECTOR_PODS.format('pod_id'),
             helpers.LABEL_SELECTOR_TYPE.format('public')])

    @mock.patch.object(helpers.User, 'pods_to_dict')
    @mock.patch.object(helpers.User, 'get')
    @mock.patch.object(helpers.Services, '_get')
    def test_get_by_user(self, mock_get, mock_u_get, mock_u_pods):
        services = helpers.Services()
        mock_u_get.return_value = helpers.User
        mock_u_pods.return_value = [{'id': 'pod_id'}]
        services.get_by_user(3)
        mock_get.assert_called_once_with(
            [helpers.LABEL_SELECTOR_PODS.format('pod_id')])


if __name__ == '__main__':
    unittest.main()
