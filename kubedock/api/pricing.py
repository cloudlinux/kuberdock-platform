from flask import Blueprint, current_app
from flask.views import MethodView
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from ..core import db
from ..rbac import check_permission
from ..utils import login_required_or_basic_or_token, KubeUtils, register_api
from ..users import User
from ..validation import check_pricing_api, package_schema, kube_schema, packagekube_schema
from ..billing.models import Package, Kube, PackageKube
from . import APIError


pricing = Blueprint('pricing', __name__, url_prefix='/pricing')

# === PACKAGE ROUTINES ===


@pricing.route('/userpackage', methods=['GET'], strict_slashes=False)
@KubeUtils.jsonwrap
@login_required_or_basic_or_token
@check_permission('get', 'pods')
def get_user_package():
    user = KubeUtils._get_current_user()
    user = User.query.filter_by(username=user.username).first()
    if user is None:
        raise APIError('No such user', 404)
    # current_app.logger.debug(user.package.kubes)
    return {k.kubes.name: k.kubes.id for k in user.package.kubes if k.kubes is not None}


class PackagesAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, login_required_or_basic_or_token]

    @check_permission('get', 'users')
    def get(self, package_id=None):
        if package_id is None:
            return [p.to_dict() for p in Package.query.all()]
        data = Package.query.get(package_id)
        if data is None:
            raise APIError('Package not found', 404)
        return data.to_dict()

    @check_permission('create', 'users')
    def post(self):
        params = check_pricing_api(self._get_params(), package_schema)
        if Package.query.filter_by(name=params['name']).first() is not None:
            raise APIError('Package with name \'{0}\' already exists'
                           .format(params['name']))
        package = Package(**params)
        db.session.add(package)
        try:
            db.session.commit()
        except (IntegrityError, InvalidRequestError):
            db.session.rollback()
            raise APIError('could not create package')
        return package.to_dict()

    @check_permission('edit', 'users')
    def put(self, package_id):
        package = Package.query.get(package_id)
        if package is None:
            raise APIError('Package not found', 404)
        params = check_pricing_api(self._get_params(), package_schema, update=True)

        if 'name' in params:
            duplicate = Package.query.filter(Package.name == params['name'],
                                             Package.id != package_id).first()
            if duplicate is not None:
                raise APIError('Package with name \'{0}\' already exists'
                               .format(params['name']))

        for key, value in params.iteritems():
            setattr(package, key, value)
        try:
            db.session.commit()
        except (IntegrityError, InvalidRequestError):
            db.session.rollback()
            raise APIError('could not update package')
        return package.to_dict()

    @check_permission('delete', 'users')
    def delete(self, package_id):
        package = Package.query.get(package_id)
        if package is None:
            raise APIError('Package not found', 404)
        if package.users:
            raise APIError('You have users with this package')
        try:
            PackageKube.query.filter_by(package_id=package_id).delete()
            db.session.delete(package)
            db.session.commit()
        except (IntegrityError, InvalidRequestError):
            raise APIError('could not delete package')

register_api(pricing, PackagesAPI, 'packages', '/packages/', 'package_id', strict_slashes=False)


# === KUBE ROUTINES ===


class KubesAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, login_required_or_basic_or_token]

    @check_permission('get', 'users')
    def get(self, kube_id=None):
        if kube_id is None:
            return [i.to_dict() for i in Kube.query.all()]
        item = Kube.query.get(kube_id)
        if item is None:
            raise APIError('Kube not found', 404)
        return item.to_dict()

    @check_permission('create', 'users')
    def post(self):
        params = self._get_params()
        return add_kube(params)

    @check_permission('edit', 'users')
    def put(self, kube_id):
        kube = Kube.query.get(kube_id)
        if kube is None:
            raise APIError('Kube not found', 404)
        data = check_pricing_api(self._get_params(), kube_schema, update=True)
        if 'name' in data:
            duplicate = Kube.query.filter(Kube.name == data['name'],
                                          Kube.id != kube_id).first() is not None
            if duplicate:
                raise APIError('Kube with name \'{0}\' already exists'
                               .format(data['name']))

        for key, value in data.items():
            setattr(kube, key, value)
        try:
            db.session.commit()
        except (IntegrityError, InvalidRequestError):
            db.session.rollback()
            raise APIError('could not update kube')
        return kube.to_dict()

    @check_permission('delete', 'users')
    def delete(self, kube_id):
        kube = Kube.query.get(kube_id)
        if kube is None:
            raise APIError('Kube not found', 404)
        if kube.nodes:
            raise APIError('Some nodes use this kube type')
        if kube.pods:
            raise APIError('Some pods use this kube type')
        try:
            PackageKube.query.filter_by(kube_id=kube_id).delete()
            db.session.delete(kube)
            db.session.commit()
        except (IntegrityError, InvalidRequestError):
            raise APIError('could not delete package')

register_api(pricing, KubesAPI, 'kubes', '/kubes/', 'kube_id', strict_slashes=False)


def add_kube(data):
    data = check_pricing_api(data, kube_schema)
    if Kube.query.filter_by(name=data['name']).first() is not None:
        raise APIError('Kube type with name \'{0}\' already exists'
                       .format(data['name']))

    kube = Kube(**data)
    db.session.add(kube)
    try:
        db.session.commit()
    except (IntegrityError, InvalidRequestError):
        db.session.rollback()
        raise APIError('could not create package')
    return kube.to_dict()


# === PACKAGE KUBE ROUTINES ===


@pricing.route('/packages/<int:package_id>/kubes-by-id', methods=['GET'],
               strict_slashes=False)
@KubeUtils.jsonwrap
@login_required_or_basic_or_token
@check_permission('get', 'users')
def get_package_kube_ids(package_id):
    package = Package.query.get(package_id)
    if package is None:
        raise APIError('Package not found', 404)
    return [kube.kube_id for kube in package.kubes if kube.kubes is not None]


@pricing.route('/packages/<int:package_id>/kubes-by-name', methods=['GET'],
               strict_slashes=False)
@KubeUtils.jsonwrap
@login_required_or_basic_or_token
@check_permission('get', 'users')
def get_package_kube_names(package_id):
    package = Package.query.get(package_id)
    if package is None:
        raise APIError('Package not found', 404)
    return [kube.kubes.name for kube in package.kubes if kube.kubes is not None]


class PackageKubesAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, login_required_or_basic_or_token]

    @check_permission('get', 'users')
    def get(self, package_id, kube_id=None):
        if kube_id is not None:
            raise APIError('Method not allowed', 405)
        package = Package.query.get(package_id)
        if package is None:
            raise APIError('Package not found', 404)
        return [dict(kube.kubes.to_dict(), kube_price=kube.kube_price)
                for kube in package.kubes if kube.kubes is not None]

    @check_permission('create', 'users')
    def post(self, package_id):
        if Package.query.get(package_id) is None:
            raise APIError('Package not found', 404)
        params = self._get_params()
        if 'id' in params:
            params = check_pricing_api(params, packagekube_schema)
            kube_id = params['id']
            if Kube.query.get(kube_id) is None:
                raise APIError('Kube not found', 404)
        else:
            params = check_pricing_api(params, dict(kube_schema, **packagekube_schema))
            kube_id = add_kube({key: value for key, value in params.iteritems()
                                if key in kube_schema})['id']

        return _add_kube_type_to_package(package_id, kube_id, params['kube_price'])

    @check_permission('edit', 'users')
    def put(self, package_id=None, kube_id=None):
        if Package.query.get(package_id) is None:
            raise APIError('Package not found', 404)
        if Kube.query.get(kube_id) is None:
            raise APIError('Kube not found', 404)
        params = check_pricing_api(self._get_params(), packagekube_schema)

        return _add_kube_type_to_package(package_id, kube_id, params['kube_price'])

    @check_permission('delete', 'users')
    def delete(self, package_id, kube_id):
        package_kube = PackageKube.query.filter_by(package_id=package_id,
                                                   kube_id=kube_id).first()
        if package_kube is None:
            raise APIError('Kube type is not in the package', 404)
        db.session.delete(package_kube)
        try:
            db.session.commit()
        except (IntegrityError, InvalidRequestError):
            db.session.rollback()
            raise APIError('could not remove kube type from package')

register_api(pricing, PackageKubesAPI, 'packagekubes',
             '/packages/<int:package_id>/kubes/', 'kube_id', strict_slashes=False)


def _add_kube_type_to_package(package_id, kube_id, kube_price):
    package_kube = PackageKube.query.filter_by(package_id=package_id, kube_id=kube_id).first()
    if package_kube is None:
        package_kube = PackageKube(package_id=package_id, kube_id=kube_id)
        db.session.add(package_kube)
    package_kube.kube_price = kube_price

    try:
        db.session.commit()
    except (IntegrityError, InvalidRequestError):
        db.session.rollback()
        raise APIError('could not add kube type to package')
    return package_kube.to_dict()
