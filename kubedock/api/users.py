from flask import Blueprint, request, jsonify, current_app, session
from flask.ext.login import login_user, logout_user, current_user
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from . import APIError
from ..billing import Package
from ..core import db
from ..rbac import check_permission
from ..rbac.models import Role
from ..utils import login_required_or_basic
from ..users.models import User, UserActivity
from ..users.signals import (
    user_logged_in_by_another, user_logged_out_by_another)



users = Blueprint('users', __name__, url_prefix='/users')


@users.route('/loginA', methods=['POST'])
@login_required_or_basic
@check_permission('auth_by_another', 'users')
def auth_another():
    data = request.form
    user_id = data['user_id']
    current_app.logger.debug('auth_another({0})'.format(user_id))
    user = User.query.get(user_id)
    if user is None:
        raise APIError('User with Id {0} does not exist'.format(user_id))
    session['auth_by_another'] = session.get('auth_by_another', current_user.id)
    user_logged_in_by_another.send((current_user.id, user_id))
    login_user(user)
    current_app.logger.debug('auth_another({0}) after'.format(current_user.id))
    return jsonify({'status': 'OK'})


@check_permission('get', 'users')
def get_users_collection():
    return [u.to_dict() for u in User.all()]


@users.route('/', methods=['GET'])
@login_required_or_basic
def get_list():
    return jsonify({'status': 'OK', 'data': get_users_collection()})


@users.route('/roles', methods=['GET'])
@login_required_or_basic
@check_permission('get', 'users')
def get_roles():
    return jsonify({
        'status': 'OK',
        'data': [x.rolename for x in db.session.query(Role).all()]
    })


@users.route('/<user_id>', methods=['GET'])
@login_required_or_basic
@check_permission('get', 'users')
def get_one_user(user_id):
    if user_id == 'all':
        return jsonify({'status': 'OK', 'data': get_users_collection()})
    # Suppose our IDs are integers only
    if user_id.isdigit():
        u = User.query.get(user_id)
    else:
        u = User.filter_by(username=user_id).first()
    if u is None:
        raise APIError("User {0} doesn't exists".format(user_id))
    return jsonify({'status': 'OK', 'data': u.to_dict()})


@users.route('/a/<user_id>', methods=['GET'])
@login_required_or_basic
@check_permission('get', 'users')
def get_user_activities(user_id):
    u = User.filter_by(id=user_id).first()
    if u:
        return jsonify({'status': 'OK', 'data': u.user_activity()})
    raise APIError("User {0} doesn't exists".format(user_id))


@users.route('/activities', methods=['POST'])
@login_required_or_basic
@check_permission('get', 'users')
def get_users_activities():
    data = request.form
    user_ids = data.get('users_ids', '').split(',')
    data_from = data.get('date_from')
    date_to = data.get('date_to')
    if not user_ids:
        raise APIError("Select at least one user")
    objects_list = UserActivity.get_users_activities(
        user_ids, data_from, date_to, to_dict=True)
    return jsonify({'data': objects_list})


@users.route('/logHistory', methods=['GET'])
@login_required_or_basic
@check_permission('get', 'users')
def get_user_log_history():
    data = request.args
    uid = data.get('uid')
    data_from = data.get('date_from')
    date_to = data.get('date_to')
    if not uid:
        raise APIError("Undefined user")
    objects_list = UserActivity.get_sessions(uid, data_from, date_to)
    return jsonify({'data': objects_list})


@users.route('/online/', methods=['GET'])
@login_required_or_basic
@check_permission('get', 'users')
def get_online_users():
    return jsonify({'data': User.get_online_collection()})


@users.route('/', methods=['POST'])
@login_required_or_basic
@check_permission('create', 'users')
def create_item():
    data = request.json
    if data is None:
        data = dict(request.form)
    for key in data.keys():
        if type(data[key]) is list and len(data[key]) == 1:
            data[key] = data[key][0]
    try:
        rolename = data.pop('rolename', 'User')
        package = data.pop('package', 'basic')
        r = Role.filter_by(rolename=rolename).first()
        p = get_pricing(package)
        temp = dict(filter((lambda t: t[1] != ''), data.items()))
        u = User(**temp)
        u.role = r
        u.package = p
        u.save()
        data.update({'id': u.id, 'rolename': rolename, 'package': package})
        return jsonify({'status': 'OK', 'data': data})
    except (IntegrityError, InvalidRequestError):
        db.session.rollback()
        raise APIError('Conflict: User "{0}" already '
                       'exists'.format(data['username']))


@users.route('/<user_id>', methods=['PUT'])
@login_required_or_basic
@check_permission('edit', 'users')
def put_item(user_id):
    if user_id.isdigit():
        u = db.session.query(User).get(user_id)
    else:
        u = db.session.query(User).filter_by(username=user_id).first()
    if u is not None:
        data = request.json
        if data is None:
            data = request.form.to_dict()
        for key in data.keys():
            if isinstance(data[key], list) and len(data[key]) == 1:
                data[key] = data[key][0]
        
        # after some validation, including username unique...
        if 'role' in data:
            rolename = rolename=data.pop('role', 'User')
            r = db.session.query(Role).filter_by(rolename=rolename).first()
            if r is not None:
                data['role'] = r
            else:
                data['role'] = db.session.query(Role).filter_by(rolename='User').first()
        data = dict(filter((lambda item: item[1] != ''), data.items()))
        for attr in data.keys():
            setattr(u, attr, data[attr])
        u.save()
        return jsonify({'status': 'OK'})
    raise APIError("User {0} doesn't exists".format(user_id))


@users.route('/<user_id>', methods=['DELETE'])
@login_required_or_basic
@check_permission('delete', 'users')
def delete_item(user_id):
    if user_id.isdigit():
        u = User.query.get(user_id)
    else:
        u = User.filter_by(username=user_id).first()
    if u is not None:
        u.delete()
    return jsonify({'status': 'OK'})


def get_pricing(package_name):
    try:
        return filter((lambda x: x.name == package_name),
            db.session.query(Package).all())[0]
    except IndexError:
        return None