from flask import Blueprint, request, current_app
from sqlalchemy.exc import IntegrityError

from ..core import db
from ..decorators import maintenance_protected
from ..domains.models import BaseDomain
from ..exceptions import (
    APIError, AlreadyExistsError, NotFound, InternalAPIError,
    CannotBeDeletedError)
from ..kapi.ingress import prepare_ip_sharing
from ..login import auth_required
from ..rbac import check_permission
from ..utils import KubeUtils


domains = Blueprint('domains', __name__, url_prefix='/domains')


@domains.route('/', methods=['GET'])
@auth_required
@check_permission('get', 'domains')
@KubeUtils.jsonwrap
def get_all():
    return BaseDomain.get_objects_collection()


@domains.route('/<int:domain_id>', methods=['GET'])
@auth_required
@check_permission('get', 'domains')
@KubeUtils.jsonwrap
def get_one(domain_id):
    domain = BaseDomain.query.get(domain_id)
    if domain is None:
        raise NotFound()
    return domain.to_dict()


def _commit_transaction(integrity_error, unknown_error_message):
    """Tries to commit transaction with BaseDomain model: create, update or
    delete.
    :param integrity_error: exception, which must be raise in case of
        database integrity error
    :param unknown_error_message: message that should be passed to
        InternalAPIError in case of unknown exception.
    """
    rollback = True
    try:
        db.session.commit()
        rollback = False
    except IntegrityError:
        raise integrity_error
    except Exception as err:
        current_app.logger.exception(unknown_error_message)
        raise InternalAPIError(
            unknown_error_message + '\nException: {}'.format(err))
    finally:
        if rollback:
            db.session.rollback()


@domains.route('/', methods=['POST'])
@auth_required
@check_permission('create', 'domains')
@maintenance_protected
@KubeUtils.jsonwrap
def create():
    """Creates BaseDomain model in database.
    Request must contain parameter 'name' - name for domain.
    Raises AlreadyExistsError if domain with specified name already exists.
    :return: dict with created BaseDomain model fields.
    """
    data = request.json
    try:
        name = data['name']
    except (KeyError, TypeError) as e:
        raise APIError(repr(e))
    prepare_ip_sharing()
    domain = BaseDomain(name=name)
    db.session.add(domain)
    _commit_transaction(AlreadyExistsError(),
                   u'Failed to add domain: {}'.format(name))
    return domain.to_dict()


@domains.route('/<int:domain_id>', methods=['PATCH', 'PUT'])
@auth_required
@check_permission('edit', 'domains')
@maintenance_protected
@KubeUtils.jsonwrap
def edit(domain_id):
    """Updates BaseDomain model in database.
    Now it is only possible to change domain name. If the does not contain
    'name' field, then the method does nothing.
    Raises AlreadyExistsError if new name conflicts with some another existing
    domain.
    :param domain_id: id of BaseDomain model
    :return: dict with created BaseDomain model fields.
    """
    data = request.json
    domain = BaseDomain.query.get(domain_id)
    if domain is None:
        raise NotFound()
    name = data.get('name', None)
    if name and name != domain.name:
        domain.name = data['name']
        _commit_transaction(AlreadyExistsError(),
                       u'Failed to change domain name: {}'.format(
                           data['name']))
    return domain.to_dict()


@domains.route('/<int:domain_id>', methods=['DELETE'])
@auth_required
@check_permission('delete', 'domains')
@maintenance_protected
@KubeUtils.jsonwrap
def delete(domain_id):
    domain = BaseDomain.query.get(domain_id)
    if domain is None:
        raise NotFound()
    db.session.delete(domain)
    _commit_transaction(CannotBeDeletedError(),
                   u'Failed to delete domain: {}'.format(domain.name))
