import json
from flask import Blueprint, request, jsonify

from . import APIError
from ..core import db
from ..rbac import check_permission, init_permissions
from ..rbac.models import Role, Resource, Permission
from ..utils import login_required_or_basic, APIError


settings = Blueprint('settings', __name__, url_prefix='/settings')


def get_permissions():
    data = []
    roles = {r.id: r.to_dict() for r in Role.all()}
    resources = {r.id: r.to_dict() for r in Resource.all()}
    for res in Resource.all():
        perms = set()
        _roles = {}
        for p in res.permissions:
            perms.add(p.name)
            role = roles[p.role_id]
            rolename = role['rolename']
            if rolename in _roles:
                _roles[rolename].append(p.to_dict())
            else:
                _roles[rolename] = [p.to_dict()]
        # role = roles[res.role_id]
        data.append({'id': res.id, 'name': res.name, 'permissions': list(perms),
                     'roles': _roles, 'all_roles': roles})
    return roles, data


@settings.route('/permissions/<pid>', methods=['PUT'])
@login_required_or_basic
def permissions(pid):
    data = request.json or request.form.to_dict()
    allow = data.get('allow')
    if allow not in ('true', 'false', True, False):
        raise APIError("Value error: {0}".format(allow))
    perm = Permission.query.get(int(pid))
    if allow in ('true', True):
        perm.set_allow()
    else:
        perm.set_deny()
    init_permissions()
    return jsonify({'status': 'OK'})