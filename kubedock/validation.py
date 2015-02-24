import socket
import cerberus
import cerberus.errors
from copy import deepcopy

from .api import APIError


"""
This schemes it's just a shortcut variables for convenience and reusability
"""
# ===================================================================
container_image_name = r"^[a-zA-Z0-9_]+[a-zA-Z0-9/:_!.\-]*$"
container_image_name_scheme = {
    'type': 'string',
    'empty': False,
    'required': True,
    'maxlength': 128,
    'regex': container_image_name,
}


lastadded_image_scheme = deepcopy(container_image_name_scheme)
lastadded_image_scheme['required'] = False


# http://stackoverflow.com/questions/1418423/the-hostname-regex
hostname_regex = r"^(?=.{1,255}$)[0-9A-Za-z](?:(?:[0-9A-Za-z]|-){0,61}[0-9A-Za-z])?(?:\.[0-9A-Za-z](?:(?:[0-9A-Za-z]|-){0,61}[0-9A-Za-z])?)*\.?$"
hostname_scheme = {
    'type': 'string',
    'empty': False,
    'required': True,
    'maxlength': 255,
    'regex': hostname_regex,
    'resolvable': True,
}


pod_name = r"^[a-zA-Z0-9_]+[a-zA-Z0-9._\- ]*$"
pod_name_scheme = {
    'type': 'string',
    'empty': False,
    'required': True,
    'maxlength': 255,
    'regex': pod_name,
}


port_scheme = {
    'type': 'integer',
    'min': 0,
    'max': 65535,
}
nullable_port_scheme = deepcopy(port_scheme)
nullable_port_scheme['nullable'] = True


new_pod_scheme = {
    'name': pod_name_scheme,
    'lastAddedImage': lastadded_image_scheme,       # ignored
    'port': nullable_port_scheme,                   # ignore, read-only
    'portalIP': {                                   # ignore, read-only
        'type': 'ipv4',
        'nullable': True
    },
    'service': {'type': 'boolean'},
    'replicas': {'type': 'integer', 'min': 0},
    'kubes': {'type': 'integer', 'min': 0},
    'cluster': {'type': 'boolean'},
    'save_only': {'type': 'boolean'},
    'restartPolicy': {
        'type': 'dict',
        'restart_polices': ['always', 'onFailure', 'never']
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
                    'allowed': ['PullAlways', 'PullIfNotPresent'],
                    'required': False
                },
                'resources': {
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
                'cpu': {'type': 'integer', 'min': 0},
                # TODO check real or buyed ram
                'memory': {'type': 'integer', 'min': 0},
                'image': container_image_name_scheme,
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
                            'containerPort': port_scheme,
                            'hostPort': nullable_port_scheme,
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
                            'mountPath': {'type': 'string'},
                            'name': {'type': 'string'},
                            'readOnly': {'type': 'boolean'}
                        }
                    }
                },
                'workingDir': {
                    'type': 'list',
                    'schema': {
                        'type': 'string'
                    }
                },
            }
        }
    }
}

change_pod_scheme = deepcopy(new_pod_scheme)
change_pod_scheme.update({
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
        'regex': pod_name
    },
    'dockers': {'type': 'list'},                    # retrieved from kubernetes
    'labels': {                                     # TODO when implement
        'type': 'dict',
        'required': False
    },
})
change_pod_scheme['containers']['schema']['schema']['workingDir'] = {
    'type': 'string'
}
# ===================================================================


class V(cerberus.Validator):
    """
    This class is for all custom and our app-specific validators and types,
    implement any new here.
    """
    # TODO my be custom regex validator for allow compiled regexps
    # TODO custom error messages for regex
    def _validate_type_ipv4(self, field, value):
        try:
            socket.inet_pton(socket.AF_INET, value)
        except socket.error:
            self._error(field, 'Invalid ipv4 address')

    def _validate_resolvable(self, resolvable, field, value):
        if resolvable:
            try:
                socket.gethostbyname(value)
            except socket.error:
                self._error(field,
                            "Can't be resolved. "
                            "Check /etc/hosts file for correct Node records")

    def _validate_restart_polices(self, polices, field, value):
        if (len(value.keys()) != 1) or (value.keys()[0] not in polices):
            self._error(field,
                        'Restart Policy should be only one of %s' % polices)


def check_int_id(id):
    try:
        int(id)
    except ValueError:
        raise APIError('Invalid id')


def check_container_image_name(searchkey):
    validator = V()
    if not validator.validate(
            {'Container image name': searchkey},
            {'Container image name': container_image_name_scheme}):
        raise APIError(validator.errors)


def check_node_data(data):
    # TODO remove when implement other fields
    validator = V(allow_unknown=True)
    if not validator.validate(data, {
            'hostname': hostname_scheme,
            # 'annotations': '',
            # 'labels': '',
        }):
        raise APIError(validator.errors)


def check_hostname(hostname):
    validator = V()
    if not validator.validate({'Hostname': hostname},
                              {'Hostname': hostname_scheme}):
        raise APIError(validator.errors)


def check_change_pod_data(data):
    validator = V()
    if not validator.validate(data, change_pod_scheme):
        raise APIError(validator.errors)


def check_new_pod_data(data):
    validator = V()
    if not validator.validate(data, new_pod_scheme):
        raise APIError(validator.errors)