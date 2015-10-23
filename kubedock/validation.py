import re
import socket
import cerberus
import cerberus.errors
from copy import deepcopy

from sqlalchemy import func

from .api import APIError
from .billing import Kube
from .predefined_apps.models import PredefinedApp
from .users.models import User
from .nodes.models import Node
from .settings import (KUBERDOCK_INTERNAL_USER, AWS, CEPH,
                       MAX_KUBES_PER_CONTAINER)


SUPPORTED_VOLUME_TYPES = ['persistentDisk', 'localStorage']

"""
This schemas it's just a shortcut variables for convenience and reusability
"""
# ===================================================================
PATH_LENGTH = 512

container_image_name = r"^[a-zA-Z0-9_]+[a-zA-Z0-9/:_!.\-]*$"
container_image_name_schema = {
    'type': 'string',
    'empty': False,
    'required': True,
    'maxlength': 128,
    'regex': container_image_name,
}

ascii_string = {
    'type': str, 'regex': {
        'regex': re.compile(ur'^[\u0000-\u007f]*$'),  # ascii range
        'message': 'must be an ascii string'}}

image_request_schema = {
    'image': dict(ascii_string, empty=False, required=True),
    'auth': {
        'type': dict,
        'required': False,
        'nullable': True,
        'schema': {
            'username': dict(ascii_string, empty=False, required=True),
            'password': dict(ascii_string, empty=False, required=True)
        },
    },
    'refresh_cache': {'coerce': bool},
}

# http://stackoverflow.com/questions/1418423/the-hostname-regex
hostname_regex = re.compile(r"^(?=.{1,255}$)[0-9A-Z](?:(?:[0-9A-Z]|-){0,61}[0-9A-Z])?"
                            r"(?:\.[0-9A-Z](?:(?:[0-9A-Z]|-){0,61}[0-9A-Z])?)*\.?$",
                            re.IGNORECASE)
hostname_schema = {
    'type': 'string',
    'empty': False,
    'required': True,
    'maxlength': 255,
    'regex': hostname_regex,
    'resolvable': True,
}


email_local_regex = re.compile(
    r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*\Z"  # dot-atom
    r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-\011\013\014\016-\177])*"\Z)',  # quoted-string
    re.IGNORECASE)
email_domain_regex = re.compile(
    r'^(?=.{1,255}$)(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'
    r'(?P<root>[A-Z0-9-]{2,63}(?<![-0-9]))\Z',
    re.IGNORECASE)
email_literal_regex = re.compile(
    # literal form, ipv4 or ipv6 address (SMTP 4.1.3)
    r'\[([A-f0-9:\.]+)\]\Z',
    re.IGNORECASE)


# Kubernetes restriction, names must be dns-compatible
# pod_name = r"^(([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])+$"
pod_name_schema = {
    'type': 'string',
    'empty': False,
    'required': True,
    'maxlength': 63,    # kubernetes restriction (was)
    # 'regex': pod_name,
}


port_schema = {
    'type': 'integer',
    'min': 0,
    'max': 65535,
}
nullable_port_schema = deepcopy(port_schema)
nullable_port_schema['nullable'] = True


name_schema = {
    'type': 'string',
    'nullable': True,
    'maxlength': 25,
    'regex': {
        'regex': re.compile(r'^[A-Z]{,25}$', re.IGNORECASE),
        'message': 'only letters of Latin alphabet are allowed'
    }
}

create_user_schema = {
    'username': {
        'type': ['username', 'email'],
        'required': True,
        'empty': False,
        'unique_case_insensitive': User.username,
        'maxlength': 50,
    },
    'email': {
        'type': 'email',
        'required': True,
        'empty': False,
        'unique_case_insensitive': User.email,
        'maxlength': 50.
    },
    'password': {
        'type': 'string',
        'required': True,
        'empty': False,
        'maxlength': 25.
    },
    'first_name': name_schema,
    'last_name': name_schema,
    'middle_initials': name_schema,
    'rolename': {
        'type': 'string',
        'required': True,
        'empty': False,
        'maxlength': 64.
    },
    'package': {
        'type': 'string',
        'required': True,
        'empty': False,
        'maxlength': 64,
    },
    'active': {
        'type': 'extbool',
        'required': True,
    },
    'suspended': {
        'type': 'extbool',
        'required': False,
    },
}


args_list_schema = {'type': 'list', 'schema': {'type': 'string', 'empty': False}}
env_schema = {'type': 'list', 'schema': {'type': 'dict', 'schema': {
    'name': {'type': 'string', 'required': True, 'empty': False, 'maxlength': 255},
    'value': {'type': 'string', 'required': True},
}}}
path_schema = {'type': 'string', 'maxlength': PATH_LENGTH}
protocol_schema = {'type': 'string', 'allowed': ['TCP', 'tcp', 'UDP', 'udp']}
new_pod_schema = {
    'name': pod_name_schema,
    'clusterIP': {
        'type': 'ipv4',
        'nullable': True,
        'internal_only': True,
    },
    'replicas': {'type': 'integer', 'min': 0, 'max': 1},
    'kube_type': {
        'type': 'integer',
        'required': True,
        'kube_type_exists': True,
    },
    'kuberdock_template_id': {
        'type': 'integer',
        'min': 0,
        'nullable': True,
        'template_exists': True,
    },
    'replicationController': {'type': 'boolean'},   # TODO remove
    'node': {
        'type': 'string',
        'nullable': True,
        'internal_only': True,
    },
    'set_public_ip': {'type': 'boolean', 'required': False},    # TODO remove
    'public_ip': {'type': 'ipv4', 'required': False},           # TODO remove
    'restartPolicy': {
        'type': 'string', 'required': True,
        'allowed': ['Always', 'OnFailure', 'Never']
    },
    'volumes': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {
                    'type': 'string',
                    'empty': False,
                    'maxlength': 255,
                    'volume_type_required': True,
                },
                'persistentDisk': {
                    'type': 'dict',
                    'nullable': True,
                    'pd_backend_required': True,
                    'schema': {
                        'pdName': {
                            'type': 'string'
                        },
                        'pdSize': {
                            'type': 'integer',
                            'nullable': True,
                        },
                        'used': {
                            'type': 'boolean',
                            'required': False,
                        }
                    }
                },
                'localStorage': {
                    'nullable': True,
                    'anyof': [
                        {'type': 'boolean'},
                        {
                            'type': 'dict',
                            'schema': {
                                'path': {
                                    'type': 'string',
                                    'required': False,
                                    'nullable': False,
                                    'empty': False,
                                    'maxlength': PATH_LENGTH,
                                    # allowed only for kuberdock-internal
                                    'internal_only': True,
                                }
                            }
                        }
                    ]
                },
                # 'emptyDir': {
                #     'type': 'dict',
                #     'nullable': True
                # },
                # 'scriptableDisk': {
                #     'type': 'dict',
                #     'nullable': True
                # },
                # 'awsElasticBlockStore': {
                #     'type': 'dict',
                #     'nullable': True
                # },
                # 'gitRepo': {
                #     'type': 'dict',
                #     'nullable': True
                # },
                # 'glusterfs': {
                #     'type': 'dict',
                #     'nullable': True
                # },
                # 'iscsi': {
                #     'type': 'dict',
                #     'nullable': True
                # },
                # 'nfs': {
                #     'type': 'dict',
                #     'nullable': True
                # },
                # 'secret': {
                #     'type': 'dict',
                #     'nullable': True
                # },
            },
        }
    },
    'containers': {
        'type': 'list',
        'minlength': 1,
        'required': True,
        'schema': {
            'type': 'dict',
            'schema': {
                'sourceUrl': {'type': 'string', 'required': False},
                'capabilities': {'type': 'dict', 'required': False},
                # 1) right choices are 'Always', 'IfNotPresent', 'Never'
                # 2) anyway we will overwrite it to "imagePullPolicy: Always"
                # 'imagePullPolicy': {
                #     'type': 'string',
                #     'allowed': ['PullAlways', 'PullIfNotPresent', 'IfNotPresent'],
                #     'required': False
                # },
                'limits': {
                    'type': 'dict',
                    'required': False
                },
                'command': args_list_schema,
                'args': args_list_schema,
                'kubes': {'type': 'integer',
                          'min': 1,
                          'max': MAX_KUBES_PER_CONTAINER},
                'image': container_image_name_schema,
                'parentID': {
                    'type': 'string',
                    'required': False
                },
                'name': {
                    'type': 'string',
                    'empty': False,
                    'maxlength': 255
                },
                'env': env_schema,
                'ports': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'containerPort': dict(port_schema, required=True),
                            # null if not public
                            'hostPort': dict(port_schema, nullable=True),
                            'isPublic': {'type': 'boolean'},
                            'protocol': protocol_schema,
                        }
                    }
                },
                'volumeMounts': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'mountPath': {
                                'type': 'string',
                                'maxlength': PATH_LENGTH,
                            },
                            'name': {
                                'type': 'string',
                                'has_volume': True,
                            },
                            'readOnly': {'type': 'boolean'}     # TODO remove
                        },
                    }
                },
                'workingDir': path_schema,
                "terminationMessagePath": {
                    'type': 'string',
                    'maxlength': PATH_LENGTH,
                    'nullable': True
                },
                'secret': {
                    'type': 'dict',
                    'nullable': True,
                    'schema': {
                        'username': {'type': 'string', 'nullable': True},
                        'password': {'type': 'string', 'nullable': True},
                    }
                }
            }
        }
    }
}

change_pod_schema = deepcopy(new_pod_schema)
change_pod_schema.update({
    'owner': {                                      # ignore, read-only
        'type': 'string',
        'maxlength': 255,
        'empty': False,
    },
    'status': {                                     # ignore, read-only
        'type': 'string',
        'empty': False,
    },
    'command': {
        'type': 'string',
        'allowed': ['start', 'stop', 'resize'],
    },
    'id': {
        'type': 'string',
        'maxlength': 36,
    },
    'sid': {
        'type': 'string',
        'maxlength': 1024
    },
    'containerPort': {
        'type': 'integer',
        'required': False
    },
    'checked': {'type': 'boolean', 'required': False},
    'servicename': {
        'type': 'string',
        'required': False,
        'empty': False,
        # 'regex': pod_name
    },
    'labels': {                                     # TODO when implement
        'type': 'dict',
        'required': False
    },
    'annotations': {
        'type': 'dict',
        'required': False
    },
    'kubes': {'type': 'strnum', 'empty': True, 'required': False},
})
change_pod_schema['containers']['schema']['schema']['volumeMounts']\
['schema']['schema']['path'] = {
    'type': 'string',
    'maxlength': PATH_LENGTH,
    'required': False
}


# billing

positive_float_schema = {'coerce': float, 'min': 0}
positive_integer_schema = {'coerce': int, 'min': 0}
billing_name_schema = {'type': 'string', 'maxlength': 64,
                       'required': True, 'empty': False}
package_schema = {
    'name': billing_name_schema,
    'first_deposit': positive_float_schema,
    'currency': {'type': 'string', 'maxlength': 16, 'empty': False},
    'period': {'type': 'string', 'maxlength': 16, 'empty': False,
               'allowed': ['hour', 'month', 'quarter', 'annuel']},
    'prefix': {'type': 'string'},
    'suffix': {'type': 'string'},
    'price_ip': positive_float_schema,
    'price_pstorage': positive_float_schema,
    'price_over_traffic': positive_float_schema,
}

kube_schema = {
    'name': billing_name_schema,
    'cpu': positive_float_schema,
    'memory': positive_integer_schema,
    'disk_space': positive_integer_schema,
    'included_traffic': positive_integer_schema,
    'cpu_units': {'type': 'string', 'maxlength': 32, 'empty': False,
                  'allowed': ['Cores']},
    'memory_units': {'type': 'string', 'maxlength': 3, 'empty': False,
                     'allowed': ['MB']},
    'disk_space_units': {'type': 'string', 'maxlength': 3, 'empty': False,
                         'allowed': ['GB']},
}

packagekube_schema = {
    'kube_price': dict(positive_float_schema, required=True),
    'id': positive_integer_schema
}


# ===================================================================


class V(cerberus.Validator):
    """
    This class is for all custom and our app-specific validators and types,
    implement any new here.
    Additionally supports type 'extbool' - extended bool, value may be a boolean
    or one of ('true', 'false', '1', '0')
    """
    # TODO: add readable error messages for regexps in old schemas
    type_map = {str: 'string',
                int: 'integer',
                float: 'float',
                bool: 'boolean',
                dict: 'dict',
                list: 'list',
                # None: 'string'  # you can use `None` to set the default type
                set: 'set'}

    def __init__(self, *args, **kwargs):
        self.user = kwargs.get('user')
        super(V, self).__init__(*args, **kwargs)

    def validate_schema(self, schema):
        """
        Little hack to allow us to use sandard python types (or anything at all)
        for type validation. Just map it to some string in self.type_map
        """
        for value in schema.itervalues():
            vtype = value.get('type')
            if not vtype:
                continue
            if isinstance(vtype, (list, tuple)):
                value['type'] = [
                    self.type_map.get(typeentry, typeentry)
                    for typeentry in vtype
                ]
            else:
                value['type'] = self.type_map.get(vtype, vtype)
        return super(V, self).validate_schema(schema)

    def _api_validation(self, data, schema, **kwargs):
        validated = self.validated(data, schema, **kwargs)
        if validated is None:
            raise APIError(self.errors)
        return validated

    def _validate_regex(self, re_obj, field, value):
        """
        The same as original Validator._validate_regex, but can accept
        pre-compiled regex as a parameter or a regex-object:
        {'regex': <pattern or compiled regex>, 'message': <custom error message>}

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
            self._error(field, message.format(value=value, regex=re_obj.pattern))

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
                self._error(field, 'There is no template with such template_id')

    def _validate_kube_type_exists(self, exists, field, value):
        if exists:
            if value == Kube.get_internal_service_kube_type():
                return
            templ = Node.query.filter(Node.kube_id == value).first()
            if templ is None:
                self._error(field, "Pod can't be created, because cluster has "
                                   "no nodes with such kube type, please "
                                   "contact administrator.")

    def _validate_pd_backend_required(self, pd_backend_required, field, value):
        if pd_backend_required and not (AWS or CEPH):
            self._error(field, 'persistent storage backend wasn\'t configured')

    def _validate_type_ipv4(self, field, value):
        try:
            socket.inet_pton(socket.AF_INET, value)
        except socket.error:
            self._error(field, 'Invalid ipv4 address')

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

    def _validate_has_volume(self, has_volume, field, value):
        # Used in volumeMounts
        if has_volume:
            if not self.document.get('volumes'):
                self._error(field,
                            'Volume is needed, but no volumes are described')
                return
            vol_names = [v.get('name', '') for v in self.document['volumes']]
            if value not in vol_names:
                self._error(
                    field,
                    'Volume "{0}" is not defined in volumes list'.format(value))

    def _validate_volume_type_required(self, vtr, field, value):
        # Used in volumes list
        if vtr:
            for vol in self.document['volumes']:
                if vol.keys() == ['name']:
                    self._error(field,
                        'Volume type is required for volume "{0}"'.format(value))
                    return
                for k in vol.keys():
                    if k not in SUPPORTED_VOLUME_TYPES + ['name']:
                        self._error(field,
                                    'Unsupported volume type "{0}"'.format(k))

    def _validate_type_extbool(self, field, value):
        """Validate 'extended bool' it may be bool, string with values
        ('0', '1', 'true', 'false')

        """
        if not isinstance(value, (bool, str, unicode)):
            self._error(field, u'Invalid type. Must be bool or string')
        if isinstance(value, (str, unicode)):
            valid_values = ['true', 'false', '0', '1']
            if value.lower() not in valid_values:
                self._error(field,
                            u'Invalid value "{}". Must be one of: {}'.format(
                                value, valid_values))


def check_int_id(id):
    try:
        int(id)
    except ValueError:
        raise APIError('Invalid id')


def check_kube_indb(kube_type):
    kube = Kube.query.get(kube_type)
    if not kube:
        raise APIError('No such kube_type: {0}'.format(kube_type))
    if not kube.is_public():
        raise APIError('Forbidden kube type: {0}'.format(kube_type))


def check_container_image_name(searchkey):
    validator = V()
    if not validator.validate(
            {'Container image name': searchkey},
            {'Container image name': container_image_name_schema}):
        raise APIError(validator.errors)


def check_image_request(params):
    V()._api_validation(params, image_request_schema)


def check_node_data(data):
    validator = V(allow_unknown=True)
    if not validator.validate(data, {
            'hostname': hostname_schema,
            'kube_type': {'type': 'integer', 'min': 0, 'required': True},
        }):
        raise APIError(validator.errors)
    if is_ip(data['hostname']):
        raise APIError('Please add nodes by hostname, not by ip')
    kube_type = data.get('kube_type', Kube.get_default_kube_type())
    check_kube_indb(kube_type)


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
        raise APIError(validator.errors)
    if is_ip(hostname):
        raise APIError('Please, enter hostname, not ip address.')


def check_change_pod_data(data):
    validator = V()
    if not validator.validate(data, change_pod_schema):
        raise APIError(validator.errors)


def check_new_pod_data(data, user=None):
    validator = V(user=None if user is None else user.username)
    if not validator.validate(data, new_pod_schema):
        raise APIError(validator.errors)
    kube_type = data.get('kube_type', Kube.get_default_kube_type())
    check_kube_indb(kube_type)


def check_internal_pod_data(data, user=None):
    validator = V(user=None if user is None else user.username)
    if not validator.validate(data, new_pod_schema):
        raise APIError(validator.errors)
    kube_type = data.get('kube_type', Kube.get_default_kube_type())
    if Kube.get_internal_service_kube_type() != kube_type:
        raise APIError('Internal pod must be of type {0}'.format(
            Kube.get_internal_service_kube_type()))


class UserValidator(V):
    """Validator for user api"""

    username_regex = {
        'regex': re.compile(r'^[A-Z0-9](?:[A-Z0-9_-]{0,23}[A-Z0-9])?$',
                            re.IGNORECASE),
        'message': 'only letters of Latin alphabet, numbers, '\
                   'hyphen and underscore are allowed'
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

    def validate_user_create(self, data):
        try:
            self._api_validation(data, create_user_schema)
        except APIError:
            if 'username' in self.errors:
                self.errors['username'] = ('Username should contain only '
                                           'Latin letters and Numbers and '
                                           'must not be more than '
                                           '25 characters in length')
            raise APIError(self.errors)
        data = convert_extbools(data, create_user_schema)
        return data

    def validate_user_update(self, data):
        self._api_validation(data, create_user_schema, update=True)
        data = convert_extbools(data, create_user_schema)
        if self.allow_unknown:  # filter unknown
            return {key: value for key, value in data.iteritems()
                    if key in create_user_schema}
        return data

    def _validate_type_username(self, field, value):
        """Validates username by username_regex"""
        super(V, self)._validate_type_string(field, value)

        if not self.username_regex['regex'].match(value):
            self._error(field, self.username_regex['message'])


def convert_extbools(data, schema):
    """Converts values of extbool field types in data dict to booleans.
    Returns data dict with converted values
    """
    for field, desc in schema.iteritems():
        if field not in data:
            continue
        fieldtype = desc.get('type')
        if fieldtype != 'extbool':
            continue
        value = data[field]
        if isinstance(value, bool):
            continue
        if isinstance(value, (str, unicode)):
            if value.lower() in ('true', '1'):
                data[field] = True
                continue
        data[field] = False
    return data


def check_pricing_api(data, schema, *args, **kwargs):
    validated = V(allow_unknown=True)._api_validation(data, schema, *args, **kwargs)
    # purge unknown
    return {field: value for field, value in validated.iteritems() if field in schema}
