import re
import socket
import cerberus
import cerberus.errors
from copy import deepcopy

from sqlalchemy import func

from .api import APIError
from .billing import Kube
from .users.models import User
from .settings import KUBERDOCK_INTERNAL_USER, AWS, CEPH


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


username_regex = {
    'regex': re.compile(r'^[A-Z0-9](?:[A-Z0-9_-]{0,23}[A-Z0-9])?$', re.IGNORECASE),
    'message': 'only letters of Latin alphabet, numbers, hyphen and underscore are allowed'
}
name_schema = {'type': 'string',
               'nullable': True,
               'maxlength': 25,
               'regex': {'regex': re.compile(r'^[A-Z]{,25}$', re.IGNORECASE),
                         'message': 'only letters of Latin alphabet are allowed'}}
create_user_schema = {
    'username': {
        'type': 'string',
        'required': True,
        'empty': False,
        'unique_case_insensitive': User.username,
        'maxlength': 25,
        'regex': username_regex,
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
        'type': 'boolean',
        'required': True,
    },
}


new_pod_schema = {
    'name': pod_name_schema,
    'clusterIP': {                                   # ignore, read-only
        'type': 'ipv4',
        'nullable': True
    },
    'replicas': {'type': 'integer', 'min': 0},
    'kube_type': {'type': 'integer', 'min': 0, 'required': True},
    'replicationController': {'type': 'boolean'},
    'node': {'type': 'string', 'nullable': True},
    'set_public_ip': {'type': 'boolean', 'required': False},    # TODO remove
    'public_ip': {'type': 'ipv4', 'required': False},
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
                    # TODO this name must be unique, per what?
                    'type': 'string',
                    'empty': False,
                    'maxlength': 255,
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
                                    # TODO validate that dir exists on node
                                    # 'dirExist': True
                                }
                            }
                        }
                    ]
                },
                'emptyDir': {
                    'type': 'dict',
                    'nullable': True
                },
                'scriptableDisk': {
                    'type': 'dict',
                    'nullable': True
                },
                'awsElasticBlockStore': {
                    'type': 'dict',
                    'nullable': True
                },
                'gitRepo': {
                    'type': 'dict',
                    'nullable': True
                },
                'glusterfs': {
                    'type': 'dict',
                    'nullable': True
                },
                'iscsi': {
                    'type': 'dict',
                    'nullable': True
                },
                'nfs': {
                    'type': 'dict',
                    'nullable': True
                },
                'secret': {
                    'type': 'dict',
                    'nullable': True
                }
            },
        }
    },
    'containers': {
        'type': 'list',
        'minlength': 1,
        'schema': {
            'type': 'dict',
            'schema': {
                'capabilities': {'type': 'dict', 'required': False},
                'imagePullPolicy': {
                    'type': 'string',
                    'allowed': ['PullAlways', 'PullIfNotPresent', 'IfNotPresent'],
                    'required': False
                },
                'limits': {
                    'type': 'dict',
                    'required': False
                },
                'command': {
                    'type': 'list',
                    # 'minlength': 1,
                    'schema': {
                        'type': 'string',
                        'empty': False
                    }
                },
                'args': {
                    'type': 'list',
                    # 'minlength': 1,
                    'schema': {
                        'type': 'string',
                        'empty': False
                    }
                },
                'kubes': {'type': 'integer', 'min': 1},
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
                'env': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'name': {
                                'type': 'string',
                                'maxlength': 255,
                                'empty': False,
                                # 'regex': ''     # maybe needed
                            },
                            'value': {'type': 'string'},
                        },
                    }
                },
                'ports': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'containerPort': port_schema,
                            'hostPort': nullable_port_schema,  # TODO nullable?
                            'isPublic': {'type': 'boolean'},
                            'protocol': {
                                'type': 'string',
                                'maxlength': 255
                            },
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
                            'name': {'type': 'string'},    # TODO depend volumes
                            'readOnly': {'type': 'boolean'}
                        }
                    }
                },
                'workingDir': {
                    'type': 'string',
                    'maxlength': PATH_LENGTH,
                },
                "terminationMessagePath": {
                    'type': 'string',
                    'maxlength': PATH_LENGTH,
                    'nullable': True
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
    # service params
    'price': {'type': 'strnum', 'empty': True, 'required': False},
    'kubes': {'type': 'strnum', 'empty': True, 'required': False},
})
change_pod_schema['containers']['schema']['schema']['volumeMounts']\
['schema']['schema']['path'] = {
    'type': 'string',
    'maxlength': PATH_LENGTH,
    'required': False
}
# ===================================================================


class V(cerberus.Validator):
    """
    This class is for all custom and our app-specific validators and types,
    implement any new here.
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
            if value.get('type') in self.type_map:
                value['type'] = self.type_map[value.get('type')]
        return super(V, self).validate_schema(schema)

    def _api_validation(self, data, schema, **kwargs):
        if not self.validate(data, schema, **kwargs):
            raise APIError(self.errors)

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

        message = 'value "{value}" does not match regex "{regex}"'
        if isinstance(re_obj, dict):
            message = re_obj['message']
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


def check_int_id(id):
    try:
        int(id)
    except ValueError:
        raise APIError('Invalid id')


def check_kube_indb(kube_type):
    if not Kube.query.get(kube_type):
        raise APIError('No such kube_type: {0}'.format(kube_type))


def check_container_image_name(searchkey):
    validator = V()
    if not validator.validate(
            {'Container image name': searchkey},
            {'Container image name': container_image_name_schema}):
        raise APIError(validator.errors)


def check_node_data(data):
    validator = V(allow_unknown=True)
    if not validator.validate(data, {
            'hostname': hostname_schema,
            'kube_type': {'type': 'integer', 'min': 0, 'required': True},
        }):
        raise APIError(validator.errors)
    if is_ip(data['hostname']):
        raise APIError('Please add nodes by hostname, not by ip')
    kube_type = data.get('kube_type', 0)
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
    kube_type = data.get('kube_type', 0)
    check_kube_indb(kube_type)


class UserValidator(V):
    """Validator for user api"""

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
        self._api_validation(data, create_user_schema)

    def validate_user_update(self, data):
        self._api_validation(data, create_user_schema, update=True)
