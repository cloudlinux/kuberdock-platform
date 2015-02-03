from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from ..billing import Pricing
from ..core import db, check_permission
from ..utils import login_required_or_basic
from ..users import User, Role


users = Blueprint('users', __name__, url_prefix='/users')


@check_permission('get', 'users')
def get_users_collection():
    return [u.to_dict() for u in User.all()]


@users.route('/', methods=['GET'])
@login_required_or_basic
def get_list():
    return jsonify({'status': 'OK', 'data': get_users_collection()})


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
        u = db.session.query(User).filter_by(username=user_id).first()
    if u is None:
        return jsonify({'status': "User {0} doesn't exists".format(user_id)}), 404
    return jsonify({'status': 'OK', 'data': u.to_dict()})


@users.route('/a/<user_id>', methods=['GET'])
@login_required_or_basic
@check_permission('get', 'users')
def get_user_activities(user_id):
    u = User.filter_by(id=user_id).first()
    if u:
        return jsonify({'status': 'OK', 'data': u.user_activity()})
    else:
        return jsonify({'status': "User %s doesn't exists" % user_id}), 404


@users.route('/online/', methods=['GET'])
@login_required_or_basic
@check_permission('get', 'users')
def get_online_users():
    objects_list = User.get_online_collection()
    return jsonify({'data': objects_list})


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
        rolename = data.pop('rolename', 'user')
        package = data.pop('package', 'basic')
        r = db.session.query(Role).filter_by(rolename=rolename).first()
        p = get_pricing(package)
        temp = dict(filter((lambda t: t[1] != ''), data.items()))
        u = User(**temp)
        u.role = r
        u.pricing = p
        db.session.add(u)
        db.session.commit()
        data.update({'id': u.id, 'rolename': rolename, 'package': package})
        return jsonify({'status': 'OK', 'data': data})
    except (IntegrityError, InvalidRequestError):
        db.session.rollback()
        return jsonify({'status': 'Conflict: User "{0}" already exists'.format(data['username'])}), 409


@users.route('/<user_id>', methods=['PUT'])
@login_required_or_basic
@check_permission('edit', 'users')
def put_item(user_id):
    if user_id.isdigit():
        u = User.query.get(user_id)
    else:
        u = db.session.query(User).filter_by(username=user_id).first()
    if u is not None:
        data = request.json
        if data is None:
            data = dict(request.form)
        for key in data.keys():
            if type(data[key]) is list and len(data[key]) == 1:
                data[key] = data[key][0]
        # after some validation, including username unique...
        r = db.session.query(Role).filter_by(rolename=data.pop('rolename', 'User')).first()
        #p = db.session.query(Pricing).get(u.pricing_id)
        data = dict(filter((lambda item: item[1] != ''), data.items()))
        for key in data.keys():
            setattr(u, key, data[key])
        u.role = r
        #u.pricing = p
        db.session.add(u)
        db.session.commit()
        return jsonify({'status': 'OK'})
    else:
        return jsonify({'status': "User " + user_id + " doesn't exists"}), 404


@users.route('/<user_id>', methods=['DELETE'])
@login_required_or_basic
@check_permission('delete', 'users')
def delete_item(user_id):
    if user_id.isdigit():
        u = User.query.get(user_id)
    else:
        u = db.session.query(User).filter_by(username=user_id).first()
    if u is not None:
        db.session.delete(u)
        db.session.commit()
    return jsonify({'status': 'OK'})


def get_pricing(package_name):
    try:
        return filter((lambda x: x.package.package_name == package_name),
            db.session.query(Pricing).all())[0]
    except IndexError:
        return None