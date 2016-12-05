from flask import Blueprint
from flask.views import MethodView

from .utils import use_kwargs
from .. import dns_management
from ..core import db
from ..decorators import maintenance_protected
from ..domains.models import BaseDomain
from ..exceptions import (AlreadyExistsError, CannotBeDeletedError,
                          InternalAPIError, DomainNotFound, DNSPluginError,
                          DomainZoneDoesNotExist)
from ..kapi.ingress import prepare_ip_sharing
from ..login import auth_required
from ..rbac import check_permission
from ..utils import atomic, KubeUtils, register_api
from ..validation.schemas import domain_schema, certificate_schema

domains = Blueprint('domains', __name__, url_prefix='/domains')


class CreateDomainInternalError(InternalAPIError):
    message_template = 'Failed to add domain ({excType}: {excValue})'


class EditDomainInternalError(InternalAPIError):
    message_template = (
        'Failed to change domain name ({excType}: {excValue})')


class DeleteDomainInternalError(InternalAPIError):
    message_template = 'Failed to delete domain ({excType}: {excValue})'

# TODO: Validate that common name in certificate is wildcard cert of the given
# domain
base_domain_schema = {
    'name': dict(domain_schema, required=True),
    'certificate': certificate_schema,
}


class DomainsAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, auth_required]

    @check_permission('get', 'domains')
    def get(self, domain_id=None):
        """Creates BaseDomain model in database.

        Request must contain parameter 'name' - name for domain.
        Raises AlreadyExistsError if domain with specified name already exists.
        :return: dict with created BaseDomain model fields.
        """
        if domain_id is not None:
            domain = BaseDomain.query.get(domain_id)
            if domain is None:
                raise DomainNotFound()
            return domain.to_dict()
        return BaseDomain.get_objects_collection()

    @maintenance_protected
    @check_permission('create', 'domains')
    @use_kwargs(base_domain_schema, allow_unknown=True)
    def post(self, **params):
        """Creates BaseDomain model in database.

        Request must contain parameter 'name' - name for domain.
        Raises AlreadyExistsError if domain with specified name already exists.
        :param name: domain name
        :return: dict with created BaseDomain model fields.
        """
        prepare_ip_sharing()
        with atomic(CreateDomainInternalError.from_exc, nested=False):
            name = params['name']
            if BaseDomain.query.filter(BaseDomain.name == name).first():
                raise AlreadyExistsError()
            zone_exists, message = dns_management.check_if_zone_exists(name)
            if message:
                raise DNSPluginError(message)
            if not zone_exists:
                raise DomainZoneDoesNotExist(name)

            domain = BaseDomain(name=name)

            if 'certificate' in params:
                domain.certificate = params['certificate']

            db.session.add(domain)
        return domain.to_dict()

    @maintenance_protected
    @check_permission('edit', 'domains')
    @atomic(EditDomainInternalError.from_exc, nested=False)
    @use_kwargs({'name': domain_schema}, allow_unknown=True)
    def put(self, domain_id, **params):
        """Updates BaseDomain model in database.

        Now it is only possible to change domain name. If the request
        does not contain 'name' field, then the method does nothing.
        Raises AlreadyExistsError if new name conflicts with some another
        existing domain.
        :param domain_id: id of BaseDomain model
        :param name: domain name
        :return: dict with created BaseDomain model fields.
        """
        name = params.get('name')
        domain = BaseDomain.query.get(domain_id)
        if domain is None:
            raise DomainNotFound()
        if name and name != domain.name:
            if BaseDomain.query.filter(BaseDomain.name == name).first():
                raise AlreadyExistsError()
            domain.name = name
        return domain.to_dict()

    patch = put

    @maintenance_protected
    @check_permission('delete', 'domains')
    @atomic(DeleteDomainInternalError.from_exc, nested=False)
    def delete(self, domain_id):
        domain = BaseDomain.query.get(domain_id)
        if domain is None:
            raise DomainNotFound()
        if domain.pod_domains:
            raise CannotBeDeletedError(
                'Domain cannot be deleted: there are some pods that use it')
        db.session.delete(domain)


register_api(domains, DomainsAPI, 'domains', '/', 'domain_id', 'int')
