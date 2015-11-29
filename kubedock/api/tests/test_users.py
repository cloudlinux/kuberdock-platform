import unittest
import logging
import pytz
from ipaddress import ip_address
from kubedock.testutils.testcases import APITestCase, attr
from kubedock.testutils import fixtures

from uuid import uuid4
from kubedock.core import db
from kubedock.users.models import User
from kubedock.pods.models import Pod
from kubedock.billing.models import Package, PackageKube, Kube


class UserFullTestCase(APITestCase):
    """Tests for /api/users/full endpoint"""
    url = '/users/full'

    def setUp(self):
        super(UserFullTestCase, self).setUp()
        self.user, user_password = fixtures.user_fixtures()
        self.admin, admin_password = fixtures.admin_fixtures()
        self.userauth = (self.user.username, user_password)
        self.adminauth = (self.admin.username, admin_password)

    # @unittest.skip('')
    def test_get(self):
        # get list
        self.assert401(self.open())
        self.assert403(self.open(auth=self.userauth))
        response = self.open(auth=self.adminauth)
        self.assert200(response)  # only Admin has permission
        user, admin = self.user.to_dict(full=True), self.admin.to_dict(full=True)
        user['join_date'] = user['join_date'].replace(tzinfo=pytz.utc).isoformat()
        admin['join_date'] = admin['join_date'].replace(tzinfo=pytz.utc).isoformat()
        self.assertIn(user, response.json['data'])
        self.assertIn(admin, response.json['data'])

    # @unittest.skip('')
    def test_post(self):
        data = dict(username='test_post_users',
                    first_name='', last_name='', middle_initials='',
                    password='p-0', email='test_user@test.test',
                    active=True, rolename='User', package='Standard package')

        # add
        self.assert401(self.open(method='POST', json=data))
        self.assert403(self.open(method='POST', json=data, auth=self.userauth))
        response = self.open(method='POST', json=data, auth=self.adminauth)
        self.assert200(response)  # only Admin has permission
        self.assertDictContainsSubset(data, response.json['data'])

        # check conversion of extended boolean fields
        data['username'] += '1'
        data['email'] = '1' + data['email']
        data['active'] = 'TrUe'
        response = self.open(method='POST', json=data, auth=self.adminauth)
        self.assert200(response)  # active is valid
        self.assertEqual(response.json['data']['active'], True)

        data['username'] += '1'
        data['email'] = '1' + data['email']
        data['suspended'] = '1'
        response = self.open(method='POST', json=data, auth=self.adminauth)
        self.assert200(response)  # suspended is valid
        self.assertEqual(response.json['data']['suspended'], True)

    # @unittest.skip('')
    def test_put(self):
        new_package = Package(id=1, name='New package', first_deposit=0,
                              currency='USD', period='hour', prefix='$',
                              suffix=' USD')
        db.session.add(new_package)
        db.session.commit()
        data = dict(password='new_password', email='new_email@test.test',
                    first_name='fn', last_name='ln',
                    middle_initials='mi', rolename='Admin',
                    package=new_package.name)

        # update
        url = '{0}/{1}'.format(self.url, self.user.id)
        self.assert401(self.open(url=url, method='PUT', json=data))
        self.assert403(self.open(url=url, method='PUT', json=data, auth=self.userauth))
        response = self.open(url=url, method='PUT', json=data, auth=self.adminauth)
        self.assert200(response)  # only Admin has permission

        user = User.query.get(self.user.id)
        self.assertTrue(user.verify_password(data.pop('password')))
        self.assertEqual(data.pop('package'), user.package.name)
        self.assertEqual(data.pop('rolename'), user.role.rolename)
        for field, value in data.iteritems():
            self.assertEqual(value, getattr(user, field))

    # @unittest.skip('')
    @attr('k8s')
    def test_delete(self):
        # delete
        logging.getLogger('UserFullTestCase.delete').info(
            'This test will work only with k8s.')
        url = '{0}/{1}'.format(self.url, self.user.id)
        self.assert401(self.open(url=url, method='DELETE'))
        self.assert403(self.open(url=url, method='DELETE', auth=self.userauth))
        response = self.open(url=url, method='DELETE', auth=self.adminauth)
        self.assert200(response)  # only Admin has permission

        self.assertIsNone(User.not_deleted.filter_by(id=self.user.id).first())

    # @unittest.skip('')
    def test_change_package(self, *args):
        """
        AC-1003
        If new package lacks kube_types, that used in user's pods,
        then forbid this change.
        """
        user = self.user
        url = '{0}/{1}'.format(self.url, user.id)
        package0 = user.package
        package1 = Package(id=1, name='New package', first_deposit=0,
                           currency='USD', period='hour', prefix='$',
                           suffix=' USD')
        kube0, kube1, kube2 = Kube.public_kubes().all()
        # new package allows only standard kube
        PackageKube(packages=package1, kubes=kube0, kube_price=0)
        db.session.commit()

        # change package: user still doesn't have pods
        data = {'package': package1.name}
        self.assert401(self.open(url=url, method='PUT', json=data))
        self.assert403(self.open(url=url, method='PUT', json=data, auth=self.userauth))
        response = self.open(url=url, method='PUT', json=data, auth=self.adminauth)
        self.assert200(response)  # only Admin has permission

        # add pod with kube type that exists in both packages (Standard kube)
        pod = Pod(id=str(uuid4()), name='test_change_package1',
                  owner_id=user.id, kube_id=0, config='')
        db.session.add(pod)
        db.session.commit()

        # change package: both packages have this kube_type
        data = {'package': package0.name}
        self.assert200(self.open(url=url, method='PUT', json=data,
                                 auth=self.adminauth))  # only Admin has permission

        # add pod with kube type that exists only in current package
        pod = Pod(id=str(uuid4()), name='test_change_package2',
                  owner_id=user.id, kube_id=1, config='')
        db.session.add(pod)
        db.session.commit()

        # change package: new package doesn't have kube_type of some of user's pods
        data = {'package': package1.name}
        self.assert400(self.open(url=url, method='PUT', json=data,
                                 auth=self.adminauth))  # only Admin has permission

    @attr('k8s')
    def test_suspend(self):
        """AC-1608 In case of unsuspend, return all public IPs"""
        from kubedock.kapi.podcollection import PodCollection
        from kubedock.pods.models import PodIP, IPPool

        user = self.user
        url = '{0}/{1}'.format(self.url, user.id)

        ippool = IPPool(network='192.168.1.252/30').save()
        min_pod = {'restartPolicy': 'Always', 'kube_type': 0, 'containers': [{
            'image': 'nginx', 'name': 'fk8i0gai',
            'args': ['nginx', '-g', 'daemon off;'],
            'ports': [{'protocol': 'tcp', 'isPublic': True, 'containerPort': 80}],
        }]}

        # pod-1
        res = PodCollection(user).add(dict(min_pod, name='pod-1'), skip_check=False)
        pod_1 = Pod.query.get(res['id'])
        pod_1.with_ip_conf = {
            'public_ip': res['public_ip'],
            'containers': [{'ports': [{'isPublic': True}]}],
        }
        pod_1.without_ip_conf = {
            'public_ip_before_freed': res['public_ip'],
            'containers': [{'ports': [{'isPublic_before_freed': True}]}],
        }

        # pod-2
        res = PodCollection(user).add(dict(min_pod, name='pod-2'), skip_check=False)
        pod_2 = Pod.query.get(res['id'])
        pod_2.with_ip_conf = {
            'public_ip': res['public_ip'],
            'containers': [{'ports': [{'isPublic': True}]}],
        }
        pod_2.without_ip_conf = {
            'public_ip_before_freed': res['public_ip'],
            'containers': [{'ports': [{'isPublic_before_freed': True}]}],
        }

        # helpers
        def _has_public_ip(pod):
            podip = PodIP.query.filter_by(pod_id=pod.id).first()
            conf = pod.get_dbconfig()
            port = conf['containers'][0]['ports'][0]
            if podip is None:
                self.assertFalse(port.get('isPublic'))
                self.assertFalse(conf.get('public_ip'))
                self.assertTrue(port.get('isPublic_before_freed'))
                self.assertTrue(conf.get('public_ip_before_freed'))
                return False
            self.assertFalse(port.get('isPublic_before_freed'))
            self.assertFalse(conf.get('public_ip_before_freed'))
            self.assertTrue(port.get('isPublic'))
            self.assertEqual(conf.get('public_ip'), unicode(ip_address(podip.ip_address)))
            return True

        def _count_pods_with_public_ip():
            return _has_public_ip(pod_1) + _has_public_ip(pod_2)

        # suspend user. Both ip must be freed
        self.assertEqual(_count_pods_with_public_ip(), 2,
                         'all pods must have public ip in the beginning')
        data = {'suspended': True}
        response = self.open(url=url, method='PUT', json=data, auth=self.adminauth)
        self.assert200(response)

        self.assertEqual(_count_pods_with_public_ip(), 0,
                         'all pods must lose public ip')

        # unsuspend must be atomic, so if one pod cannot get public ip, all won't
        ippool.block_ip(ippool.free_hosts(as_int=True)[0])
        db.session.commit()

        data = {'suspended': False}
        response = self.open(url=url, method='PUT', json=data, auth=self.adminauth)
        self.assert500(response)
        self.assertDictContainsSubset({'type': 'UserUpdateError'}, response.json)
        self.assertEqual(_count_pods_with_public_ip(), 0, "operation must be "
                         "atomic, so if one pod can't get public ip, all won't")

        # unblock ip in ippool to be able to unsuspend user
        ippool.unblock_ip(ippool.get_blocked_set(as_int=True).pop())
        db.session.commit()

        data = {'suspended': False}
        response = self.open(url=url, method='PUT', json=data, auth=self.adminauth)
        self.assert200(response)
        self.assertEqual(_count_pods_with_public_ip(), 2,
                         'all pods must get their ip back')


if __name__ == '__main__':
    unittest.main()
