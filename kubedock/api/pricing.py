from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from ..billing import Package
from ..core import db
from ..rbac import check_permission
from ..utils import login_required_or_basic
from ..users import User
from ..pods import Pod
from ..billing.models import Package, Kube
from ..stats import StatWrap5Min
from collections import defaultdict
import time
import datetime
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from . import APIError


pricing = Blueprint('pricing', __name__, url_prefix='/pricing')

# === PACKAGE ROUTINES ===
@pricing.route('/packages', methods=['GET'], strict_slashes=False)
@pricing.route('/packages/<package_id>', methods=['GET'], strict_slashes=False)
@login_required_or_basic
@check_permission('get', 'users')
def get_package(package_id=None):
    if package_id is None:
        return jsonify({
            'status': 'OK',
             'data': [p.to_dict() for p in db.session.query(Package).all()]})
    data = db.session.query(Package).get(package_id)
    if data is None:
        raise APIError('Package not found', 404)
    return jsonify({'status': 'OK', 'data': data.to_dict()})


@pricing.route('/packages/<package_id>', methods=['PUT'])
@login_required_or_basic
@check_permission('edit', 'users')
def update_package(package_id):
    package = db.session.query(Package).get(package_id)
    if package is None:
        raise APIError('Package not found', 404)
    params = request.json
    if params is None:
        params = dict(request.form)
    for key in params.keys():
        if hasattr(package, key):
            setattr(package, key, params[key])
    db.session.commit()
    return jsonify({'status': 'OK'})


@pricing.route('/packages', methods=['POST'], strict_slashes=False)
@login_required_or_basic
@check_permission('create', 'users')
def create_package():
    data = {}
    params = request.json
    if params is None:
        params = dict(request.form)
    defaults = {'currency': 'USD', 'period': 'hour'}
    for attr in 'name', 'amount', 'currency', 'period':
        data[attr] = params.get(attr, defaults.get(attr))
        if data[attr] is None:
            return jsonify({
                'status': 'ERROR',
                'message': "attribute '{0}' is expected to be set".format(attr,)
            })
    try:
        package = Package(**data)
        db.session.add(package)
        db.session.commit()
        data['id'] = package.id
    except (IntegrityError, InvalidRequestError), e:
        db.session.rollback()
        return jsonify({
            'status': 'ERROR',
            'message': "could not add package {0}: {1}!".format(data['name'], str(e))
        })
    return jsonify({'status': 'OK', 'data': data})


@pricing.route('/packages/<package_id>', methods=['DELETE'])
@login_required_or_basic
@check_permission('delete', 'users')
def delete_package(package_id):
    package = db.session.query(Package).get(package_id)
    if package is None:
        raise APIError('Package not found', 404)
    db.session.delete(package)
    db.session.commit()
    return jsonify({'status': 'OK'})


# === KUBE ROUTINES ===
@pricing.route('/kubes', methods=['GET'], strict_slashes=False)
@pricing.route('/kubes/<int:kube_id>', methods=['GET'])
@login_required_or_basic
@check_permission('get', 'users')
def get_kube(kube_id=None):
    if kube_id is None:
        data = [i.to_dict() for i in db.session.query(Kube).all()]
    else:
        item = db.session.query(Kube).get(kube_id)
        if item is None:
            raise APIError('Kube not found', 404)
        data = item.to_dict()
    return jsonify({'status': 'OK', 'data': data})


@pricing.route('/kubes', methods=['POST'], strict_slashes=False)
@login_required_or_basic
@check_permission('create', 'users')
def create_kube():
    params = request.json
    if params is None:
        params = dict(request.form)
    return jsonify(add_kube(params))


def add_kube(data):
    attrs = {}
    defaults = {'cpu': 0, 'cpu_units': 'MHz', 'memory': 0, 'memory_units': 'MB',
                'disk_space': 0, 'total_traffic': 0, 'default': False}
    for attr in ('name',  'cpu', 'cpu_units', 'memory', 'memory_units',
                 'disk_space', 'total_traffic'):
        attrs[attr] = data.get(attr, defaults.get(attr))
        if attrs[attr] is None:
            return {
                'status': 'ERROR',
                'message': "attribute '{0}' is expected to be set".format(attr,)
            }
    try:
        kube = Kube(**attrs)
        db.session.add(kube)
        db.session.commit()
        attrs['id'] = kube.id
    except (IntegrityError, InvalidRequestError):
        db.session.rollback()
        return {
            'status': 'ERROR',
            'message': "Kube '{0}' already exists!".format(data['name'],)
        }
    return {'status': 'OK', 'data': attrs}


@pricing.route('/kubes/<int:kube_id>', methods=['PUT'])
@login_required_or_basic
@check_permission('edit', 'users')
def update_kube(kube_id):
    conv = {'cpu': float, 'memory': int}
    item = db.session.query(Kube).get(kube_id)
    if item is None:
        raise APIError('Kube not found', 404)
    if request.json is not None:
        data = request.json
    else:
        data = request.form
    for key, value in data.items():
        if hasattr(item, key):
            setattr(item, key, conv.get(key, str)(value))
    db.session.commit()
    return jsonify({'status': 'OK'});


@pricing.route('/kubes/<int:kube_id>', methods=['DELETE'])
@login_required_or_basic
@check_permission('delete', 'users')
def delete_kube(kube_id):
    item = db.session.query(Kube).get(kube_id)
    if item is None:
        raise APIError('Kube not found', 404)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'status': 'OK'});


# === PACKAGE KUBE ROUTINES ===
@pricing.route('/packages/<int:package_id>/kubes-by-id', methods=['GET'], strict_slashes=False)
@login_required_or_basic
@check_permission('get', 'users')
def get_package_kube_ids(package_id):
    package = db.session.query(Package).get(package_id)
    if package is None:
        raise APIError('Package not found', 404)
    kubes = []
    for kube in package.kubes:
        kubes.append(kube.id)
    return jsonify({'status': 'OK', 'data': kubes})


@pricing.route('/packages/<int:package_id>/kubes-by-name', methods=['GET'], strict_slashes=False)
@login_required_or_basic
@check_permission('get', 'users')
def get_package_kube_names(package_id):
    package = db.session.query(Package).get(package_id)
    if package is None:
        raise APIError('Package not found', 404)
    kubes = []
    for kube in package.kubes:
        kubes.append(kube.name)
    return jsonify({'status': 'OK', 'data': kubes})


@pricing.route('/packages/<int:package_id>/kubes', methods=['GET'], strict_slashes=False)
@login_required_or_basic
@check_permission('get', 'users')
def get_package_kubes(package_id):
    package = db.session.query(Package).get(package_id)
    if package is None:
        raise APIError('Package not found', 404)
    kubes = []
    for kube in package.kubes:
        kubes.append(kube.to_dict())
    return jsonify({'status': 'OK', 'data': kubes})


@pricing.route('/packages/<int:package_id>/kubes', methods=['POST'], strict_slashes=False)
@pricing.route('/packages/<int:package_id>/kubes/<int:kube_id>', methods=['PUT'])
@login_required_or_basic
@check_permission('edit', 'users')
def add_kube_to_package(package_id, kube_id=None):
    package = db.session.query(Package).get(package_id)
    if package is None:
        raise APIError('Package not found', 404)
    if kube_id is None:
        params = request.json
        if params is None:
            params = dict(request.form)
        if 'id' not in params:
            rv = add_kube(params)
            if 'data' not in rv:
                return jsonify(rv)
            kube_id = rv['data']['id']
        else:
            kube_id = params['id']
    kube = db.session.query(Kube).get(kube_id)
    if kube is None:
        raise APIError('Kube not found', 404)
    package.kubes.append(kube)
    db.session.commit()
    return jsonify({'status': 'OK'})


@pricing.route('/packages/<int:package_id>/kubes/<int:kube_id>', methods=['DELETE'])
@login_required_or_basic
@check_permission('edit', 'users')
def delete_kube_from_package(package_id, kube_id):
    package = db.session.query(Package).get(package_id)
    if package is None:
        raise APIError('Package not found', 404)
    kube = db.session.query(Kube).get(kube_id)
    if kube is None:
        raise APIError('Kube not found', 404)
    package.kubes.remove(kube)
    db.session.commit()
    return jsonify({'status': 'OK'})