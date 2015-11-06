from sqlalchemy.exc import IntegrityError, InvalidRequestError

from ..core import db
from ..settings import CEPH, AWS
from ..utils import APIError
from ..validation import UserValidator
from ..billing.models import Package
from ..pods.models import Pod
from ..rbac.models import Role
from ..users.models import User
from ..users.utils import enrich_tz_with_offset
from .podcollection import PodCollection
from .pstorage import CephStorage, AmazonStorage


class ResourceReleaseError(APIError):
    """Occurs when some of user's resources couldn't be released."""
    type = 'ResourceReleaseError'


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

    @enrich_tz_with_offset(['timezone'])
    def create(self, data):
        """Create user"""
        data = UserValidator().validate_user_create(data)
        temp = {key: value for key, value in data.iteritems()
                if value != '' and key not in ('package', 'rolename',)}
        try:
            user = User(**temp)
            user.role = Role.by_rolename(data['rolename'])
            user.package = Package.by_name(data['package'])
            user.save()
        except (IntegrityError, InvalidRequestError), e:
            raise APIError('Cannot create a user: {0}'.format(str(e)))

        data.update({'id': user.id})
        return data

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
            if p is None:
                p = Package.by_name('Standard package')

            old_package, new_package = user.package, p
            kubes_in_old_only = (set(kube.kube_id for kube in old_package.kubes) -
                                 set(kube.kube_id for kube in new_package.kubes))
            if kubes_in_old_only:
                if user.pods.filter(Pod.kube_id.in_(kubes_in_old_only)).first() is not None:
                    raise APIError("New package doesn't have kube_types of some "
                                   "of user's pods")

            data['package'] = p
        user.update(data)
        try:
            user.save()
        except (IntegrityError, InvalidRequestError), e:
            db.session.rollback()
            raise APIError('Cannot update a user: {0}'.format(str(e)))

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
        try:
            user.save()
        except (IntegrityError, InvalidRequestError), e:
            db.session.rollback()
            raise APIError('Cannot update a user: {0}'.format(str(e)))

    def delete(self, user, force=False):
        """Release all user's resources and mark user as deleted.

        :param user: user id, username or kuberdock.users.models.User object
        :param force: if True, will not raise ResourceReleaseError
        :raises ResourceReleaseError: if couldn't release some resources
        :raises APIError: if user was not found
        """
        user = self._convert_user(user)
        uid = user.id
        user.logout()

        pod_collection = PodCollection(user)
        for pod in pod_collection.get(as_json=False):
            pod_collection.delete(pod['id'])
        # now, when we deleted all pods, events will rape db session a little bit
        # get new, clean user instance to prevent a lot of various SA errors
        user = User.get(uid)

        for pd in user.persistent_disks:
            rv_ceph = CephStorage().delete_by_id(pd.id) if CEPH else 1
            rv_aws = AmazonStorage().delete_by_id(pd.id) if AWS else 1
            if not force and (CEPH or AWS) and (rv_ceph != 0 and rv_aws != 0):
                raise ResourceReleaseError(u'Persistent Disk "{0}" is busy or does '
                                           u'not exist.'.format(pd.name))
            try:
                pd.delete()
            except Exception:
                if not force:
                    raise ResourceReleaseError(u'Couldn\'t delete Persistent Disk '
                                               u'"{1}" from db'.format(pd.name))

        user.deleted = True
        try:
            db.session.commit()
        except (IntegrityError, InvalidRequestError), e:
            db.session.rollback()
            raise APIError('Cannot delete a user: {0}'.format(str(e)))

    @staticmethod
    def _convert_user(user):
        """Transform id, username, or User to User."""
        result = User.get(user)
        if result is None:
            raise APIError('User "{0}" doesn\'t exist'.format(user), 404)
        return result
