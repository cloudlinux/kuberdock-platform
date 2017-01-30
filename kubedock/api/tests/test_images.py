
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

import mock

from kubedock.testutils.testcases import APITestCase
from kubedock.api import images
from kubedock.login import current_user


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
        Image.return_value.get_container_config.assert_called_once_with(
            auth=None, refresh_cache=None, secrets=None)

    @mock.patch.object(images, 'PodCollection')
    @mock.patch.object(images.kapi_images.Image, 'get_container_config')
    def test_get_dockerfile_data_by_pod(
            self, get_container_config, PodCollection):
        secrets = {
            'secret-id-1': ('username-1', 'password-1', 'https://1-regist.ry'),
            'secret-id-2': ('username-2', 'password-2', 'https://2-regist.ry'),
        }
        image = '1-regist.ry/qwerty'
        get_container_config.return_value = {'a': 'b'}
        PodCollection.return_value.get_secrets.return_value = secrets
        PodCollection.return_value._get_by_id.return_value.containers = [
            {'image': image}, {'image': 'other_image'}]
        PodCollection.return_value._get_by_id.return_value.edited_config = None
        response = self.user_open(
            '/images/new', method='POST', json={'image': image,
                                                'podID': 'pod-id'})
        self.assert200(response)
        PodCollection.assert_called_once_with(current_user)
        PodCollection.return_value._get_by_id.assert_called_once_with('pod-id')
        PodCollection.return_value.get_secrets.assert_called_once_with(
            PodCollection.return_value._get_by_id.return_value)
        get_container_config.assert_called_once_with(
            auth=None, refresh_cache=None, secrets=secrets.values())

        # no such image in pod
        PodCollection.return_value.get_secrets.reset_mock()
        get_container_config.reset_mock()
        response = self.user_open(
            '/images/new', method='POST', json={'image': 'image-not-from-pod',
                                                'podID': 'pod-id'})
        self.assert200(response)
        self.assertFalse(PodCollection.return_value.get_secrets.called)
        get_container_config.assert_called_once_with(
            auth=None, refresh_cache=None, secrets=None)

    @mock.patch('kubedock.kapi.images.check_registry_status')
    def test_ping_registry(self, check_registry_status):
        response = self.user_open(
            '/images/isalive', query_string={'url': 'https://1.2.3.4'})
        self.assert200(response)
        check_registry_status.assert_called_once_with('https://1.2.3.4')
