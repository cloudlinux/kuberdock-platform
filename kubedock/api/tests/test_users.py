import unittest
import logging
import pytz
import mock
from ipaddress import ip_address
from kubedock.testutils.testcases import APITestCase, attr
from flask import current_app

from uuid import uuid4
from kubedock.core import db
from kubedock.users.models import User, UserActivity
from kubedock.pods.models import Pod
from kubedock.billing.models import Package, PackageKube, Kube
from kubedock.kapi import podcollection as kapi_podcollection

class UserCRUDTestCase(APITestCase):
    """Tests for /api/users/all endpoint"""
    url = '/users/all'

    # @unittest.skip('')
    def test_get(self):
        # get list
        response = self.admin_open()
        self.assert200(response)
        user, admin = self.user.to_dict(full=True), self.admin.to_dict(
            full=True)
        user['join_date'] = user['join_date'].replace(
            tzinfo=pytz.utc).isoformat()
        admin['join_date'] = admin['join_date'].replace(
            tzinfo=pytz.utc).isoformat()
        user_short, admin_short = self.user.to_dict(), self.admin.to_dict()
        self_actions = {'lock': False, 'suspend': False, 'delete': False}
        actions = {'lock': True, 'suspend': True, 'delete': True}
        user_short['actions'] = user['actions'] = actions
        admin_short['actions'] = admin['actions'] = self_actions

        from pprint import pprint
        pprint(user)
        pprint(response.json['data'])

        self.assertIn(user, response.json['data'])
        self.assertIn(admin, response.json['data'])
        # short
        response = self.admin_open(self.url + '?short=true')
        self.assert200(response)
        self.assertIn(user_short, response.json['data'])
        self.assertIn(admin_short, response.json['data'])

        # get one
        response = self.admin_open(self.item_url(12345))
        self.assertAPIError(response, 404, 'UserNotFound')
        response = self.admin_open(self.item_url(self.user.id))
        self.assert200(response)
        self.assertEqual(user, response.json['data'])
        # short
        response = self.admin_open(self.item_url(12345) + '?short=true')
        self.assertAPIError(response, 404, 'UserNotFound')
        response = self.admin_open(self.item_url(self.user.id) + '?short=true')
        self.assert200(response)
        self.assertEqual(user_short, response.json['data'])

    # @unittest.skip('')
    @mock.patch('kubedock.kapi.users.license_valid', lambda *a, **kw: True)
    @mock.patch('kubedock.kapi.users.UserCollection.get_client_id')
    def test_post(self, uc):
        data = dict(username='test_post_users',
                    first_name='', last_name='', middle_initials='',
                    password='p-0', email='test_user@test.test',
                    active=True, rolename='User', package='Standard package')

        # add
        response = self.admin_open(method='POST', json=data)
        self.assert200(response)
        self.assertEqual(User.get(data['username']).to_dict(),
                         response.json['data'])

        # check conversion of extended boolean fields
        data['username'] += '1'
        data['email'] = '1' + data['email']
        data['active'] = 'TrUe'
        response = self.admin_open(method='POST', json=data)
        self.assert200(response)  # active is valid
        self.assertEqual(response.json['data']['active'], True)

        data['username'] += '1'
        data['email'] = '1' + data['email']
        data['suspended'] = '1'
        response = self.admin_open(method='POST', json=data)
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
        response = self.admin_open(self.item_url(self.user.id), 'PUT', data)
        self.assert200(response)

        user = User.query.get(self.user.id)
        self.assertTrue(user.verify_password(data.pop('password')))
        self.assertEqual(data.pop('package'), user.package.name)
        self.assertEqual(data.pop('rolename'), user.role.rolename)
        for field, value in data.iteritems():
            self.assertEqual(value, getattr(user, field))

    @mock.patch.object(kapi_podcollection.KubeQuery, '_run')
    def test_delete(self, PodCollection):
        user, _ = self.fixtures.user_fixtures()
        # delete
        self.assert200(self.admin_open(self.item_url(user.id), 'DELETE'))
        self.db.session.expire_all()
        self.assertTrue(user.deleted)
        # undelete
        url = '/users/undelete/{0}'.format(user.id)
        self.assert200(self.admin_open(url, 'POST'))
        self.db.session.expire_all()
        self.assertFalse(user.deleted)

    def test_change_package(self, *args):
        """
        AC-1003
        If new package lacks kube_types, that used in user's pods,
        then forbid this change.
        """
        user = self.user
        url = self.item_url(self.user.id)
        package0 = user.package
        package1 = Package(id=1, name='New package', first_deposit=0,
                           currency='USD', period='hour', prefix='$',
                           suffix=' USD')
        kube0, kube1, kube2 = Kube.public_kubes().all()
        # new package allows only standard kube
        PackageKube(package=package1, kube=kube0, kube_price=0)
        db.session.commit()

        # change package: user still doesn't have pods
        data = {'package': package1.name}
        response = self.admin_open(url=url, method='PUT', json=data)
        self.assert200(response)

        # add pod with kube type that exists in both packages (Standard kube)
        pod = Pod(id=str(uuid4()), name='test_change_package1',
                  owner_id=user.id, kube_id=0, config='')
        db.session.add(pod)
        db.session.commit()

        # change package: both packages have this kube_type
        data = {'package': package0.name}
        self.assert200(self.admin_open(url=url, method='PUT', json=data))

        # add pod with kube type that exists only in current package
        pod = Pod(id=str(uuid4()), name='test_change_package2',
                  owner_id=user.id, kube_id=1, config='')
        db.session.add(pod)
        db.session.commit()

        # change package: new package doesn't have kube_type of some of user's
        # pods
        data = {'package': package1.name}
        self.assert400(self.admin_open(url=url, method='PUT', json=data))

    @mock.patch.object(kapi_podcollection, 'license_valid', lambda: True)
    @mock.patch.object(kapi_podcollection.KubeQuery, '_run')
    def test_suspend(self, _run):
        """AC-1608 In case of unsuspend, return all public IPs"""
        from kubedock.kapi.podcollection import PodCollection
        from kubedock.pods.models import PodIP, IPPool

        # Disable as otherwise test breaks. Was created before introducing
        # this feature
        current_app.config['NONFLOATING_PUBLIC_IPS'] = False

        user = self.user
        url = self.item_url(self.user.id)

        ippool = IPPool(network='192.168.1.252/30').save()
        min_pod = {'restartPolicy': 'Always', 'kube_type': 0, 'containers': [{
            'image': 'nginx', 'name': 'fk8i0gai',
            'args': ['nginx', '-g', 'daemon off;'],
            'ports': [{'protocol': 'tcp', 'isPublic': True,
                       'containerPort': 80}],
        }]}

        # pod-1
        res = PodCollection(user).add(dict(min_pod, name='pod-1'),
                                      skip_check=False)
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
        res = PodCollection(user).add(dict(min_pod, name='pod-2'),
                                      skip_check=False)
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
            self.assertEqual(conf.get('public_ip'),
                             unicode(ip_address(podip.ip_address)))
            return True

        def _count_pods_with_public_ip():
            return _has_public_ip(pod_1) + _has_public_ip(pod_2)

        # suspend user. Both ip must be freed
        self.assertEqual(_count_pods_with_public_ip(), 2,
                         'all pods must have public ip in the beginning')
        data = {'suspended': True}
        response = self.admin_open(url=url, method='PUT', json=data)
        self.assert200(response)

        self.assertEqual(_count_pods_with_public_ip(), 0,
                         'all pods must lose public ip')

        # unsuspend must be atomic, so if one pod cannot get public ip,
        # all won't
        ippool.block_ip(ippool.free_hosts(as_int=True)[0])
        db.session.commit()

        data = {'suspended': False}
        response = self.admin_open(url=url, method='PUT', json=data)
        self.assertAPIError(response, 400, 'NoFreeIPs')
        self.assertEqual(_count_pods_with_public_ip(), 0,
                         "operation must be  atomic, so if one pod can't get "
                         "public ip, all won't")

        # unblock ip in ippool to be able to unsuspend user
        ippool.unblock_ip(ippool.get_blocked_set(as_int=True).pop())
        db.session.commit()

        data = {'suspended': False}
        response = self.admin_open(url=url, method='PUT', json=data)
        self.assert200(response)
        self.assertEqual(_count_pods_with_public_ip(), 2,
                         'all pods must get their ip back')


class TestUsers(APITestCase):
    """Tests for /api/users/* endpoints"""
    url = '/users'

    def test_get_usernames(self):
        response = self.admin_open(self.item_url('q') + '?s=mi')
        self.assert200(response)
        self.assertIn('admin', response.json['data'])
        self.assertNotIn('kuberdock-internal', response.json['data'])

    def test_get_roles(self):
        response = self.admin_open(self.item_url('roles'))
        self.assert200(response)
        self.assertItemsEqual(['Admin', 'User', 'TrialUser', 'LimitedUser'],
                              response.json['data'])

    def test_get_log_history(self):
        response = self.admin_open(self.item_url('logHistory'),
                                   query_string={'uid': self.user.id})
        self.assert200(response)  # only admin has permission
        # TODO: check response; 404 case; check date_from, date_to params

    def test_get_online(self):
        response = self.admin_open(self.item_url('online'))
        self.assert200(response)  # only admin has permission
        # TODO: check response; 404 case

    def test_login_as(self):
        response = self.admin_open(self.item_url('loginA'), method='POST',
                                   query_string={'user_id': self.user.id})
        self.assert200(response)  # only admin has permission
        # TODO: check response; 404 case; login as self;

    def test_get_user_activities(self):
        response = self.admin_open(self.item_url('a', 12345))
        self.assertAPIError(response, 404, 'UserNotFound')

        login = UserActivity(action=UserActivity.LOGIN_A,
                             user_id=self.admin.id)
        logout = UserActivity(action=UserActivity.LOGOUT_A,
                              user_id=self.admin.id)
        db.session.add_all([login, logout])
        db.session.commit()

        response = self.admin_open(self.item_url('a', self.admin.id))
        self.assert200(response)
        login_ts = {'ts': login.ts.replace(tzinfo=pytz.UTC).isoformat()}
        logout_ts = {'ts': logout.ts.replace(tzinfo=pytz.UTC).isoformat()}
        self.assertEqual(login.to_dict(include=login_ts),
                         response.json['data'][-2])
        self.assertEqual(logout.to_dict(include=logout_ts),
                         response.json['data'][-1])


class TestSelf(APITestCase):
    url = '/users/editself'

    def test_editself(self):
        data = {'password': str(uuid4())[:25]}

        response = self.user_open(method='PATCH', json=data)
        self.assert200(response)
        response = self.user_open(method='PATCH', json=data)
        # password has changed
        self.assertAPIError(response, 401, 'NotAuthorized')

    def test_get_self(self):
        response = self.user_open()
        self.assert200(response)
        self.assertEqual(response.json['data'],
                         self.user.to_dict(for_profile=True))


if __name__ == '__main__':
    unittest.main()
