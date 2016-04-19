import mock
from kubedock.testutils.testcases import APITestCase


class TestStats(APITestCase):
    """
    Test for 'api/stats' endpoint
    """
    url = '/stats/'

    def setUp(self):
        self.pod = self.fixtures.pod(owner_id=self.user.id)
        self.other_user, _ = self.fixtures.user_fixtures()
        self.other_pod = self.fixtures.pod(owner_id=self.other_user.id)

    @mock.patch('kubedock.api.stats.KubeStat')
    def test_get_stats(self, KubeStat):
        # only admin can get node stats
        response = self.admin_open(query_string={'node': 'kdnode1'})
        self.assert200(response)

        # user can get info about own pods only
        response = self.user_open(query_string={'unit': self.pod.id})
        self.assert200(response)
        response = self.user_open(query_string={'unit': self.other_pod.id})
        self.assertAPIError(response, 404, 'PodNotFound')
