from random import random, choice, randrange
import unittest
from string import ascii_letters, digits
from uuid import uuid4
from kubedock.testutils.testcases import APITestCase
from kubedock.billing.models import Package, Kube, INTERNAL_SERVICE_KUBE_TYPE
from kubedock.nodes.models import Node
from kubedock.pods.models import Pod


def randstr(length=8, symbols=ascii_letters + digits):
    return ''.join(choice(symbols) for i in range(length))


def valid_package(**kwargs):
    return dict({'name': randstr(),
                 'first_deposit': random() * 10,
                 'price_ip': random() * 10,
                 'price_pstorage': random() * 10,
                 'price_over_traffic': random() * 10,
                 'currency': randstr(3),
                 'period': choice(['hour', 'month', 'quarter', 'annuel']),
                 'prefix': randstr(),
                 'suffix': randstr()}, **kwargs)


def valid_kube(**kwargs):
    return dict({'name': randstr(),
                 'cpu': 0.01 + random() * 9.98,
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
    packages = '/pricing/packages'.format
    package = '/pricing/packages/{0}'.format
    package_kubes = '/pricing/packages/{0}/kubes'.format
    package_kube = '/pricing/packages/{0}/kubes/{1}'.format


class ExtendedAPITestCase(APITestCase):
    def setUp(self):
        response = self.admin_open(Url.packages(), 'POST', valid_package())
        self.package = Package.query.get(response.json['data']['id'])

        response = self.admin_open(Url.kubes(), 'POST', valid_kube(is_default=False))
        self.kube = Kube.query.get(response.json['data']['id'])

        response = self.admin_open(Url.package_kubes(self.package.id), 'POST',
                                   valid_package_kube_link(id=self.kube.id))
        self.pk = self.package.kubes[0]


class TestPackageCRUD(ExtendedAPITestCase):
    def test_get_not_found(self):
        response = self.admin_open(Url.package(12345))
        self.assertAPIError(response, 404, 'PackageNotFound')

    def test_get_one(self):
        response = self.admin_open(Url.package(12345))
        self.assertAPIError(response, 404, 'PackageNotFound')

        response = self.admin_open(Url.package(self.package.id))
        self.assert200(response)
        self.assertDictContainsSubset({'name': self.package.name}, response.json['data'])

    def test_get_list(self):
        for i in range(10):
            self.admin_open(Url.packages(), 'POST', valid_package())
        response = self.admin_open(Url.packages())
        self.assert200(response)
        self.assertEqual(len(response.json['data']), 12)  # 10 + standard + pre-created

    def test_create(self):
        url = Url.packages()
        response = self.admin_open(url, 'POST', valid_package(name=self.package.name))
        self.assertAPIError(response, 400, 'DuplicateName')
        response = self.admin_open(url, 'POST', valid_package(name=''))
        self.assertAPIError(response, 400, 'ValidationError')
        response = self.admin_open(url, 'POST', valid_package())
        self.assert200(response)

    def test_update(self):
        response = self.admin_open(Url.package(12345), 'PUT', {'name': 'asd'})
        self.assertAPIError(response, 404, 'PackageNotFound')

        response = self.admin_open(Url.package(self.package.id), 'PUT',
                                   valid_package(name=''))
        self.assertAPIError(response, 400, 'ValidationError')
        response = self.admin_open(Url.package(self.package.id), 'PUT', valid_package())
        self.assert200(response)

    def test_update_duplicate_name(self):
        self.admin_open(Url.packages(), 'POST', {'name': 'zxc'}).json['data']['id']
        response = self.admin_open(Url.package(self.package.id), 'PUT', {'name': 'zxc'})
        self.assertAPIError(response, 400, 'DuplicateName')

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


class TestKubeCRUD(ExtendedAPITestCase):
    """Tests for /pricing/kubes and /pricing/package/<pkg>/kubes endpoints."""
    def test_get_not_found(self):
        response = self.admin_open(Url.kube(12345))
        self.assertAPIError(response, 404, 'KubeNotFound')

        response = self.admin_open(Url.kube(self.kube.id))
        self.assert200(response)
        self.assertDictContainsSubset({'name': self.kube.name}, response.json['data'])

        for i in range(10):
            self.admin_open(Url.kubes(), 'POST', valid_kube())
        response = self.admin_open(Url.kubes())
        self.assert200(response)
        # 10 + 3 * standard + pre-created in setUp: no intarnal!
        self.assertEqual(len(response.json['data']), 14)

    def test_create(self):
        response = self.admin_open(Url.kubes(), 'POST', valid_kube(name=self.kube.name))
        self.assertAPIError(response, 400, 'DuplicateName')
        response = self.admin_open(Url.kubes(), 'POST', valid_kube(name=''))
        self.assertAPIError(response, 400, 'ValidationError')

        response = self.admin_open(Url.kubes(), 'POST', valid_kube())
        self.assert200(response)

    def test_create_new_default_must_reset_current_default(self):
        default_kube_id = Kube.get_default_kube_type()
        response = self.admin_open(Url.kubes(), 'POST', valid_kube(is_default=True))
        self.assert200(response)
        self.assertFalse(Kube.query.get(default_kube_id).is_default)

    def test_update(self):
        response = self.admin_open(Url.kube(12345), 'PUT', {'name': 'asd'})
        self.assertAPIError(response, 404, 'KubeNotFound')

        other = self.admin_open(Url.kubes(), 'POST', valid_kube()).json['data']
        response = self.admin_open(Url.kube(self.kube.id), 'PUT', {'name': other['name']})
        self.assertAPIError(response, 400, 'DuplicateName')

        response = self.admin_open(Url.kube(self.kube.id), 'PUT', {'name': ''})
        self.assertAPIError(response, 400, 'ValidationError')

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
        default = self.admin_open(Url.kubes(), 'POST', valid_kube(is_default=True))
        response = self.admin_open(Url.kube(default.json['data']['id']), 'PUT',
                                   valid_kube(is_default=False))
        self.assertAPIError(response, 400, 'DefaultKubeNotRemovable')

    def test_delete_not_found(self):
        response = self.admin_open(Url.kube(12345), 'DELETE')
        self.assertAPIError(response, 404, 'KubeNotFound')

        response = self.admin_open(Url.kube(INTERNAL_SERVICE_KUBE_TYPE), 'DELETE')
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
        pod = Pod(id=str(uuid4()), name='test', owner=self.user, kube=self.kube)
        self.db.session.add(pod)
        self.db.session.commit()

        response = self.admin_open(Url.kube(self.kube.id), 'DELETE')
        self.assertAPIError(response, 400, 'KubeInUse')

    def test_delete_default_kube(self):
        default = self.admin_open(Url.kubes(), 'POST', valid_kube(is_default=True))
        response = self.admin_open(Url.kube(default.json['data']['id']), 'DELETE')
        self.assertAPIError(response, 400, 'DefaultKubeNotRemovable')


class TestPackageKubeCRUD(ExtendedAPITestCase):
    def test_get_one(self):
        response = self.admin_open(Url.package_kube(12345, self.kube.id))
        self.assertAPIError(response, 404, 'PackageNotFound')
        response = self.admin_open(Url.package_kube(self.package.id, 12345))
        self.assertAPIError(response, 404, 'KubeNotFound')

        response = self.admin_open(Url.package_kube(self.package.id, self.kube.id))
        self.assert200(response)
        self.assertDictContainsSubset({'kube_price': self.pk.kube_price,
                                       'id': self.kube.id, 'name': self.kube.name},
                                      response.json['data'])

    def test_get_list(self):
        response = self.admin_open(Url.package_kubes(12345))
        self.assertAPIError(response, 404, 'PackageNotFound')

        url = Url.package_kubes(self.package.id)
        by_id, by_name = [self.kube.id], [self.kube.name]
        for i in range(10):
            kube = valid_package_kube()
            by_id.append(self.admin_open(url, 'POST', kube).json['data']['kube_id'])
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
        response = self.open('/pricing/userpackage')
        self.assertAPIError(response, 401, 'NotAuthorized')
        response = self.open('/pricing/userpackage', auth=self.userauth)
        self.assertEqual(len(response.json['data']), expected)

    def test_create(self):
        response = self.admin_open(Url.package_kubes(12345), 'POST',
                                   valid_package_kube(name=self.kube.name))
        self.assertAPIError(response, 404, 'PackageNotFound')

        url = Url.package_kubes(self.package.id)
        response = self.admin_open(url, 'POST', valid_package_kube(id=12345))
        self.assertAPIError(response, 404, 'KubeNotFound')
        response = self.admin_open(url, 'POST', valid_package_kube(name=self.kube.name))
        self.assertAPIError(response, 400, 'DuplicateName')
        response = self.admin_open(url, 'POST', valid_package_kube(name=''))
        self.assertAPIError(response, 400, 'ValidationError')

        response = self.admin_open(url, 'POST', valid_package_kube())
        self.assert200(response)

    def test_create_new_default_must_reset_current_default(self):
        default_kube_id = Kube.get_default_kube_type()
        response = self.admin_open(Url.package_kubes(self.package.id), 'POST',
                                   valid_package_kube(is_default=True))
        self.assert200(response)
        self.assertFalse(Kube.query.get(default_kube_id).is_default)

    def test_update(self):
        response = self.admin_open(Url.package_kube(12345, self.kube.id), 'PUT',
                                   valid_package_kube_link())
        self.assertAPIError(response, 404, 'PackageNotFound')
        response = self.admin_open(Url.package_kube(self.package.id, 12345), 'PUT',
                                   valid_package_kube_link())
        self.assertAPIError(response, 404, 'KubeNotFound')

        response = self.admin_open(
            Url.package_kube(self.package.id, INTERNAL_SERVICE_KUBE_TYPE),
            'PUT', valid_package_kube_link(id=self.kube.id))
        self.assertAPIError(response, 403, 'OperationOnInternalKube')

        response = self.admin_open(Url.package_kube(self.package.id, self.kube.id),
                                   'PUT', valid_package_kube_link(id=self.kube.id))
        self.assert200(response)

    def test_delete(self):
        response = self.admin_open(Url.package_kube(self.package.id, 12345), 'DELETE')
        self.assertAPIError(response, 404, 'KubeNotFound')
        response = self.admin_open(Url.package_kube(12345, self.kube.id), 'DELETE')
        self.assertAPIError(response, 404, 'KubeNotFound')

        url = Url.package_kube(self.package.id, self.kube.id)
        response = self.admin_open(url, 'DELETE')
        self.assert200(response)

    def test_delete_in_use(self):
        self.user.package = self.package

        pod = Pod(id=str(uuid4()), name='test', owner=self.user, kube=self.kube)
        self.db.session.add(pod)
        self.db.session.commit()

        url = Url.package_kube(self.package.id, self.kube.id)
        response = self.admin_open(url, 'DELETE')
        self.assertAPIError(response, 400, 'KubeInUse')


if __name__ == '__main__':
    unittest.main()
