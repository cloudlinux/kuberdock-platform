import unittest
import mock

from kubedock.testutils.testcases import APITestCase
from kubedock.core import db
from kubedock.domains.models import BaseDomain, PodDomain


class TestDomains(APITestCase):

    @mock.patch('kubedock.api.domains.prepare_ip_sharing')
    def test_create_domain(self, prepare_ip_sharing_mock):
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
        self.assert400(response)

        # check creation of the same domain
        response = self.admin_open('/domains/', method='POST',
                                   json={'name': test_name})
        self.assertStatus(response, 409)

        # check another domain creation
        test_name2 = 'qwerty.com'
        response = self.admin_open('/domains/', method='POST',
                                   json={'name': test_name2})
        self.assert200(response)
        domain_dict = response.json['data']
        self.assertEqual(domain_dict['name'], test_name2)
        dbdomains = db.session.query(BaseDomain).all()
        self.assertEqual(len(dbdomains), 2)

    def test_eidt_domain(self):
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
        self.assertStatus(response, 409)

        # check update not existing domain
        response = self.admin_open('/domains/{}'.format(323232), method='PUT',
                                   json={'name': test_name2})
        self.assert404(response)

    def test_delete_domain(self):
        response = self.admin_open('/domains/{}'.format(123), method='DELETE')
        self.assert404(response)

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
        self.assert404(response)

        dbpodomain = PodDomain(
            domain_id=id1,
            name='qwerty',
            pod_id=None)
        db.session.add(dbpodomain)
        db.session.commit()
        response = self.admin_open('/domains/{}'.format(id1), method='DELETE')
        self.assertStatus(response, 409)


if __name__ == '__main__':
    unittest.main()
