import unittest

import mock

from kubedock.core import db
from kubedock.domains.models import BaseDomain, PodDomain
from kubedock.testutils import fixtures
from kubedock.testutils.testcases import APITestCase

global_patchers = [
    mock.patch('kubedock.kapi.ingress.is_subsystem_up', return_value=False),
    mock.patch('kubedock.kapi.ingress.check_subsystem_up_preconditions'),
    mock.patch('kubedock.kapi.ingress.prepare_ip_sharing_task')
]


def setUpModule():
    for patcher in global_patchers:
        patcher.start()


def tearDownModule():
    for patcher in global_patchers:
        patcher.stop()


class TestDomains(APITestCase):
    @mock.patch('kubedock.kapi.ingress.is_subsystem_up')
    @mock.patch('kubedock.kapi.ingress.prepare_ip_sharing_task.si')
    @mock.patch('kubedock.dns_management.check_if_zone_exists')
    def test_create_domain_with_absent_zone(
            self, check_if_zone_exists_mock, prepare_ip_sharing_mock,
            is_system_up_mock
    ):
        check_if_zone_exists_mock.return_value = (False, None)
        is_system_up_mock.return_value = False
        test_name = 'example.com'
        response = self.admin_open('/domains/', method='POST',
                                   json={'name': test_name})
        self.assert404(response)
        self.assertFalse(prepare_ip_sharing_mock.called)
        self.assertIsNone(BaseDomain.filter_by(name=test_name).first())

    @mock.patch('kubedock.kapi.ingress.is_subsystem_up')
    @mock.patch('kubedock.kapi.ingress.prepare_ip_sharing_task.si')
    @mock.patch('kubedock.dns_management.check_if_zone_exists')
    def test_ingress_up_called_at_first_call(
            self, check_if_zone_exists_mock, prepare_ip_sharing_mock,
            is_system_up_mock
    ):
        check_if_zone_exists_mock.return_value = (True, None)
        is_system_up_mock.return_value = False
        test_name = 'example.com'
        response = self.admin_open('/domains/', method='POST',
                                   json={'name': test_name})
        self.assert200(response)
        self.assertTrue(prepare_ip_sharing_mock.called)

    @mock.patch('kubedock.kapi.ingress.is_subsystem_up')
    @mock.patch('kubedock.kapi.ingress.prepare_ip_sharing_task.si')
    @mock.patch('kubedock.dns_management.check_if_zone_exists')
    def test_ingress_up_not_called_again(
            self, check_if_zone_exists_mock, prepare_ip_sharing_mock,
            is_system_up_mock
    ):
        check_if_zone_exists_mock.return_value = (True, None)
        is_system_up_mock.return_value = True
        test_name = 'example.com'
        response = self.admin_open('/domains/', method='POST',
                                   json={'name': test_name})
        self.assert200(response)
        self.assertFalse(prepare_ip_sharing_mock.called)

    @mock.patch('kubedock.kapi.ingress.prepare_ip_sharing_task.si')
    @mock.patch('kubedock.dns_management.check_if_zone_exists')
    def test_create_domain(self, check_if_zone_exists_mock,
                           prepare_ip_sharing_mock):
        check_if_zone_exists_mock.return_value = (True, None)
        test_name = 'example.com'
        response = self.admin_open('/domains/', method='POST',
                                   json={'name': test_name})
        self.assert200(response)
        self.assertTrue(prepare_ip_sharing_mock.called)
        domain_dict = response.json['data']
        self.assertEqual(domain_dict['name'], test_name)
        dbdomains = db.session.query(BaseDomain).filter(
            BaseDomain.name == test_name).all()
        self.assertEqual(len(dbdomains), 1)
        self.assertEqual(domain_dict['id'], dbdomains[0].id)

        # check query with missed 'name' field
        response = self.admin_open('/domains/', method='POST',
                                   json={'no name': 'field'})
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'name': u'required field'})

        # check query with invalid 'name' field
        response = self.admin_open('/domains/', method='POST',
                                   json={'name': '!@#$%^&'})
        self.assertAPIError(response, 400, 'ValidationError',
                            {u'name': u'invalid domain'})

        # check creation of the same domain
        response = self.admin_open('/domains/', method='POST',
                                   json={'name': test_name})
        self.assertAPIError(response, 409, 'AlreadyExistsError')

        # check another domain creation
        test_name2 = 'qwerty.com'
        response = self.admin_open('/domains/', method='POST',
                                   json={'name': test_name2})
        self.assert200(response)
        domain_dict = response.json['data']
        self.assertEqual(domain_dict['name'], test_name2)
        dbdomains = db.session.query(BaseDomain).all()
        self.assertEqual(len(dbdomains), 2)

    @mock.patch('kubedock.kapi.ingress.prepare_ip_sharing_task.si')
    @mock.patch('kubedock.dns_management.check_if_zone_exists')
    def test_domain_creation_with_missing_certificate_fails(
            self, check_if_zone_exists_mock, prepare_ip_sharing_mock):
        check_if_zone_exists_mock.return_value = (True, None)
        data = {'name': 'somedomain.com', 'certificate': {}}
        response = self.admin_open('/domains/', method='POST', json=data)

        self.assert400(response)

    @mock.patch('kubedock.kapi.ingress.prepare_ip_sharing_task.si')
    @mock.patch('kubedock.dns_management.check_if_zone_exists')
    def test_domain_creation_with_incorrect_certificate_fails(
            self, check_if_zone_exists_mock, prepare_ip_sharing_mock):
        check_if_zone_exists_mock.return_value = (True, None)
        data = {
            'name': 'example.com',
            'certificate': fixtures.sample_certificate
        }

        data['certificate']['cert'] = 'some thrash'
        response = self.admin_open('/domains/', method='POST', json=data)
        self.assert400(response)

    @mock.patch('kubedock.kapi.ingress.prepare_ip_sharing_task.si')
    @mock.patch('kubedock.dns_management.check_if_zone_exists')
    def test_domain_creation_with_incorrect_private_key_fails(
            self, check_if_zone_exists_mock, prepare_ip_sharing_mock):
        check_if_zone_exists_mock.return_value = (True, None)
        data = {
            'name': 'example.com',
            'certificate': fixtures.sample_certificate
        }

        data['certificate']['key'] = 'some thrash'
        response = self.admin_open('/domains/', method='POST', json=data)
        self.assert400(response)

    @mock.patch('kubedock.kapi.ingress.prepare_ip_sharing_task.si')
    @mock.patch('kubedock.dns_management.check_if_zone_exists')
    def test_domain_creation_with_certificate_fails_if_domain_does_not_match(
            self, check_if_zone_exists_mock, prepare_ip_sharing_mock):
        check_if_zone_exists_mock.return_value = (True, None)
        data = {
            'name': 'nonmatchingdomain.com',
            'certificate': fixtures.sample_certificate
        }
        response = self.admin_open('/domains/', method='POST', json=data)

        self.assert400(response)

    @mock.patch('kubedock.kapi.ingress.prepare_ip_sharing_task.delay')
    @mock.patch('kubedock.dns_management.check_if_zone_exists')
    def test_domain_creation_with_correct_certificate_succeeds(
            self, check_if_zone_exists_mock, prepare_ip_sharing_mock):
        check_if_zone_exists_mock.return_value = (True, None)
        data = {
            'name': 'example.com',
            'certificate': fixtures.sample_certificate
        }
        response = self.admin_open('/domains/', method='POST', json=data)

        self.assert200(response)

        dbdomains = BaseDomain.query.filter_by(name=data['name']).all()
        self.assertEqual(len(dbdomains), 1)
        self.assertEqual(dbdomains[0].certificate, data['certificate'])

    def test_edit_domain(self):
        test_name1 = 'example1.com'
        test_name2 = 'example2.com'
        dbdomain = BaseDomain(name=test_name1)
        db.session.add(dbdomain)
        db.session.commit()
        id1 = dbdomain.id

        response = self.admin_open('/domains/{}'.format(id1), method='PUT',
                                   json={'name': test_name2})
        self.assert200(response)
        domain_dict = response.json['data']
        self.assertEqual(domain_dict['name'], test_name2)
        self.assertEqual(domain_dict['id'], id1)
        dbdomains = db.session.query(BaseDomain).all()
        self.assertEqual(len(dbdomains), 1)
        self.assertEqual(dbdomains[0].name, test_name2)

        dbdomain = BaseDomain(name=test_name1)
        db.session.add(dbdomain)
        db.session.commit()
        id3 = dbdomain.id

        # check update domain name to already existing one
        response = self.admin_open('/domains/{}'.format(id3), method='PUT',
                                   json={'name': test_name2})
        self.assertAPIError(response, 409, 'AlreadyExistsError')

        # check update not existing domain
        response = self.admin_open('/domains/{}'.format(323232), method='PUT',
                                   json={'name': test_name2})
        self.assertAPIError(response, 404, 'DomainNotFound')

    def test_delete_domain(self):
        response = self.admin_open('/domains/{}'.format(123), method='DELETE')
        self.assertAPIError(response, 404, 'DomainNotFound')

        test_name1 = 'example1.com'
        test_name2 = 'example2.com'
        dbdomain1 = BaseDomain(name=test_name1)
        dbdomain2 = BaseDomain(name=test_name2)
        db.session.add_all((dbdomain1, dbdomain2))
        db.session.commit()
        id1 = dbdomain1.id
        id2 = dbdomain2.id

        response = self.admin_open('/domains/{}'.format(id2), method='DELETE')
        self.assert200(response)
        dbdomains = db.session.query(BaseDomain).all()
        self.assertEqual(len(dbdomains), 1)
        self.assertEqual(dbdomains[0].id, id1)
        response = self.admin_open('/domains/{}'.format(id2), method='DELETE')
        self.assertAPIError(response, 404, 'DomainNotFound')

        dbpodomain = PodDomain(
            domain_id=id1,
            name='qwerty',
            pod_id=None)
        db.session.add(dbpodomain)
        db.session.commit()
        response = self.admin_open('/domains/{}'.format(id1), method='DELETE')
        self.assertAPIError(response, 409, 'CannotBeDeletedError')


if __name__ == '__main__':
    unittest.main()
