import mock

from kubedock.testutils.testcases import APITestCase


class TestImages(APITestCase):
    @mock.patch('kubedock.kapi.images.search_image')
    def test_search(self, search_image):
        search_image.return_value = {
            'count': 8353,
            'results': [{
                'is_automated': False,
                'repo_name': 'nginx',
                'repo_owner': None,
                'star_count': 2655,
                'short_description': 'Official build of Nginx.',
                'is_official': True,
                'pull_count': 94349454
            }],
        }
        response = self.user_open(
            '/images/', query_string={'searchkey': 'nginx'})
        self.assert200(response)
        search_image.assert_called_once_with(
            'nginx', url='https://registry.hub.docker.com', page=1)

    @mock.patch('kubedock.kapi.images.Image')
    def test_get_dockerfile_data(self, Image):
        Image.return_value.get_container_config.return_value = {'a': 'b'}
        response = self.user_open(
            '/images/new', method='POST', json={'image': 'nginx'})
        self.assert200(response)
        Image.assert_called_once_with('nginx')
        Image.return_value.get_container_config.assert_called_once_with()

    @mock.patch('kubedock.kapi.images.check_registry_status')
    def test_ping_registry(self, check_registry_status):
        response = self.user_open(
            '/images/isalive', query_string={'url': 'https://1.2.3.4'})
        self.assert200(response)
        check_registry_status.assert_called_once_with('https://1.2.3.4')
