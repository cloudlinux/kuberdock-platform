
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
from random import randint
from uuid import uuid4

import mock

from kubedock.kapi.podcollection import PodNotFound, PodCollection, KubeQuery
from kubedock.system_settings.models import SystemSettings
from kubedock.testutils.testcases import APITestCase


def valid_create_pod_params():
    return {
        'name': 'just name',
        'containers': [{
            'name': 'just name',  # hasn't in the validation schema
            'image': 'simple-image'
        }],
        'kube_type': 0,
        'restartPolicy': 'Always',
    }


class PodAPIUrl(object):
    get = '/podapi/{0}'.format
    post = '/podapi/'.format
    put = '/podapi/{0}'.format
    delete = '/podapi/{0}'.format

    check_updates = '/podapi/{0}/{1}/update'.format
    update_container = '/podapi/{0}/{1}/update'.format


class TestPodAPI(APITestCase):
    @mock.patch('kubedock.api.podapi.PodCollection')
    def test_get_not_found(self, PodCollection):
        PodCollection().get.side_effect = PodNotFound()

        response = self.user_open(PodAPIUrl.get(12345), 'GET')

        self.assertAPIError(response, 404, 'PodNotFound')

    def test_post_invalid_params(self):
        response = self.user_open(PodAPIUrl.post(), 'POST', {})

        self.assertAPIError(response, 400, 'ValidationError', {
            u'restartPolicy': u'required field',
            u'kube_type': u'required field',
            u'name': u'required field',
            u'containers': u'required field'
        })

    @mock.patch('kubedock.validation.V._validate_kube_type_exists')
    # @mock.patch('kubedock.kapi.images.Image._check_availability')
    @mock.patch('kubedock.api.podapi.PodCollection')
    def test_post(self, PodCollection, *_):
        PodCollection().add.return_value = {}
        response = self.user_open(
            PodAPIUrl.post(), 'POST', valid_create_pod_params())

        self.assert200(response)

    def test_put_invalid(self):
        response = self.user_open(PodAPIUrl.put(str(uuid4())), 'PUT', {})

        self.assertAPIError(response, 404, 'PodNotFound')

    @mock.patch('kubedock.api.podapi.PodCollection')
    def test_put(self, PodCollection):
        PodCollection().update.return_value = {}
        pod = self.fixtures.pod(status='unpaid', owner=self.user)
        pod_config = pod.get_dbconfig()

        response = self.user_open(PodAPIUrl.put(pod.id), 'PUT', {})
        self.assert200(response)

        # check fix-price users restrictions
        SystemSettings.set_by_name('billing_type', 'whmcs')
        self.user.count_type = 'fixed'
        self.db.session.commit()
        # only admin has permission to remove "unpaid" status
        set_paid = {
            'command': 'set', 'commandOptions': {'status': 'stopped'}
        }
        response = self.admin_open(PodAPIUrl.put(pod.id), 'PUT', set_paid)
        self.assert200(response)
        # only admin has permission to upgrade pod
        upgrade = {
            'command': 'redeploy', 'containers': [
                dict(c, kubes=c['kubes'] + 1) for c in
                pod_config['containers']]
        }
        response = self.admin_open(PodAPIUrl.put(pod.id), 'PUT', upgrade)
        self.assert200(response)

    @mock.patch('kubedock.api.podapi.PodCollection')
    def test_delete_not_found(self, PodCollection):
        PodCollection().delete.side_effect = PodNotFound()

        response = self.user_open(PodAPIUrl.delete(123), 'DELETE', {})

        self.assertAPIError(response, 404, 'PodNotFound')

    @mock.patch('kubedock.api.podapi.PodCollection')
    def test_delete(self, PodCollection):
        delete_id = randint(1, 1000)
        PodCollection().delete.return_value = delete_id

        response = self.user_open(PodAPIUrl.delete(delete_id), 'DELETE', {})

        self.assert200(response)

    @mock.patch('kubedock.api.podapi.PodCollection')
    def test_check_updates(self, PodCollection):
        PodCollection().check_updates.return_value = False

        pod_id = str(uuid4())
        container_name = 'just name'

        response = self.user_open(
            PodAPIUrl.check_updates(pod_id, container_name), 'GET', {})

        self.assert200(response)

        PodCollection().check_updates.assert_called_once_with(
            pod_id, container_name)

    @mock.patch('kubedock.api.podapi.PodCollection')
    def test_update_container(self, PodCollection):
        PodCollection().update_container.return_value = {}

        pod_id = str(uuid4())
        container_name = 'just name'

        response = self.user_open(
            PodAPIUrl.check_updates(pod_id, container_name), 'POST', {})

        self.assert200(response)

        PodCollection().update_container.assert_called_once_with(
            pod_id, container_name)

    @mock.patch.object(PodCollection, 'stop_unpaid', return_value=None)
    @mock.patch.object(KubeQuery, '_run')
    def test_stop_unpaid(self, _run, _stop_unpaid):
        pod = self.fixtures.pod(status='succeeded', owner=self.user)

        data = {
            'command': 'set',
            'commandOptions': {
                'unpaid': True,
            }
        }
        response = self.open(PodAPIUrl.put(pod.id), 'PUT', data,
                             auth=self.adminauth)
        self.assert200(response)
        assert _stop_unpaid.called
        assert _stop_unpaid.call_args[0][0].id == pod.id


if __name__ == '__main__':
    unittest.main()
