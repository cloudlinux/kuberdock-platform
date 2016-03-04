import requests

from sqlalchemy.exc import IntegrityError, InvalidRequestError

from hashlib import md5
from copy import deepcopy

from ..core import db
from ..utils import APIError, atomic
from ..validation import UserValidator
from ..billing.models import Package
from ..pods.models import Pod, PersistentDisk
from ..rbac.models import Role
from ..users.models import User, UserActivity
from ..system_settings.models import SystemSettings
from ..users.utils import enrich_tz_with_offset
from .podcollection import PodCollection, POD_STATUSES
from .pstorage import get_storage_class, delete_persistent_drives_task
from .licensing import is_valid as license_valid


class ResourceReleaseError(APIError):
    """Occurs when some of user's resources couldn't be released."""
    type = 'ResourceReleaseError'


class UserNotFound(APIError):
    message = 'User not found'
    status_code = 404


class UserCollection(object):
    def get(self, user=None, with_deleted=False, full=False):
        """Get user or list of users

        :param user: user id, username or kuberdock.users.models.User object
        :param with_deleted: do not ignore deleted users
        :param full: if True, return full user data (with pods, package, etc.)
        :raises APIError: if user was not found
        """
        users = User.query if with_deleted else User.not_deleted
        if user is None:
            return [user.to_dict(full=full) for user in users.all()]

        user = self._convert_user(user)
        return user.to_dict(full=full)

    @atomic(APIError("Couldn't create user.", 500, 'UserCreateError'), nested=False)
    @enrich_tz_with_offset(['timezone'])
    def create(self, data):
        """Create user"""
        if not license_valid():
            raise APIError("Action forbidden. Please check your license")
        data = UserValidator().validate_user_create(data)
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
        return user.to_dict()

    @atomic(APIError("Couldn't update user.", 500, 'UserUpdateError'), nested=False)
    @enrich_tz_with_offset(['timezone'])
    def update(self, user, data):
        """Update user

        :param user: user id, username or kuberdock.users.models.User object
        :param data: fields to update
        :raises APIError:
        """
        user = self._convert_user(user)

        data = UserValidator(id=user.id, allow_unknown=True).validate_user_update(data)
        if 'rolename' in data:
            rolename = data.pop('rolename', 'User')
            r = Role.by_rolename(rolename)
            if r is not None:
                if r.rolename == 'Admin':
                    pods = [p for p in user.pods if not p.is_deleted]
                    if pods:
                        raise APIError('User with the "{0}" role '
                                       'cannot have any pods'.format(r.rolename))
                data['role'] = r
            else:
                data['role'] = Role.by_rolename('User')
        if 'package' in data:
            package = data['package']
            p = Package.by_name(package)
            old_package, new_package = user.package, p
            kubes_in_old_only = (set(kube.kube_id for kube in old_package.kubes) -
                                 set(kube.kube_id for kube in new_package.kubes))
            if kubes_in_old_only:
                if user.pods.filter(Pod.kube_id.in_(kubes_in_old_only)).first() is not None:
                    raise APIError("New package doesn't have kube_types of some "
                                   "of user's pods")
            data['package'] = p

        if 'suspended' in data and data['suspended'] != user.suspended and user.active:
            if data['suspended']:
                self._suspend_user(user)
            else:
                self._unsuspend_user(user)
            user.suspended = data.pop('suspended')

        if 'active' in data and data['active'] != user.active:
            if data['active']:
                if not user.suspended:
                    self._unsuspend_user(user)
            else:
                user.logout(commit=False)
                if not user.suspended:
                    self._suspend_user(user)

        user.update(data)
        db.session.flush()
        return user.to_dict()

    @atomic(APIError("Couldn't update user.", 500, 'UserUpdateError'), nested=False)
    @enrich_tz_with_offset(['timezone'])
    def update_profile(self, user, data):
        """Update user's profile

        :param user: user id, username or kuberdock.users.models.User object
        :param data: fields to update
        :raises APIError:
        """
        user = self._convert_user(user)
        data = UserValidator(id=user.id, allow_unknown=True).validate_user_update(data)
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
        delete_persistent_drives_task.apply_async(
            ([pd.id for pd in user.persistent_disks],),
            countdown=10
        )

        user.deleted = True
        try:
            db.session.commit()
        except (IntegrityError, InvalidRequestError), e:
            db.session.rollback()
            raise APIError('Cannot delete a user: {0}'.format(str(e)), 500)

    @atomic(APIError("Couldn't undelete user.", 500, 'UserUndeleteError'), nested=False)
    def undelete(self, user):
        """Undelete user.

        :param user: user id, username or kuberdock.users.models.User object
        :raises APIError: if user was not found
        """
        user = self._convert_user(user)
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
        """Transform id, username, or User to User."""
        result = User.get(user)
        if result is None:
            raise UserNotFound('User "{0}" does not exists'.format(user))
        return result

    @staticmethod
    @atomic()
    def _suspend_user(user):
        pod_collection = PodCollection(user)
        for pod in pod_collection.get(as_json=False):
            if pod.get('status') != POD_STATUSES.stopped:
                pod_collection.update(pod['id'], {'command': 'stop'})
            pod_collection._remove_public_ip(pod_id=pod['id'])

    @staticmethod
    @atomic()
    def _unsuspend_user(user):
        pod_collection = PodCollection(user)
        for pod in pod_collection.get(as_json=False):
            pod_collection._return_public_ip(pod['id'])

    @staticmethod
    def get_client_id(data, package):
        """Tries to create the user in billing"""
        # TODO: untie from WHMCS specifics, maybe as plugin

        if data.get('clientid'):
            return
        if SystemSettings.get_by_name('billing_type') == 'No billing':
            return
        url, username, password = map(SystemSettings.get_by_name,
                ('billing_url', 'billing_username', 'billing_password'))
        if not all((url, username, password)):
            raise APIError("Some billing parameters are missing or "
                           "not properly configured")
        billing_data = deepcopy(data)
        billing_data.update({
            'action'      : 'addclient',
            'username'    : username,
            'password'    : md5(password).hexdigest(),
            'firstname'   : data.pop('first_name', 'kduser'),
            'lastname'    : data.pop('last_name', 'kduser'),
            'kduser'      : data.get('username', 'kduser'),
            'address1'    : 'KuberDock',
            'city'        : 'KuberDock',
            'state'       : 'None',
            'postcode'    : '12345',
            'country'     : 'US',
            'phonenumber' : '0000000',
            'package_id'  : package.id,
            'responsetype': 'json'})
        r = requests.post(url.strip('/ ') + '/includes/api.php', data=billing_data)
        if r.status_code != 200:
            raise APIError(
                "Could not add user to billing. Make sure billing site "
                "is accessible and properly functioning")
        data['clientid'] = r.json().get('clientid')
