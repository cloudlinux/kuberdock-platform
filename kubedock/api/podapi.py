from flask import Blueprint, current_app, request
from flask.views import MethodView

from kubedock.billing import has_billing
from .utils import use_kwargs
from ..backups import pods as backup_pods
from ..decorators import maintenance_protected
from ..exceptions import PermissionDenied, NoFreeIPs, \
    NoFreeIPsAdminNotification
from ..kapi.apps import PredefinedApp
from ..kapi.podcollection import PodCollection, PodNotFound
from ..login import auth_required
from ..pods.models import Pod
from ..rbac import check_permission
from ..system_settings.models import SystemSettings
from ..tasks import make_backup
from ..utils import KubeUtils, register_api, catch_error
from ..validation import check_new_pod_data, check_change_pod_data, \
    owner_optional_schema, owner_mandatory_schema

podapi = Blueprint('podapi', __name__, url_prefix='/podapi')


schema = {'owner': owner_optional_schema}


def check_owner_permissions(owner=None, action='get'):
    current_user = KubeUtils.get_current_user()
    owner = owner or current_user

    check_permission('own', 'pods', user=owner).check()
    if owner == current_user:
        check_permission(action, 'pods').check()
    else:
        check_permission('{}_non_owned'.format(action), 'pods').check()
    return owner


class PodsAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, KubeUtils.pod_start_permissions,
                  auth_required]

    @use_kwargs(schema)
    def get(self, pod_id, owner=None):
        owner = check_owner_permissions(owner)
        return PodCollection(owner).get(pod_id, as_json=False)

    @maintenance_protected
    @catch_error(action='notify', trigger='resources')
    @use_kwargs(schema, allow_unknown=True)
    def post(self, owner=None, **params):
        owner = check_owner_permissions(owner, 'create')
        params = check_new_pod_data(params, owner)
        try:
            return PodCollection(owner).add(params)
        except NoFreeIPs:
            raise NoFreeIPsAdminNotification

    @maintenance_protected
    @use_kwargs({}, allow_unknown=True)
    def put(self, pod_id, **params):
        # it's left for backwards compatibility
        # that this method does not contain parameter "owner"
        # todo: In api/v2 add parameter "owner"
        current_user = self.get_current_user()
        db_pod = Pod.query.get(pod_id)
        if db_pod is None:
            raise PodNotFound()
        owner = db_pod.owner

        check_permission('own', 'pods', user=owner).check()
        if owner == current_user:
            check_permission('edit', 'pods').check()
        else:
            check_permission('edit_non_owned', 'pods').check()

        data = check_change_pod_data(params)

        privileged = False
        if current_user.is_administrator():
            privileged = True  # admin interacts with user's pod

        billing_type = SystemSettings.get_by_name('billing_type').lower()
        if billing_type != 'no billing' and current_user.fix_price \
                and not privileged:
            command = data.get('command')
            command_options = data.get('commandOptions')
            if command == 'set' and 'status' in command_options \
                    and command_options['status'] != db_pod.status:
                # fix-price user is not allowed to change paid/unpaid status
                # and start pod directly, only through billing system
                raise PermissionDenied(
                    'Direct requests are forbidden for fixed-price users.')

            kubes = db_pod.kubes_detailed
            for container in data.get('containers', []):
                if container.get('kubes') is not None:
                    kubes[container['name']] = container['kubes']
            if command == 'redeploy' and db_pod.kubes != sum(kubes.values()):
                # fix-price user is not allowed to upgrade pod
                # directly, only through billing system
                raise PermissionDenied(
                    'Direct requests are forbidden for fixed-price users.')

            edited = db_pod.get_dbconfig().get('edited_config') is not None
            apply_edit = data['commandOptions'].get('applyEdit')
            if command in ('start', 'redeploy') and edited and apply_edit:
                # fix-price user is not allowed to apply changes in pod
                # directly, only through billing system
                raise PermissionDenied(
                    'Direct requests are forbidden for fixed-price users.')

        pods = PodCollection(owner)
        return pods.update(pod_id, data)

    patch = put

    @maintenance_protected
    @use_kwargs(schema)
    def delete(self, pod_id, owner=None):
        owner = check_owner_permissions(owner, 'delete')
        pods = PodCollection(owner)
        result = pods.delete(pod_id)
        if has_billing():
            current_billing = SystemSettings.get_by_name('billing_type')
            billing = current_app.billing_factory.get_billing(current_billing)
            billing.deletepod(pod_id=pod_id)
        return result


register_api(podapi, PodsAPI, 'podapi', '/', 'pod_id')


@podapi.route('/<pod_id>/<container_name>/update', methods=['GET'])
@auth_required
@KubeUtils.jsonwrap
@use_kwargs(schema)
def check_updates(pod_id, container_name, owner=None):
    owner = check_owner_permissions(owner)
    return PodCollection(owner).check_updates(pod_id, container_name)


@podapi.route('/<pod_id>/<container_name>/update', methods=['POST'])
@auth_required
@KubeUtils.jsonwrap
@use_kwargs(schema)
def update_container(pod_id, container_name, owner=None):
    owner = check_owner_permissions(owner)
    return PodCollection(owner).update_container(pod_id, container_name)


@podapi.route('/<pod_id>/<container_name>/exec', methods=['POST'])
@auth_required
@KubeUtils.jsonwrap
@use_kwargs(dict(schema, command={
    'type': 'string', 'required': True, 'empty': False}))
def exec_in_container(pod_id, container_name, owner=None, command=''):
    owner = check_owner_permissions(owner)
    return PodCollection(owner).exec_in_container(
        pod_id, container_name, command)


@podapi.route('/<pod_id>/reset_direct_access_pass', methods=['GET'])
@auth_required
@KubeUtils.jsonwrap
@use_kwargs(schema)
def reset_access_container(pod_id, owner=None):
    current_user = KubeUtils.get_current_user()
    owner = owner or current_user

    check_permission('own', 'pods', user=owner).check()
    if owner == current_user:
        check_permission('get', 'pods').check()
    else:
        check_permission('get_non_owned', 'pods').check()
    return PodCollection(owner).reset_direct_access_pass(pod_id)


@podapi.route('/<pod_id>/dump', methods=['GET'])
@auth_required
@maintenance_protected
@check_permission('dump', 'pods')
@KubeUtils.jsonwrap
def dump(pod_id):
    return PodCollection().dump(pod_id)


@podapi.route('/dump', methods=['GET'])
@auth_required
@maintenance_protected
@check_permission('dump', 'pods')
@KubeUtils.jsonwrap
@use_kwargs({'owner': owner_optional_schema})
def batch_dump(owner=None):
    return PodCollection(owner).dump()


restore_args_schema = {
    'pod_dump': {
        'type': 'dict',
        'required': True
    },
    'owner': owner_mandatory_schema,
    'pv_backups_location': {
        'type': 'string',
        'required': False,
        'nullable': True
    },
    'pv_backups_path_template': {
        'type': 'string',
        'required': False,
        'nullable': True
    },
}


@podapi.route('/restore', methods=['POST'])
@auth_required
@maintenance_protected
@check_permission('create_non_owned', 'pods')
@KubeUtils.jsonwrap
@use_kwargs(restore_args_schema)
def restore(pod_dump, owner, **kwargs):
    with check_permission('own', 'pods', user=owner):
        return backup_pods.restore(pod_dump=pod_dump, owner=owner, **kwargs)


@podapi.route('/<pod_id>/plans-info', methods=['GET'])
@auth_required
@KubeUtils.jsonwrap
def get_plans_info_for_pod(pod_id):
    current_user = KubeUtils.get_current_user()
    return PredefinedApp.get_plans_info_for_pod(pod_id, user=current_user)


@podapi.route('/backup', methods=['GET', 'POST'])
@auth_required
@KubeUtils.jsonwrap
def backup_list():
    if request.method == 'GET':
        return [
            {'id': 1, 'timestamp': '2016-11-28 23:11:33', 'size': '1.3GB'},
            {'id': 2, 'timestamp': '2016-11-29 23:15:07', 'size': '1.1GB'}]
    make_backup.delay()
