from flask import Blueprint
from flask.views import MethodView

from kubedock import tasks
from .utils import use_kwargs
from .. import dns_management, certificate_utils
from ..core import db
from ..decorators import maintenance_protected
from ..domains.models import BaseDomain
from ..exceptions import (AlreadyExistsError, CannotBeDeletedError,
                          InternalAPIError, DomainNotFound, DNSPluginError,
                          DomainZoneDoesNotExist, CertificatDoesNotMatchDomain)
from ..kapi import ingress
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
    def post(self, name, certificate=None, **kwargs):
        """Creates BaseDomain model in database.

        Request must contain parameter 'name' - name for domain.
        Raises AlreadyExistsError if domain with specified name already exists.
        :param name: domain name
        :param certificate: domain certificate
        :return: dict with created BaseDomain model fields.
        """
        # check preconditions
        subsystem_is_up = ingress.is_subsystem_up()
        if not subsystem_is_up:
            ingress.check_subsystem_up_preconditions()

        if BaseDomain.query.filter(BaseDomain.name == name).first():
            raise AlreadyExistsError()

        zone_exists, message = dns_management.check_if_zone_exists(name)
        if message:
            raise DNSPluginError(message)
        if not zone_exists:
            raise DomainZoneDoesNotExist(name)

        # add domain
        with atomic(CreateDomainInternalError.from_exc, nested=False):
            domain = BaseDomain.create(name=name)
            if certificate:
                certificate_utils.check_cert_is_valid_for_domain(
                    '*.' + name, certificate['cert'])
                domain.certificate = certificate

            db.session.add(domain)

        # up subsystem if needed and create wildcard dns record
        post_actions = tasks.create_wildcard_dns_record.si(name)
        if not subsystem_is_up:
            post_actions = ingress.prepare_ip_sharing_task.si() | post_actions
        post_actions.delay()

        return domain.to_dict()

    @maintenance_protected
    @check_permission('edit', 'domains')
    @atomic(EditDomainInternalError.from_exc, nested=False)
    @use_kwargs(base_domain_schema, allow_unknown=True)
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
            (tasks.delete_wildcard_dns_record.si(name)
             | tasks.create_wildcard_dns_record.si(name)).delay()
        domain.certificate = params.get('certificate')
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
        domain_name = domain.name
        db.session.delete(domain)
        tasks.delete_wildcard_dns_record.delay(domain_name)


register_api(domains, DomainsAPI, 'domains', '/', 'domain_id', 'int')
