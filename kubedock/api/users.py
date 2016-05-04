from flask import Blueprint, request, current_app, session
from flask.ext.login import login_user
from flask.views import MethodView

from . import APIError
from ..rbac import check_permission
from ..rbac.models import Role
from ..login import auth_required
from ..utils import KubeUtils, register_api
from ..validation import extbool
from ..users.models import User, UserActivity
from ..users.signals import user_logged_in_by_another
from ..kapi.users import UserCollection, UserNotFound


users = Blueprint('users', __name__, url_prefix='/users')


@users.route('/loginA', methods=['POST'])
@auth_required
@check_permission('auth_by_another', 'users')
@KubeUtils.jsonwrap
def auth_another(uid=None):
    data = KubeUtils._get_params()
    original_user = KubeUtils._get_current_user()
    uid = uid if uid else data['user_id']
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        raise APIError("User UID is expected")
    if original_user.id == uid:
        raise APIError("Logging in as admin is pointless")
    user = User.query.get(uid)
    if user is None or user.deleted:
        raise UserNotFound('User "{0}" does not exists'.format(uid))
    session['auth_by_another'] = session.get('auth_by_another',
                                             original_user.id)
    user_logged_in_by_another.send((original_user.id, user.id))
    login_user(user)


@users.route('/q', methods=['GET'])
@auth_required
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_usernames():
    with_deleted = request.args.get('with-deleted', False)
    return User.search_usernames(request.args.get('s'), with_deleted)


@users.route('/roles', methods=['GET'])
@auth_required
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_roles():
    return zip(*Role.query.filter(~Role.internal).values(Role.rolename))[0]


@users.route('/a/<user>', methods=['GET'])
@auth_required
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_user_activities(user):
    data = request.args
    data_from = data.get('date_from')
    date_to = data.get('date_to')
    return UserCollection(KubeUtils._get_current_user()).get_activities(
        user, data_from, date_to, to_dict=True)


@users.route('/logHistory', methods=['GET'], strict_slashes=False)
@auth_required
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_user_log_history():
    data = request.args
    uid = data.get('uid')
    data_from = data.get('date_from')
    date_to = data.get('date_to')
    if not uid:
        raise APIError("Undefined user")
    return UserActivity.get_sessions(uid, data_from, date_to)


@users.route('/online', methods=['GET'], strict_slashes=False)
@auth_required
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_online_users():
    return User.get_online_collection()


class UsersAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, auth_required]

    @check_permission('get', 'users')
    def get(self, uid=None):
        full = not extbool(KubeUtils._get_params().get('short', False))
        with_deleted = request.args.get('with-deleted')
        return UserCollection(KubeUtils._get_current_user()).get(
            user=uid, with_deleted=with_deleted, full=full)

    @check_permission('create', 'users')
    def post(self):
        data = KubeUtils._get_params()
        return UserCollection(KubeUtils._get_current_user()).create(data)

    @check_permission('edit', 'users')
    def put(self, uid):
        data = KubeUtils._get_params()
        return UserCollection(KubeUtils._get_current_user()).update(uid, data)
    patch = put

    @check_permission('delete', 'users')
    def delete(self, uid):
        force = KubeUtils._get_params().get('force', False)
        return UserCollection(KubeUtils._get_current_user()).delete(uid, force)
register_api(users, UsersAPI, 'podapi', '/all/', 'uid', strict_slashes=False)


@users.route('/editself', methods=['GET'])
@auth_required
@KubeUtils.jsonwrap
def get_self():
    return KubeUtils._get_current_user().to_dict(for_profile=True)


@users.route('/editself', methods=['PUT', 'PATCH'])
@auth_required
@KubeUtils.jsonwrap
def edit_self():
    uid = KubeUtils._get_current_user().id
    data = KubeUtils._get_params()
    doer = KubeUtils._get_current_user()
    return UserCollection(doer).update_profile(uid, data)


@users.route('/undelete/<uid>', methods=['POST'])
@auth_required
@check_permission('create', 'users')
@KubeUtils.jsonwrap
def undelete_item(uid):
    return UserCollection(KubeUtils._get_current_user()).undelete(uid)
