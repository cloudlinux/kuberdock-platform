
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

from random import random, choice, randrange
import unittest
import mock
from string import ascii_letters, digits
from uuid import uuid4
from kubedock.testutils.testcases import APITestCase
from kubedock.billing.models import Package, Kube, INTERNAL_SERVICE_KUBE_TYPE
from kubedock.nodes.models import Node
from kubedock.pods.models import Pod

from kubedock.api.pricing import _format_package_version


def randstr(length=8, symbols=ascii_letters + digits):
    return ''.join(choice(symbols) for i in range(length))


def valid_package(**kwargs):
    return dict({'name': randstr(),
                 'first_deposit': random() * 10,
                 'price_ip': random() * 10,
                 'price_pstorage': random() * 10,
                 'price_over_traffic': random() * 10,
                 'currency': randstr(3),
                 'period': choice(['hour', 'month', 'quarter', 'annual']),
                 'prefix': randstr(),
                 'suffix': randstr(),
                 'is_default': random() > 0.5}, **kwargs)


def valid_kube(**kwargs):
    return dict({'name': randstr(),
                 'cpu': randrange(1, 80) / 8.,
                 'cpu_units': 'Cores',
                 'memory': randrange(1, 99999),
                 'memory_units': 'MB',
                 'disk_space': randrange(1, 999),
                 'disk_space_units': 'GB',
                 'included_traffic': randrange(99999),
                 'is_default': random() > 0.5}, **kwargs)


def valid_package_kube_link(**kwargs):
    return dict({'kube_price': random() * 10, 'id': randrange(8**8)}, **kwargs)


def valid_package_kube(**kwargs):
    return dict({'kube_price': random() * 10}, **valid_kube(**kwargs))


class Url(object):
    kubes = '/pricing/kubes'.format
    kube = '/pricing/kubes/{0}'.format
    kube_default = '/pricing/kubes/default'.format
    packages = '/pricing/packages'.format
    package = '/pricing/packages/{0}'.format
    package_default = '/pricing/packages/default'.format
    package_kubes = '/pricing/packages/{0}/kubes'.format
    package_kube = '/pricing/packages/{0}/kubes/{1}'.format


class ExtendedAPITestCase(APITestCase):
    def setUp(self):
        response = self.admin_open(Url.packages(), 'POST',
                                   valid_package(is_default=False))
        self.package = Package.query.get(response.json['data']['id'])

        response = self.admin_open(Url.kubes(), 'POST',
                                   valid_kube(is_default=False))
        self.kube = Kube.query.get(response.json['data']['id'])

        response = self.admin_open(Url.package_kubes(self.package.id), 'POST',
                                   valid_package_kube_link(id=self.kube.id))
        self.pk = self.package.kubes[0]


class TestPackageCRUD(ExtendedAPITestCase):
    def test_get_one(self):
        response = self.user_open(Url.package(12345))
        self.assertAPIError(response, 404, 'PackageNotFound')

        # user can get only own package
        response = self.user_open(Url.package(self.package.id))
        self.assertAPIError(response, 404, 'PackageNotFound')
        response = self.user_open(Url.package(self.user.package_id))
        self.assert200(response)

        # admin can get any package
        response = self.open(Url.package(self.package.id), auth=self.adminauth)
        self.assert200(response)
        self.assertDictContainsSubset({'name': self.package.name},
                                      response.json['data'])

    def test_get_list(self):
        for i in range(10):
            self.admin_open(Url.packages(), 'POST', valid_package())

        response = self.user_open(Url.packages())
        self.assert200(response)
        # only user's own package
        self.assertEqual(len(response.json['data']), 1)

        response = self.open(Url.packages(), auth=self.adminauth)
        self.assert200(response)
        # 10 + standard + pre-created
        self.assertEqual(len(response.json['data']), 12)

    def test_create(self):
        url = Url.packages()
        response = self.admin_open(url, 'POST', valid_package(
            name=self.package.name))
        self.assertAPIError(response, 400, 'DuplicateName')
        response = self.admin_open(url, 'POST', valid_package(name=''))
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'name': u'empty values not allowed'})
        response = self.admin_open(url, 'POST', valid_package())
        self.assert200(response)

    def test_update(self):
        response = self.admin_open(Url.package(12345), 'PUT', {'name': 'asd'})
        self.assertAPIError(response, 404, 'PackageNotFound')

        response = self.admin_open(Url.package(self.package.id), 'PUT',
                                   valid_package(name=''))
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'name': u'empty values not allowed'})
        response = self.admin_open(Url.package(self.package.id), 'PUT',
                                   valid_package())
        self.assert200(response)

    def test_update_duplicate_name(self):
        self.admin_open(Url.packages(), 'POST',
                        {'name': 'zxc'}).json['data']['id']
        response = self.admin_open(Url.package(self.package.id), 'PUT',
                                   {'name': 'zxc'})
        self.assertAPIError(response, 400, 'DuplicateName')

    def test_update_set_new_default_must_reset_current_default(self):
        default = Package.get_default()
        response = self.admin_open(Url.package(self.package.id), 'PUT',
                                   valid_package(is_default=True))
        self.assert200(response)
        self.assertFalse(default.is_default)

    def test_update_remove_default_flag(self):
        default = self.admin_open(Url.packages(), 'POST',
                                  valid_package(is_default=True))
        response = self.admin_open(Url.package(default.json['data']['id']),
                                   'PUT', valid_package(is_default=False))
        self.assertAPIError(response, 400, 'DefaultPackageNotRemovable')

    def test_delete(self):
        response = self.admin_open(Url.package(12345), 'DELETE')
        self.assertAPIError(response, 404, 'PackageNotFound')
        response = self.admin_open(Url.package(self.package.id), 'DELETE')
        self.assert200(response)

    def test_delete_in_use(self):
        self.user.package = self.package
        self.db.session.commit()

        response = self.admin_open(Url.package(self.package.id), 'DELETE')
        self.assertAPIError(response, 400, 'PackageInUse')

    def test_delete_default(self):
        default = self.admin_open(Url.packages(), 'POST',
                                  valid_package(is_default=True))
        response = self.admin_open(Url.package(
            default.json['data']['id']), 'DELETE')
        self.assertAPIError(response, 400, 'DefaultPackageNotRemovable')

    def test_get_default(self):
        response = self.admin_open(Url.package_default())
        self.assert200(response)


class TestKubeCRUD(ExtendedAPITestCase):
    """Tests for /pricing/kubes and /pricing/package/<pkg>/kubes endpoints."""
    def test_get_not_found(self):
        response = self.admin_open(Url.kube(12345))
        self.assertAPIError(response, 404, 'KubeNotFound')

        response = self.admin_open(Url.kube(self.kube.id))
        self.assert200(response)
        self.assertDictContainsSubset({'name': self.kube.name},
                                      response.json['data'])

        for i in range(10):
            self.admin_open(Url.kubes(), 'POST', valid_kube())
        response = self.admin_open(Url.kubes())
        self.assert200(response)
        # 10 + 3 * standard + pre-created in setUp: no intarnal!
        self.assertEqual(len(response.json['data']), 14)

    def test_create(self):
        response = self.admin_open(Url.kubes(), 'POST', valid_kube(
            name=self.kube.name))
        self.assertAPIError(response, 400, 'DuplicateName')
        response = self.admin_open(Url.kubes(), 'POST', valid_kube(name=''))
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'name': u'empty values not allowed'})

        response = self.admin_open(Url.kubes(), 'POST', valid_kube())
        self.assert200(response)

    def test_create_new_default_must_reset_current_default(self):
        default_kube_id = Kube.get_default_kube_type()
        response = self.admin_open(Url.kubes(), 'POST',
                                   valid_kube(is_default=True))
        self.assert200(response)
        self.assertFalse(Kube.query.get(default_kube_id).is_default)

    def test_update(self):
        response = self.admin_open(Url.kube(12345), 'PUT', {'name': 'asd'})
        self.assertAPIError(response, 404, 'KubeNotFound')

        other = self.admin_open(Url.kubes(), 'POST',
                                valid_kube()).json['data']
        response = self.admin_open(Url.kube(self.kube.id), 'PUT',
                                   {'name': other['name']})
        self.assertAPIError(response, 400, 'DuplicateName')

        response = self.admin_open(Url.kube(self.kube.id), 'PUT', {'name': ''})
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'name': u'empty values not allowed'})

        response = self.admin_open(Url.kube(INTERNAL_SERVICE_KUBE_TYPE), 'PUT',
                                   valid_kube())
        self.assertAPIError(response, 403, 'OperationOnInternalKube')

        response = self.admin_open(Url.kube(self.kube.id), 'PUT', valid_kube())
        self.assert200(response)

    def test_update_set_new_default_must_reset_current_default(self):
        default_kube_id = Kube.get_default_kube_type()
        response = self.admin_open(Url.kube(self.kube.id), 'PUT',
                                   valid_kube(is_default=True))
        self.assert200(response)
        self.assertFalse(Kube.query.get(default_kube_id).is_default)

    def test_update_remove_default_flag(self):
        default = self.admin_open(Url.kubes(), 'POST',
                                  valid_kube(is_default=True))
        response = self.admin_open(Url.kube(default.json['data']['id']), 'PUT',
                                   valid_kube(is_default=False))
        self.assertAPIError(response, 400, 'DefaultKubeNotRemovable')

    def test_delete_not_found(self):
        response = self.admin_open(Url.kube(12345), 'DELETE')
        self.assertAPIError(response, 404, 'KubeNotFound')

        response = self.admin_open(Url.kube(INTERNAL_SERVICE_KUBE_TYPE),
                                   'DELETE')
        self.assertAPIError(response, 403, 'OperationOnInternalKube')

        response = self.admin_open(Url.kube(self.kube.id), 'DELETE')
        self.assert200(response)

    def test_delete_in_use(self):
        self.user.package = self.package

        node = Node(ip='1.2.3.4', hostname='test', kube=self.kube)
        self.db.session.add(node)
        self.db.session.commit()

        response = self.admin_open(Url.kube(self.kube.id), 'DELETE')
        self.assertAPIError(response, 400, 'KubeInUse')

        self.db.session.delete(node)
        pod = Pod(id=str(uuid4()), name='test', owner=self.user,
                  kube=self.kube)
        self.db.session.add(pod)
        self.db.session.commit()

        response = self.admin_open(Url.kube(self.kube.id), 'DELETE')
        self.assertAPIError(response, 400, 'KubeInUse')

    def test_delete_default_kube(self):
        default = self.admin_open(Url.kubes(), 'POST',
                                  valid_kube(is_default=True))
        response = self.admin_open(Url.kube(
            default.json['data']['id']), 'DELETE')
        self.assertAPIError(response, 400, 'DefaultKubeNotRemovable')

    def test_get_default(self):
        response = self.admin_open(Url.kube_default())
        self.assert200(response)


class TestPackageKubeCRUD(ExtendedAPITestCase):
    def test_get_one(self):
        response = self.admin_open(Url.package_kube(12345, self.kube.id))
        self.assertAPIError(response, 404, 'PackageNotFound')
        response = self.admin_open(Url.package_kube(self.package.id, 12345))
        self.assertAPIError(response, 404, 'KubeNotFound')

        response = self.admin_open(Url.package_kube(
            self.package.id, self.kube.id))
        self.assert200(response)
        self.assertDictContainsSubset({'kube_price': self.pk.kube_price,
                                       'id': self.kube.id,
                                       'name': self.kube.name},
                                      response.json['data'])

    def test_get_list(self):
        response = self.admin_open(Url.package_kubes(12345))
        self.assertAPIError(response, 404, 'PackageNotFound')

        url = Url.package_kubes(self.package.id)
        by_id, by_name = [self.kube.id], [self.kube.name]
        for i in range(10):
            kube = valid_package_kube()
            by_id.append(self.admin_open(url, 'POST',
                                         kube).json['data']['kube_id'])
            by_name.append(kube['name'])
        expected = 11  # 10 + pre-created in setUp

        response = self.admin_open(url)
        self.assert200(response)
        self.assertEqual(len(response.json['data']), expected)

        response = self.admin_open(Url.package_kubes(12345) + '-by-id')
        self.assertAPIError(response, 404, 'PackageNotFound')
        response = self.admin_open(url + '-by-id')
        self.assert200(response)
        self.assertItemsEqual(response.json['data'], by_id)

        response = self.admin_open(Url.package_kubes(12345) + '-by-name')
        self.assertAPIError(response, 404, 'PackageNotFound')
        response = self.admin_open(url + '-by-name')
        self.assert200(response)
        self.assertItemsEqual(response.json['data'], by_name)

        self.user.package = self.package
        self.db.session.commit()
        response = self.user_open('/pricing/userpackage')
        self.assertEqual(len(response.json['data']), expected)

    def test_create(self):
        response = self.admin_open(Url.package_kubes(12345), 'POST',
                                   valid_package_kube(name=self.kube.name))
        self.assertAPIError(response, 404, 'PackageNotFound')

        url = Url.package_kubes(self.package.id)
        response = self.admin_open(url, 'POST', valid_package_kube(id=12345))
        self.assertAPIError(response, 404, 'KubeNotFound')
        response = self.admin_open(url, 'POST',
                                   valid_package_kube(name=self.kube.name))
        self.assertAPIError(response, 400, 'DuplicateName')
        response = self.admin_open(url, 'POST', valid_package_kube(name=''))
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'name': u'empty values not allowed'})

        response = self.admin_open(url, 'POST', valid_package_kube())
        self.assert200(response)

    def test_create_new_default_must_reset_current_default(self):
        default_kube_id = Kube.get_default_kube_type()
        response = self.admin_open(Url.package_kubes(self.package.id), 'POST',
                                   valid_package_kube(is_default=True))
        self.assert200(response)
        self.assertFalse(Kube.query.get(default_kube_id).is_default)

    def test_update(self):
        response = self.admin_open(Url.package_kube(12345, self.kube.id),
                                   'PUT',
                                   valid_package_kube_link())
        self.assertAPIError(response, 404, 'PackageNotFound')
        response = self.admin_open(Url.package_kube(self.package.id, 12345),
                                   'PUT',
                                   valid_package_kube_link())
        self.assertAPIError(response, 404, 'KubeNotFound')

        response = self.admin_open(
            Url.package_kube(self.package.id, INTERNAL_SERVICE_KUBE_TYPE),
            'PUT', valid_package_kube_link(id=self.kube.id))
        self.assertAPIError(response, 403, 'OperationOnInternalKube')

        response = self.admin_open(Url.package_kube(
            self.package.id, self.kube.id), 'PUT',
            valid_package_kube_link(id=self.kube.id))
        self.assert200(response)

    def test_delete(self):
        response = self.admin_open(Url.package_kube(self.package.id, 12345),
                                   'DELETE')
        self.assertAPIError(response, 404, 'KubeNotFound')
        response = self.admin_open(Url.package_kube(12345, self.kube.id),
                                   'DELETE')
        self.assertAPIError(response, 404, 'KubeNotFound')

        url = Url.package_kube(self.package.id, self.kube.id)
        response = self.admin_open(url, 'DELETE')
        self.assert200(response)

    def test_delete_in_use(self):
        self.user.package = self.package

        pod = Pod(id=str(uuid4()), name='test', owner=self.user,
                  kube=self.kube)
        self.db.session.add(pod)
        self.db.session.commit()

        url = Url.package_kube(self.package.id, self.kube.id)
        response = self.admin_open(url, 'DELETE')
        self.assertAPIError(response, 400, 'KubeInUse')


class TestPricingSSE(ExtendedAPITestCase):
    def setUp(self):
        super(TestPricingSSE, self).setUp()
        self.user_1, _ = self.fixtures.user_fixtures()
        self.user_2, _ = self.fixtures.user_fixtures()
        self.user_1.package_id = self.package.id
        self.db.session.commit()

        user_patcher = mock.patch('kubedock.billing.models.send_event_to_user')
        role_patcher = mock.patch('kubedock.billing.models.send_event_to_role')
        self.addCleanup(user_patcher.stop)
        self.addCleanup(role_patcher.stop)
        self.send_user_event_mock = user_patcher.start()
        self.send_role_event_mock = role_patcher.start()

    def test_kube_change(self):
        self.admin_open(Url.kube(self.kube.id), 'PUT', valid_kube())
        updated = self.kube.to_dict()
        self.send_user_event_mock.assert_called_once_with(
            'kube:change', updated, self.user_1.id)
        self.send_role_event_mock.assert_called_once_with(
            'kube:change', updated, 1)


class TestLicense(APITestCase):
    url = '/pricing/license'

    @mock.patch('kubedock.api.pricing.get_collection')
    @mock.patch('kubedock.api.pricing.process_collection')
    def test_get_license(self, process_collection, get_collection):
        process_collection.return_value = {}
        self.assert200(self.admin_open())
        get_collection.assert_called_once_with(False)
        # TODO: cover `process_collection` with unittests
        process_collection.assert_called_once_with(get_collection.return_value)

    @mock.patch('kubedock.api.pricing.licensing')
    @mock.patch('kubedock.api.pricing.collect')
    @mock.patch('kubedock.api.pricing.process_collection')
    def test_set_installation_id(self, process_collection, collect, licensing):
        process_collection.return_value = {}
        collect.send.return_value = {'status': 'OK'}

        url = '{0}/installation_id'.format(self.url)
        installation_id = str(uuid4())
        response = self.admin_open(
            url, 'POST', json={'value': installation_id})
        self.assert200(response)

        licensing.update_installation_id.assert_called_once_with(
            installation_id)
        collect.collect.assert_called_once_with()
        collect.send.assert_called_once_with(collect.collect.return_value)
        # TODO: cover `process_collection` with unittests
        process_collection.assert_called_once_with(
            collect.collect.return_value)


class TestUtils(unittest.TestCase):
    """Tests for helper functions."""

    def test_format_package_version(self):
        version = '1.0-1.el7.centos.rc.1.cloudlinux.noarch'
        self.assertEqual(_format_package_version(version), '1.0-1.rc.1')

        version = 'qwerty'
        self.assertEqual(_format_package_version(version), version)

        version = '1.0.3-0.1.git61c6ac5.el7.centos.2.x86_64'
        self.assertEqual(_format_package_version(version), '1.0.3-0.1')

        self.assertIsNone(_format_package_version(None))


if __name__ == '__main__':
    unittest.main()
