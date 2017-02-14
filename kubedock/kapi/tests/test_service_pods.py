import mock

from kubedock.kapi import network_policies, service_pods
from kubedock.users.models import User
from kubedock.testutils.testcases import DBTestCase


class TestServicePods(DBTestCase):

    @mock.patch.object(network_policies, 'get_calico_ip_tunnel_address')
    @mock.patch.object(service_pods, 'Etcd')
    @mock.patch.object(service_pods, 'PodCollection')
    def test_create_logs_pod(self, podcollection_mock, etcd_mock,
                             get_calico_ip_mock):
        hostname = 'qwerty'
        test_result = 3131313
        pod_id = '424242'
        podcollection_mock.return_value.add.return_value = {'id': pod_id}
        podcollection_mock.return_value.get.return_value = test_result
        get_calico_ip_mock.return_value = '12.12.12.12'
        owner = User.get_internal()
        res = service_pods.create_logs_pod(hostname, owner)
        self.assertEqual(res, test_result)
        self.assertEqual(etcd_mock.call_count, 1)
        get_calico_ip_mock.assert_called_once_with()
        podcollection_mock.return_value.update.assert_called_once_with(
            pod_id, {'command': 'synchronous_start'}
        )
