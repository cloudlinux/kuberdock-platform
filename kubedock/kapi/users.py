
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

import sys
import re

from copy import deepcopy
from flask import current_app
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from .licensing import is_valid as license_valid
from .podcollection import PodCollection, POD_STATUSES
from .apps import generate
from .pstorage import delete_persistent_drives_task, PersistentStorage
from ..billing.models import Package
from ..core import db
from ..exceptions import APIError
from ..pods.models import Pod
from ..rbac.models import Role
from ..settings import KUBERDOCK_INTERNAL_USER
from ..system_settings.models import SystemSettings
from ..users.models import User, UserActivity
from ..users.utils import enrich_tz_with_offset
from ..utils import atomic
from ..validation import UserValidator
from ..billing import has_billing


class ResourceReleaseError(APIError):
    message = "Some of user's resources couldn't be released."


class UserNotFound(APIError):
    message = 'User not found'
    status_code = 404


class UserIsNotDeleteable(APIError):
    message_template = 'User {username} is undeletable'
    status_code = 403

    def __init__(self, username=None, **kwargs):
        super(UserIsNotDeleteable, self).__init__(
            details=dict(username=username, **kwargs))


class UserIsNotLockable(APIError):
    message_template = 'User {username} cannot be locked'
    status_code = 403

    def __init__(self, username=None, **kwargs):
        super(UserIsNotLockable, self).__init__(
            details=dict(username=username, **kwargs))


class UserIsNotSuspendable(APIError):
    message_template = 'User {username} cannot be suspended'
    status_code = 403

    def __init__(self, username=None, **kwargs):
        super(UserIsNotSuspendable, self).__init__(
            details=dict(username=username, **kwargs))


class UserCollection(object):
    def __init__(self, doer=None):
        self.doer = doer

    def get(self, user=None, with_deleted=False, full=False):
        """Get user or list of users

        :param user: user id, username or kuberdock.users.models.User object
        :param with_deleted: do not ignore deleted users
        :param full: if True, return full user data (with pods, package, etc.)
        :raises APIError: if user was not found
        """
        users = User.query if with_deleted else User.not_deleted
        if user is None:
            return [dict(u.to_dict(full=full),
                         actions=self._get_applicability(u))
                    for u in users.all()]

        user = self._convert_user(user)
        return dict(user.to_dict(full=full),
                    actions=self._get_applicability(user))

    @atomic(APIError("Couldn't create user.", 500, 'UserCreateError'),
            nested=False)
    @enrich_tz_with_offset(['timezone'])
    def create(self, data, return_object=False):
        """Create user"""
        if not license_valid():
            raise APIError("Action forbidden. Please check your license")
        data = UserValidator(allow_unknown=True).validate_user(data)
        role = Role.by_rolename(data['rolename'])
        package = Package.by_name(data['package'])
        self.get_client_id(data, package)
        temp = {key: value for key, value in data.iteritems()
                if value != '' and key not in ('package', 'rolename',)}
        user = User(**temp)
        user.role = role
        user.package = package
        db.session.add(user)
        db.session.flush()
        if return_object:
            return user
        return dict(user.to_dict(full=True),
                    actions=self._get_applicability(user))

    @atomic(APIError("Couldn't update user.", 500, 'UserUpdateError'),
           nested=False)
    @enrich_tz_with_offset(['timezone'])
    def update(self, user, data):
        """Update user

        :param user: user id, username or kuberdock.users.models.User object
        :param data: fields to update
        :raises APIError:
        """
        user = self._convert_user(user)

        validator = UserValidator(id=user.id, allow_unknown=True)
        data = validator.validate_user(data, update=True)

        try:
            if 'suspended' in data \
                    and data['suspended'] != user.suspended and user.active:
                if data['suspended']:
                    self._is_suspendable(user, raise_=True)
                    self._suspend_user(user)
                else:
                    self._unsuspend_user(user)
                user.suspended = data.pop('suspended')

            if 'active' in data and data['active'] != user.active:
                if data['active']:
                    if not user.suspended:
                        self._unsuspend_user(user)
                else:
                    self._is_lockable(user, raise_=True)
                    user.logout(commit=False)
                    if not user.suspended:
                        self._suspend_user(user)
        except APIError:
            current_app.logger.warn('Exception during user update',
                                    exc_info=sys.exc_info())
            raise
        except Exception:
            current_app.logger.warn('Exception during user update',
                                    exc_info=sys.exc_info())
            raise APIError("Couldn't update user.", 500, 'UserUpdateError')

        if 'rolename' in data:
            rolename = data.pop('rolename', 'User')
            r = Role.by_rolename(rolename)
            if r is not None:
                if r.rolename == 'Admin':
                    pods = [p for p in user.pods if not p.is_deleted]
                    if pods:
                        raise APIError('User with the "{0}" role '
                                        'cannot have any pods'
                                        .format(r.rolename))
                data['role'] = r
            else:
                data['role'] = Role.by_rolename('User')
        if 'package' in data:
            package = data['package']
            p = Package.by_name(package)
            old_package, new_package = user.package, p
            kubes_in_old_only = (
                set(kube.kube_id for kube in old_package.kubes) -
                set(kube.kube_id for kube in new_package.kubes)
            )
            if kubes_in_old_only:
                if user.pods.filter(Pod.kube_id.in_(
                        kubes_in_old_only)).first() is not None:
                    raise APIError(
                        "New package doesn't have kube_types of some "
                        "of user's pods")
            data['package'] = p

        user.update(data)
        db.session.flush()
        return user.to_dict()

    @atomic(APIError("Couldn't update user.", 500, 'UserUpdateError'),
            nested=False)
    @enrich_tz_with_offset(['timezone'])
    def update_profile(self, user, data):
        """Update user's profile

        :param user: user id, username or kuberdock.users.models.User object
        :param data: fields to update
        :raises APIError:
        """
        user = self._convert_user(user)
        validator = UserValidator(id=user.id, allow_unknown=True)
        data = validator.validate_user(data, update=True)
        user.update(data, for_profile=True)
        db.session.flush()
        return user.to_dict()

    def delete(self, user, force=False):
        """Release all user's resources and mark user as deleted.

        :param user: user id, username or kuberdock.users.models.User object
        :param force: if True, will not raise ResourceReleaseError
        :raises ResourceReleaseError: if couldn't release some resources
        :raises APIError: if user was not found
        """
        user = self._convert_user(user)
        self._is_deletable(user, raise_=True)
        uid = user.id
        user.logout(commit=False)

        pod_collection = PodCollection(user)
        for pod in pod_collection.get(as_json=False):
            pod_collection.delete(pod['id'])
        # Now, when we have deleted all pods, events will rape db session a
        # little bit.
        # Get new, clean user instance to prevent a lot of various SA errors
        user = User.get(uid)

        # Add some delay for deleting drives to allow kubernetes unmap drives
        # after a pod was deleted. Also in some cases this delay is not enough,
        # for example DBMS in container may save data to PD for a long time.
        # So there is a regular procedure to clean such undeleted drives
        # tasks.clean_drives_for_deleted_users.
        for pd in user.persistent_disks:
            PersistentStorage.end_stat(pd.name, user.id)
        delete_persistent_drives_task.apply_async(
            ([pd.id for pd in user.persistent_disks],),
            countdown=10
        )
        prefix = '__' + generate()
        user.username += prefix
        user.email += prefix
        user.deleted = True
        try:
            db.session.commit()
        except (IntegrityError, InvalidRequestError), e:
            db.session.rollback()
            raise APIError('Cannot delete a user: {0}'.format(str(e)), 500)

    @atomic(APIError("Couldn't undelete user.", 500, 'UserUndeleteError'),
            nested=False)
    def undelete(self, user):
        """Undelete user.

        :param user: user id, username or kuberdock.users.models.User object
        :raises APIError: if user was not found
        """
        user = self._convert_user(user)
        user.deleted = False

    @atomic(APIError("Couldn't undelete user.", 500, 'UserUndeleteError'),
            nested=False)
    def undelete_by_email(self, user_email):
        """Undelete user by email.

        :param user_email: user email -> str
        :raises APIError: if user was not found
        """
        user = User.query.filter(User.email.like(user_email + '%')).first()
        if user is None:
            raise UserNotFound('User email "{0}" does not exists'.format(
                user_email))
        user.email = re.sub(r'^([^@]+@[\w\.\-]+?)(?:__[A-Za-z0-9]{8})?$',
                            r'\1', user.email)
        user.username = re.sub(r'^(.+?)(?:__[A-Za-z0-9]{8})?$', r'\1',
                               user.username)
        user.deleted = False

    def get_activities(self, user, date_from=None, date_to=None, to_dict=None):
        """
        Requests the activities list of the user
        :param user: username, user Id, user object
        :param date_from: activities from
        :param date_to: activities to
        :param to_dict: returns list of dicts
        :returns: queryset or list or JSON string
        """
        user = UserCollection._convert_user(user)
        activities = UserActivity.query.filter(UserActivity.user_id == user.id)
        if date_from:
            activities = activities.filter(
                UserActivity.ts >= '{0} 00:00:00'.format(date_from))
        if date_to:
            activities = activities.filter(
                UserActivity.ts <= '{0} 23:59:59'.format(date_to))

        if to_dict:
            return [a.to_dict() for a in activities]
        return activities

    @staticmethod
    def _convert_user(user):
        """Transform id, case-insensitive username, or User to User."""
        result = User.get(user)
        if result is None:
            raise UserNotFound('User "{0}" does not exists'.format(user))
        return result

    def _get_applicability(self, user):
        """Mark applicable actions for user."""
        return {
            'lock': self._is_lockable(user),
            'delete': self._is_deletable(user),
            'suspend': self._is_suspendable(user),
        }

    def _is_deletable(self, user, raise_=False):
        able = (self.doer != user and user.username != KUBERDOCK_INTERNAL_USER)
        if raise_ and not able:
            raise UserIsNotDeleteable(user.username)
        return able

    def _is_lockable(self, user, raise_=False):
        able = (self.doer != user and user.username != KUBERDOCK_INTERNAL_USER)
        if raise_ and not able:
            raise UserIsNotLockable(user.username)
        return able

    def _is_suspendable(self, user, raise_=False):
        able = (not user.is_administrator() and
                user.username != KUBERDOCK_INTERNAL_USER)
        if raise_ and not able:
            raise UserIsNotSuspendable(user.username)
        return able

    @staticmethod
    @atomic()
    def _suspend_user(user):
        pod_collection = PodCollection(user)
        for pod in pod_collection.get(as_json=False):
            if pod.get('status') != POD_STATUSES.stopped:
                pod_collection.update(pod['id'], {'command': 'stop'})

    @staticmethod
    @atomic()
    def _unsuspend_user(user):
        pod_collection = PodCollection(user)
        for pod in pod_collection.get(as_json=False):
            pod_collection._return_public_ip(pod['id'])

    @staticmethod
    def get_client_id(data, package):
        """Tries to create the user in billing"""
        if data.get('clientid'):
            return
        if not has_billing():
            return
        billing_data = deepcopy(data)
        billing_data.update({
            'password': generate(8),  # password for a new user
            'firstname': billing_data.pop('first_name', 'kduser'),
            'lastname': billing_data.pop('last_name', 'kduser'),
            'username': billing_data.get('username', 'kduser'),
            'package_id': package.id})
        current_billing = SystemSettings.get_by_name('billing_type')
        billing = current_app.billing_factory.get_billing(current_billing)
        data['clientid'] = billing.getclientid(**billing_data)
