
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import re
import socket
from urlparse import urlparse

import cerberus
from ipaddress import ip_network
from sqlalchemy import func

from kubedock.billing.models import Kube, Package
from kubedock.domains.models import BaseDomain
from kubedock.kapi.images import Image
from kubedock.predefined_apps.models import PredefinedApp
from kubedock.rbac.models import Role
from kubedock.settings import AWS, CEPH, KUBERDOCK_INTERNAL_USER
from kubedock.system_settings.models import SystemSettings
from kubedock.users.models import User
from kubedock.users.utils import strip_offset_from_timezone
from kubedock.utils import get_timezone
from .exceptions import APIError, ValidationError
from .schemas import (command_pod_schema, cpu_multiplier_schema,
                      email_domain_regex, email_literal_regex,
                      email_local_regex, hostname_schema, image_request_schema,
                      image_search_schema, memory_multiplier_schema,
                      new_pod_schema, node_schema, pod_dump_schema,
                      positive_non_zero_integer_schema, user_schema,
                      container_image_regex)


class V(cerberus.Validator):
    """
    This class is for all custom and our app-specific validators and types,
    implement any new here.
    """

    ERROR_SHOULD_NOT_USE_LATEST = "Tag \":latest\" should not be used "
    "otherwise,\n proper restore is not guaranteed."

    # TODO: add readable error messages for regexps in old schemas

    def __init__(self, *args, **kwargs):
        self.user = kwargs.get('user')
        super(V, self).__init__(*args, **kwargs)

    def _api_validation(self, data, schema, *args, **kwargs):
        validated = self.validated(data, schema, *args, **kwargs)
        if validated is None:
            raise ValidationError(self.errors)
        return validated

    def _validate_regex(self, re_obj, field, value):
        """
        The same as original Validator._validate_regex, but can accept
        pre-compiled regex as a parameter or a regex-object:
        {'regex': <pattern or compiled regex>,
        'message': <custom error message>}

        Examples:

        'regex': r'^[A-Za-z]*$'
        'regex': re.compile(r'^[A-Z]*$', re.IGNORECASE)
        'regex': {'regex': r'^[A-Za-z]*$',
                  'message': 'should contain letters of Latin alphabet only'}
        'regex': {'regex': re.compile(r'^[A-Z]*$', re.IGNORECASE),
                  'message': 'should contain letters of Latin alphabet only'}
        """
        if not isinstance(value, basestring):
            return

        message = u'value "{value}" does not match regex "{regex}"'
        if isinstance(re_obj, dict):
            message = re_obj['message'].decode('utf-8')
            re_obj = re_obj['regex']

        if isinstance(re_obj, basestring):
            re_obj = re.compile(re_obj)

        if not re_obj.match(value):
            self._error(field, message.format(value=value,
                                              regex=re_obj.pattern))

    def _validate_type_email(self, field, value):
        super(V, self)._validate_type_string(field, value)

        if not value or '@' not in value:
            self._error(field, 'invalid email address (there is no @ in it)')
            return

        user_part, domain_part = value.rsplit('@', 1)

        if not email_local_regex.match(user_part):
            self._error(field, 'invalid email address (local part)')

        try:
            domain_part = domain_part.encode('idna')
        except (TypeError, UnicodeError):
            self._error(field, 'invalid email address (domain part)')

        if domain_part.endswith('.web'):
            self._error(field, 'invalid email address (domain part)')

        if email_domain_regex.match(domain_part):
            return

        literal_match = email_literal_regex.match(domain_part)
        if literal_match:
            ip_address = literal_match.group(1)
            try:
                socket.inet_pton(socket.AF_INET, ip_address)
                return
            except socket.error:
                pass
        self._error(field, 'invalid email address (domain part)')

    def _validate_internal_only(self, internal_only, field, value):
        if internal_only and self.user != KUBERDOCK_INTERNAL_USER:
            self._error(field, 'not allowed')

    def _validate_template_exists(self, exists, field, value):
        if exists:
            if value is None:
                return
            templ = PredefinedApp.query.get(value)
            if not templ:
                self._error(field,
                            'There is no template with such template_id')

    def _validate_kube_type_exists(self, exists, field, value):
        if exists:
            kube = Kube.query.get(value)
            if kube is None:
                self._error(field, 'Pod can\'t be created, because cluster '
                                   'has no kube type with id "{0}", please '
                                   'contact administrator.'.format(value))
            elif not kube.available:
                self._error(field, 'Pod can\'t be created, because cluster '
                                   'has no nodes with "{0}" kube type, please '
                                   'contact administrator.'.format(kube.name))

    def _validate_kube_type_in_user_package(self, exists, field, value):
        if exists and self.user:
            if self.user == KUBERDOCK_INTERNAL_USER and \
                    value == Kube.get_internal_service_kube_type():
                return
            package = User.get(self.user).package
            if value not in [k.kube_id for k in package.kubes]:
                self._error(field,
                            "Pod can't be created, because your package "
                            "\"{0}\" does not include kube type with id "
                            "\"{1}\"".format(package.name, value))

    def _validate_kube_type_in_db(self, exists, field, value):
        if exists:
            kube = Kube.query.get(value)
            if not kube:
                self._error(field, 'No such kube_type: "{0}"'.format(value))
            elif not kube.is_public() and self.user != KUBERDOCK_INTERNAL_USER:
                self._error(field, 'Forbidden kube type: "{0}"'.format(value))

    def _validate_pd_backend_required(self, pd_backend_required, field, value):
        if pd_backend_required and not (AWS or CEPH):
            self._error(field, 'persistent storage backend wasn\'t configured')

    def _validate_type_ipv4(self, field, value):
        try:
            socket.inet_pton(socket.AF_INET, value)
        except socket.error:
            self._error(field, 'Invalid ipv4 address')

    def _validate_type_ipv4_net(self, field, value):
        try:
            ip_network(value)
        except (ValueError, AttributeError):
            self._error(field, 'Invalid IPv4 network')

    def _validate_type_strnum(self, field, value):
        try:
            float(value)
        except ValueError:
            self._error(field, '{0} should be string or number'.format(field))

    def _validate_resolvable(self, resolvable, field, value):
        if resolvable:
            try:
                socket.gethostbyname(value)
            except socket.error:
                self._error(field,
                            "Can't be resolved. "
                            "Check /etc/hosts file for correct Node records")

    def _validate_match_volumes(self, match_volumes, field, value):
        """Used in pod spec root to check that volumeMounts match volumes"""
        if match_volumes:
            volumes_mismatch = check_volumes_match(value)
            if volumes_mismatch:
                self._error(field, volumes_mismatch)

    def _validate_pd_size_max(self, exists, field, value):
        if exists:
            max_size = SystemSettings.get_by_name('persitent_disk_max_size')
            if max_size and int(value) > int(max_size):
                self._error(field, (
                    'Persistent disk size must be less or equal '
                    'to "{0}" GB').format(max_size))

    def _validate_max_kubes_per_container(self, exists, field, value):
        if exists:
            max_size = SystemSettings.get_by_name('max_kubes_per_container')
            if max_size and int(value) > int(max_size):
                self._error(field, (
                    'Container cannot have more than {0} kubes.'.format(
                        max_size)))

    def _validate_package_exists(self, exists, field, value):
        if exists:
            if Package.by_name(value) is None:
                self._error(field, "Package doesn't exist")

    def _validate_package_id_exists(self, exists, field, value):
        if exists:
            if Package.query.get(int(value)) is None:
                self._error(field, ('Package with id "{0}" does not exist'
                                    .format(value)))

    def _validate_domain_exists(self, exists, field, value):
        if (exists and
                BaseDomain.filter(BaseDomain.name == value).first() is None):
            self._error(field, 'Domain "{0}" doesn\'t exists'.format(value))

    def _validate_url_with_schema(self, should_be_with_schema, field, value):
        if should_be_with_schema and not urlparse(value).scheme:
            self._error(field, ('Schema is missing. Please, specify URL '
                                'with "http[s]://".'))

    def _validate_image(self, obj, field, value):
        if not isinstance(obj, dict):
            obj = {}
        if not container_image_regex.match(value) and \
                obj.get('validate_image'):
            self._error(field, "Image URL must be in format [registry/]image")
        elif Image(value).tag == 'latest' and obj.get('validate_latest'):
            self._error(field, self.ERROR_SHOULD_NOT_USE_LATEST)


def check_int_id(id):
    try:
        int(id)
    except ValueError:
        raise APIError('Invalid id')


def check_image_search(searchkey):
    validator = V()
    if not validator.validate(
            {'searchkey': searchkey},
            {'searchkey': image_search_schema}):
        raise ValidationError(validator.errors['searchkey'])


def check_image_request(params):
    V()._api_validation(params, image_request_schema)


def check_node_data(data):
    V(allow_unknown=True)._api_validation(data, node_schema)
    if is_ip(data['hostname']):
        raise ValidationError('Please add nodes by hostname, not by ip')

    try:
        get_timezone()
    except OSError as err:
        raise ValidationError(
            'Unable to decect timezone on master: "{}". Please set timezone '
            'before adding a node.'.format(repr(err)))


def is_ip(addr):
    try:
        socket.inet_pton(socket.AF_INET, addr)
    except socket.error:
        return False
    else:
        return True


def check_hostname(hostname):
    validator = V()
    if not validator.validate({'Hostname': hostname},
                              {'Hostname': hostname_schema}):
        raise ValidationError(validator.errors)
    if is_ip(hostname):
        raise ValidationError('Please, enter hostname, not ip address.')


def check_change_pod_data(data):
    data = V(allow_unknown=True)._api_validation(data, command_pod_schema)
    # TODO: with cerberus 0.10, just use "purge_unknown" option
    return {
        'command': data.get('command'),
        'edited_config': data.get('edited_config'),
        'commandOptions': data.get('commandOptions') or {},
        'containers': [{'name': c.get('name'), 'kubes': c.get('kubes')}
                       for c in data.get('containers') or []]
    }


def check_new_pod_data(data, user=None, **kwargs):
    # FIXME: in cerberus 0.9.1 "corece" in nested fields doesn't work right:
    # .validated({'a': 123, 'b': {'a': 456}},
    #            {'a': {}, 'b': {'type': 'dict',
    #                            'schema': {'a': {'coerce': str}}}})
    # -> {'a': '456', 'b': {'a': 456}}
    # use normalisation only after upgrade to Cerberus 1.0 ...
    validator = V(user=None if user is None else user.username, **kwargs)
    if not validator.validate(data, new_pod_schema):
        raise ValidationError(validator.errors)

    # TODO: with cerberus 1.0 use "rename" normalization rule
    for container in data['containers']:
        for port in container.get('ports') or []:
            if port.get('podPort'):
                port['hostPort'] = port.pop('podPort')
    volumes_mismatch = check_volumes_match(data)
    if volumes_mismatch:
        raise ValidationError(volumes_mismatch)
    return data


def check_pod_dump(data, user=None, **kwargs):
    kwargs.setdefault('allow_unknown', True)
    validator = V(user=None if user is None else user.username, **kwargs)
    if not validator.validate(data, pod_dump_schema):
        raise ValidationError(validator.errors)

    # TODO: with cerberus 1.0 use "rename" normalization rule
    for container in data['pod_data']['containers']:
        for port in container.get('ports') or []:
            if port.get('podPort'):
                port['hostPort'] = port.pop('podPort')
    volumes_mismatch = check_volumes_match(data['pod_data'])
    if volumes_mismatch:
        raise ValidationError(volumes_mismatch)
    return data


def check_internal_pod_data(data, user=None):
    validator = V(user=None if user is None else user.username)
    if not validator.validate(data, new_pod_schema):
        raise APIError(validator.errors)
    kube_type = data.get('kube_type', Kube.get_default_kube_type())
    if Kube.get_internal_service_kube_type() != kube_type:
        raise APIError('Internal pod must be of type {0}'.format(
            Kube.get_internal_service_kube_type()))


def check_system_settings(data):
    validator = V()
    name = data.get('name', '')
    value = data.get('value', '')

    # Purely cosmetic issue: forbid leading '+'
    if name in ['persitent_disk_max_size', 'cpu_multiplier',
                'memory_multiplier', 'max_kubes_per_container']:
        if not re.match(r'[0-9]', value):
            fmt = 'Value for "{0}" is expected to start with digits'
            raise APIError(
                fmt.format(' '.join(name.split('_')).capitalize(), ))

    if name in ['persitent_disk_max_size', 'max_kubes_per_container',
                'max_kubes_trial_user']:
        if not validator.validate({'value': value},
                                  {'value': positive_non_zero_integer_schema}):
            fmt = 'Incorrect value for "{0}" limit'
            raise APIError(
                fmt.format(' '.join(name.split('_')).capitalize(), ))
    elif name == 'cpu_multiplier':
        if not validator.validate({'value': value},
                                  {'value': cpu_multiplier_schema}):
            raise APIError('Incorrect value for CPU multiplier')
    elif name == 'memory_multiplier':
        if not validator.validate({'value': value},
                                  {'value': memory_multiplier_schema}):
            raise APIError('Incorrect value for Memory multiplier')
    elif name == 'email':
        if not validator.validate({'value': value},
                                  {'value': {'type': 'email'}}):
            raise APIError('Incorrect value for email')
    elif name == 'billing_url':
        if not validator.validate({'value': value},
                                  {'value': {'type': 'string',
                                             'url_with_schema': True}}):
            raise APIError('Incorrect value for billing URL: {}'.format(
                validator.errors['value']))


class UserValidator(V):
    """Validator for user api"""

    username_regex = {
        'regex': re.compile(r'^[A-Z0-9](?:[A-Z0-9_-]{0,23}[A-Z0-9])?$',
                            re.IGNORECASE),
        'message': 'Username should contain only Latin letters and '
                   'Numbers and must not be more than 25 characters in length'
    }

    def __init__(self, *args, **kwargs):
        self.id = kwargs.get('id')
        super(UserValidator, self).__init__(*args, **kwargs)

    def _validate_unique_case_insensitive(self, model_field, field, value):
        model = model_field.class_

        taken_query = model.query.filter(
            func.lower(model_field) == func.lower(value)
        )
        if self.id is not None:  # in case of update
            taken_query = taken_query.filter(model.id != self.id)
        if taken_query.first() is not None:
            self._error(field, 'has already been taken')

    def _validate_role_exists(self, exists, field, value):
        if exists:
            if Role.by_rolename(value) is None:
                self._error(field, "Role doesn't exists")

    def validate_user(self, data, update=False):
        data = _clear_timezone(data, ['timezone'])
        data = self._api_validation(data, user_schema, update=update)
        # TODO: with cerberus 0.10, just use "purge_unknown" option
        data = {key: value for key, value in data.iteritems()
                if key in user_schema}
        return data

    def _validate_type_username(self, field, value):
        """Validates username by username_regex and email validator"""
        if self.username_regex['regex'].match(value):
            return

        super(UserValidator, self)._validate_type_email(field, value)

        if 'username' in self.errors:
            self._error(field, self.username_regex['message'])


def _clear_timezone(data, keys):
    """Clears timezone fields - removes UTC offset from timezone string:
    Europe/London (+000) -> Europe/London
    """
    if not data:
        return data
    for key in keys:
        if key in data:
            data[key] = strip_offset_from_timezone(data[key])
    return data


def check_pricing_api(data, schema, *args, **kwargs):
    validated = V(allow_unknown=True)._api_validation(data, schema,
                                                      *args, **kwargs)
    # purge unknown
    data = {field: value for field, value in validated.iteritems()
            if field in schema}
    return data


def check_volumes_match(pod_config):
    names = {v.get('name', '') for v in pod_config.get('volumes') or []}

    for container in pod_config.get('containers') or []:
        for volume_mount in container.get('volumeMounts') or []:
            if 'name' in volume_mount and volume_mount['name'] not in names:
                return ('Volume "{0}" ({1}) is not defined in volumes list'
                        .format(volume_mount.get('name'),
                                volume_mount.get('mountPath')))
