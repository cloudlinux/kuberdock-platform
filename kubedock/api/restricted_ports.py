from flask import Blueprint

from .utils import use_kwargs
from ..kapi import restricted_ports as kapi_restricted_ports
from ..login import auth_required
from ..rbac import check_permission
from ..utils import KubeUtils
from ..validation import V, ValidationError, port_schema, protocol_schema


restricted_ports = Blueprint('restricted-ports', __name__,
                             url_prefix='/restricted-ports')


@restricted_ports.route('/', methods=['GET'])
@auth_required
@check_permission('get', 'restricted-ports')
@KubeUtils.jsonwrap
def get_ports():
    return kapi_restricted_ports.get_ports()


@restricted_ports.route('/', methods=['POST'])
@auth_required
@check_permission('create', 'restricted-ports')
@KubeUtils.jsonwrap
@use_kwargs({'port': dict(port_schema, required=True),
             'protocol': dict(protocol_schema, required=True)})
def set_port(port, protocol):
    kapi_restricted_ports.set_port(port, protocol)


@restricted_ports.route('/<int:port>/<protocol>', methods=['DELETE'])
@auth_required
@check_permission('delete', 'restricted-ports')
@KubeUtils.jsonwrap
def del_port(port, protocol):
    v = V()
    if not v.validate({'port': port, 'protocol': protocol},
                      {'port': port_schema, 'protocol': protocol_schema}):
        raise ValidationError(v.errors)
    kapi_restricted_ports.del_port(port, protocol)
