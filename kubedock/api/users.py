from flask import Blueprint, request, current_app, jsonify
from . import route
from .. import tasks
from ..models import User, Role, Pod
from ..core import db, check_permission


bp = Blueprint('users', __name__, url_prefix='/users')


@check_permission('get', 'users')
def get_users_collection():
    users = []
    cur = db.session.query(User).all()
    for user in cur:
        users.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'active': user.active,
            'rolename': user.role.rolename,
            'description': user.description
        })
    return users


@route(bp, '/', methods=['GET'])
def get_list():
    return jsonify({'status': 'OK', 'data': get_users_collection()})


@route(bp, '/<user_id>/', methods=['GET'])
@check_permission('get', 'users')
def get_one_user(user_id):
    u = User.query.get(user_id)
    if u:
        return jsonify({'status': 'OK', 'data': u.to_dict()})
    else:
        return jsonify({'status': "User {0} doesn't exists".format(user_id)}), 404


@route(bp, '/a/<user_id>/', methods=['GET'])
@check_permission('get', 'users')
def get_user_activities(user_id):
    u = User.filter_by(id=user_id).first()
    if u:
        return jsonify({'status': 'OK', 'data': u.user_activity()})
    else:
        return jsonify({'status': "User %s doesn't exists" % user_id}), 404


@route(bp, '/online/', methods=['GET'])
@check_permission('get', 'users')
def get_online_users():
    objects_list = User.get_online_collection()
    return jsonify({'data': objects_list})


@route(bp, '/', methods=['POST'])
@check_permission('create', 'users')
def create_item():
    data = request.json
    u = db.session.query(User).filter_by(username=data['username']).first()
    if not u:
        rolename = data.pop('rolename', None)
        r = db.session.query(Role).filter_by(rolename=rolename).first()
        temp = dict(filter((lambda t: t[1] != ''), data.items()))
        u = User(**temp)
        u.role = r
        db.session.add(u)
        db.session.commit()
        data.update({'id': u.id, 'rolename': rolename})
        return jsonify({'status': 'OK', 'data': data})
    else:
        return jsonify({'status': 'Conflict: User "{0}" already exists'.format(u.username)}), 409


@route(bp, '/<user_id>/', methods=['PUT'])
@check_permission('edit', 'users')
def put_item(user_id):
    u = db.session.query(User).get(user_id)
    if u:
        data = request.json
        # after some validation, including username unique...
        r = db.session.query(Role).filter_by(rolename=data.pop('rolename', None)).first()
        data = dict(filter((lambda item: item[1] != ''), data.items()))
        u.username = data['username']
        u.email = data['email']
        u.active = data['active']
        u.description = data.get('description', '')
        u.role = r
        db.session.add(u)
        db.session.commit()
        return jsonify({'status': 'OK'})
    else:
        return jsonify({'status': "User " + user_id + " doesn't exists"}), 404


@route(bp, '/<user_id>/', methods=['DELETE'])
@check_permission('delete', 'users')
def delete_item(user_id):
    u = db.session.query(User).get(user_id)
    if u:
        db.session.delete(u)
        db.session.commit()
    return jsonify({'status': 'OK'})