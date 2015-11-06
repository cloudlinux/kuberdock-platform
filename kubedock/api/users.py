import json
from flask import Blueprint, request, current_app, session
from flask.ext.login import login_user, current_user

from . import APIError
from ..rbac import check_permission
from ..rbac.models import Role
from ..utils import login_required_or_basic_or_token, KubeUtils
from ..users.models import User, UserActivity
from ..users.signals import user_logged_in_by_another
from ..kapi.users import UserCollection


users = Blueprint('users', __name__, url_prefix='/users')


@users.route('/loginA', methods=['POST'])
@login_required_or_basic_or_token
@check_permission('auth_by_another', 'users')
@KubeUtils.jsonwrap
def auth_another():
    data = request.form
    user_id = data['user_id']
    # current_app.logger.debug('auth_another({0})'.format(user_id))
    user = User.query.get(user_id)
    if user is None or user.deleted:
        raise APIError('User with Id {0} does not exist'.format(user_id))
    session['auth_by_another'] = session.get('auth_by_another', current_user.id)
    user_logged_in_by_another.send((current_user.id, user_id))
    login_user(user)
    # current_app.logger.debug('auth_another({0}) after'.format(current_user.id))


@check_permission('get', 'users')
def get_users_usernames(s, with_deleted=False):
    users = User.query if with_deleted else User.not_deleted
    return zip(*users.filter(User.username.contains(s)).values(User.username))[0]


@users.route('/q', methods=['GET'])
@login_required_or_basic_or_token
@KubeUtils.jsonwrap
def get_usernames():
    with_deleted = request.args.get('with-deleted', False)
    return get_users_usernames(request.args.get('s'), with_deleted)


@users.route('/roles', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_roles():
    return zip(*Role.query.values(Role.rolename))[0]


def user_activities(user, date_from=None, date_to=None, to_dict=None,
                    to_json=None):
    """
    Requests the activities list of the user
    :param user: username, user Id, user object
    :param date_from: activities from
    :param date_to: activities to
    :param to_dict: returns [obj.to_dict(), ...]
    :param to_json: returns in JSON format
    :return: queryset or list or JSON string
    """
    if isinstance(user, basestring):
        user = User.get(user)
    elif isinstance(user, int):
        user = UserActivity.query.get(user)
    if user is None:
        raise APIError("User not found", 404)
    try:
        activities = UserActivity.query.filter(UserActivity.user_id == user.id)
    except AttributeError:
        current_app.logger.warning('UserActivity.get_user_activities '
                                   'failed: {0}'.format(user))
        raise APIError("User not found", 404)
    if date_from:
        activities = activities.filter(
            UserActivity.ts >= '{0} 00:00:00'.format(date_from))
    if date_to:
        activities = activities.filter(
            UserActivity.ts <= '{0} 23:59:59'.format(date_to))
    if to_dict or to_json:
        data = [a.to_dict() for a in activities]
        if to_json:
            data = json.dumps(data)
        return data
    return activities


@users.route('/a/<user>', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_user_activities(user):
    data = request.args
    data_from = data.get('date_from')
    date_to = data.get('date_to')
    return user_activities(user, data_from, date_to, to_dict=True)


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


@users.route('/', methods=['GET'])
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
@login_required_or_basic_or_token
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_full_list():
    with_deleted = request.args.get('with-deleted', False)
    return UserCollection().get(with_deleted=with_deleted, full=True)


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
