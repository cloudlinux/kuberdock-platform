from flask import Blueprint, request, current_app, session
from flask.ext.login import login_user, current_user

from . import APIError
from ..rbac import check_permission
from ..rbac.models import Role
from ..decorators import login_required_or_basic_or_token
from ..utils import KubeUtils
from ..users.models import User, UserActivity
from ..users.signals import user_logged_in_by_another
from ..kapi.users import UserCollection, UserNotFound


users = Blueprint('users', __name__, url_prefix='/users')


@users.route('/loginA', methods=['POST'])
@login_required_or_basic_or_token
@check_permission('auth_by_another', 'users')
@KubeUtils.jsonwrap
def auth_another():
    data = KubeUtils._get_params()
    uid = data['user_id']
    user = User.query.get(uid)
    if user is None or user.deleted:
        raise UserNotFound('User "{0}" does not exists'.format(uid))
    session['auth_by_another'] = session.get('auth_by_another', current_user.id)
    user_logged_in_by_another.send((current_user.id, user.id))
    login_user(user)


@users.route('/q', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_usernames():
    with_deleted = request.args.get('with-deleted', False)
    return User.search_usernames(request.args.get('s'), with_deleted)


@users.route('/roles', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_roles():
    return zip(*Role.query.filter(~Role.internal).values(Role.rolename))[0]


@users.route('/a/<user>', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_user_activities(user):
    data = request.args
    data_from = data.get('date_from')
    date_to = data.get('date_to')
    return UserCollection().get_activities(user, data_from, date_to, to_dict=True)


@users.route('/logHistory', methods=['GET'])
@login_required_or_basic_or_token
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


@users.route('/online/', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_online_users():
    return User.get_online_collection()


# Users CRUD views
# TODO: put in MethodView


@users.route('/', methods=['GET'], strict_slashes=False)
@users.route('/all', methods=['GET'])
# TODO: remove endpoint /<uid>. Conflicts with a lot of other endpoints.
@users.route('/<uid>', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_list(uid=None):
    with_deleted = request.args.get('with-deleted', False)
    return UserCollection().get(uid, with_deleted=with_deleted)


@users.route('/full', methods=['GET'])
@users.route('/full/<user>', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_full_list(user=None):
    with_deleted = request.args.get('with-deleted', False)
    return UserCollection().get(user=user, with_deleted=with_deleted, full=True)


@users.route('/', methods=['POST'], strict_slashes=False)
@users.route('/full', methods=['POST'], strict_slashes=False)
@login_required_or_basic_or_token
@check_permission('create', 'users')
@KubeUtils.jsonwrap
def create_item():
    data = KubeUtils._get_params()
    return UserCollection().create(data)


# TODO: remove endpoint /<uid>. Conflicts with a lot of other endpoints.
@users.route('/<uid>', methods=['PUT', 'PATCH'])
@users.route('/full/<uid>', methods=['PUT', 'PATCH'])
@login_required_or_basic_or_token
@check_permission('edit', 'users')
@KubeUtils.jsonwrap
def put_item(uid):
    data = KubeUtils._get_params()
    return UserCollection().update(uid, data)


@users.route('/editself', methods=['GET'])
@login_required_or_basic_or_token
@KubeUtils.jsonwrap
def get_self():
    return current_user.to_dict(for_profile=True)


@users.route('/editself', methods=['PUT', 'PATCH'])
@login_required_or_basic_or_token
@KubeUtils.jsonwrap
def edit_self():
    uid = KubeUtils._get_current_user().id
    data = KubeUtils._get_params()
    return UserCollection().update_profile(uid, data)


# TODO: remove endpoint /<uid>. Conflicts with a lot of other endpoints.
@users.route('/<uid>', methods=['DELETE'])
@users.route('/full/<uid>', methods=['DELETE'])
@login_required_or_basic_or_token
@check_permission('delete', 'users')
@KubeUtils.jsonwrap
def delete_item(uid):
    force = KubeUtils._get_params().get('force', False)
    return UserCollection().delete(uid, force)


@users.route('/undelete/<uid>', methods=['POST'])
@login_required_or_basic_or_token
@check_permission('create', 'users')
@KubeUtils.jsonwrap
def undelete_item(uid):
    return UserCollection().undelete(uid)
