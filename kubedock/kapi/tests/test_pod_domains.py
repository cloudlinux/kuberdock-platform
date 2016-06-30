from collections import namedtuple
import unittest
import mock

from kubedock.testutils.testcases import FlaskTestCase
from kubedock.testutils import create_app
from kubedock.exceptions import NotFound

from kubedock.kapi import pod_domains


class TestCase(FlaskTestCase):
    def create_app(self):
        return create_app(self)


class TestCheckDomain(TestCase):

    @mock.patch.object(pod_domains, 'BaseDomain')
    def test_check_comain(self, domain_mock):
        # domain not found
        domain_mock.query.filter_by.return_value.first.return_value = None
        with self.assertRaises(NotFound):
            pod_domains.check_domain('example.com')

        # domain found
        domain = mock.Mock()
        domain_mock.query.filter_by.return_value.first.return_value = domain
        rv = pod_domains.check_domain('example.com')
        self.assertEqual(rv, domain)


Pod = namedtuple('Pod', ('id', 'name', 'owner'))
User = namedtuple('User', ('username',))


class TestSetPodDomain(TestCase):

    def setUp(self):
        self.pod = Pod(
            id='qwerty', name='pod', owner=User(username='user'))
        self.pod_domain_name = '{0}-{1}'.format(
            self.pod.owner.username, self.pod.name)

    @mock.patch.object(pod_domains, '_get_unique_domain_name')
    @mock.patch.object(pod_domains, 'db')
    @mock.patch.object(pod_domains, 'PodDomain')
    def test_set_pod_name(self, pod_domain_mock, db_mock,
                          get_unique_domain_name_mock):
        domain_id = 1234
        pod_domain = mock.Mock()
        pod_domain_mock.return_value = pod_domain
        pod_domain_mock.query.filter_by.return_value.first.return_value = None
        get_unique_domain_name_mock.side_effect = lambda basename, _: basename

        # non unique domain
        rv1 = pod_domains.set_pod_domain(self.pod, domain_id)
        pod_domain_mock.assert_called_once_with(
            name=self.pod_domain_name,
            domain_id=domain_id,
            pod_id=self.pod.id
        )

        pod_domain_mock.reset_mock()

        # unique domain
        pod_domain_mock.query.filter_by.return_value.first.return_value = None
        rv2 = pod_domains.set_pod_domain(self.pod, domain_id)

        pod_domain_mock.assert_called_once_with(
            name=self.pod_domain_name,
            domain_id=domain_id,
            pod_id=self.pod.id
        )
        self.assertEqual((rv1, rv2), (pod_domain, pod_domain))
        self.assertEqual(db_mock.session.add.call_count, 2)

    @mock.patch.object(pod_domains, 'randstr')
    @mock.patch.object(pod_domains, 'PodDomain')
    def test_get_unique_domain_name(self, pod_domain_mock, randstr_mock):
        query_first_mock = mock.Mock()
        pod_domain_mock.query.filter_by.return_value.first = query_first_mock
        query_first_mock.return_value = None
        dname = 'qwerty1234'
        domain_id = 22
        res = pod_domains._get_unique_domain_name(dname, domain_id)
        self.assertEqual(res, dname)
        pod_domain_mock.query.filter_by.assert_called_once_with(
            name=dname, domain_id=domain_id)
        pod_domain_mock.query.filter_by.reset_mock()

        # if the first call returns som object, the to basename must be
        # appended random suffix
        query_first_mock.reset_mock()
        query_first_mock.side_effect = ['something', 'somethingelse', None]
        random_suffix = 'sfsfd'
        randstr_mock.return_value = random_suffix
        res = pod_domains._get_unique_domain_name(dname, domain_id)
        self.assertEqual(dname + random_suffix, res)
        self.assertEqual(randstr_mock.call_count, 2)
        self.assertEqual(pod_domain_mock.query.filter_by.call_count, 3)
        pod_domain_mock.query.filter_by.assert_called_with(
            name=dname + random_suffix, domain_id=domain_id)


if __name__ == '__main__':
    unittest.main()
