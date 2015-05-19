import socket
import cerberus
import cerberus.errors
from copy import deepcopy

from .api import APIError
from .billing import Kube


"""
This schemes it's just a shortcut variables for convenience and reusability
"""
# ===================================================================
PATH_LENGTH = 512

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


# Kubernetes restriction, names must be dns-compatible
pod_name = r"^(([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])+$"
pod_name_scheme = {
    'type': 'string',
    'empty': False,
    'required': True,
    'maxlength': 63,    # kubernetes restriction
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
    'portalIP': {                                   # ignore, read-only
        'type': 'ipv4',
        'nullable': True
    },
    'replicas': {'type': 'integer', 'min': 0},
    'kube_type': {'type': 'integer', 'min': 0, 'required': True},
    'cluster': {'type': 'boolean'},
    'node': {'type': 'string', 'nullable': True},
    'save_only': {'type': 'boolean'},
    'freeHost': {'type': 'string', 'required': False, 'nullable': True},
    'set_public_ip': {'type': 'boolean', 'required': False},
    'public_ip': {'type': 'ipv4', 'required': False},
    'restartPolicy': {
        'type': 'dict',
        'restart_polices': ['always', 'onFailure', 'never']
    },
#    'namespace': {'type': 'string', 'required': True},
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
                'source': {
                    'type': 'dict',
                    'schema': {
                        'hostDir': {
                            'type': 'dict',
                            'nullable': True,
                            'schema': {
                                'path': {
                                    'type': 'string',
                                    'required': False,
                                    'nullable': True,
                                    'empty': False,
                                    'maxlength': PATH_LENGTH,
                                    # TODO validate that dir exists on node
                                    # 'dirExist': True
                                }
                            }
                        },
                        'persistentDisk': {
                            'type': 'dict',
                            'nullable': True,
                            'schema': {
                                'pdName': {
                                    'type': 'string'
                                },
                                'pdSize': {
                                    'type': 'integer'
                                }
                            }
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
                    }
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
                # TODO delete when swich from v1beta1 to 3
                'cpu': {'type': 'integer', 'required': False},
                'memory': {'type': 'integer', 'required': False},
                'capabilities': {'type': 'dict', 'required': False},
                'imagePullPolicy': {
                    'type': 'string',
                    'allowed': ['PullAlways', 'PullIfNotPresent', 'IfNotPresent'],
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
                'kubes': {'type': 'integer', 'min': 1},
                'image': container_image_name_scheme,
                'imageID': {
                    'type': 'string',
                    'required': False
                },
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
                            'containerPort': port_scheme,
                            'hostPort': nullable_port_scheme,  # TODO nullable?
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
    'annotations': {
        'type': 'dict',
        'required': False
    },
    # service params
    'price': {'type': 'strnum', 'empty': True, 'required': False},
    'kubes': {'type': 'strnum', 'empty': True, 'required': False},
})
change_pod_scheme['containers']['schema']['schema']['volumeMounts']\
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
    # TODO my be custom regex validator for allow compiled regexps
    # TODO custom error messages for regex
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

    def _validate_restart_polices(self, polices, field, value):
        if (len(value.keys()) != 1) or (value.keys()[0] not in polices):
            self._error(field,
                        'Restart Policy should be only one of %s' % polices)


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
            {'Container image name': container_image_name_scheme}):
        raise APIError(validator.errors)


def check_node_data(data):
    validator = V(allow_unknown=True)
    if not validator.validate(data, {
            'hostname': hostname_scheme,
            'kube_type': {'type': 'integer', 'min': 0, 'required': True},
        }):
        raise APIError(validator.errors)
    if data['ip'] == data['hostname']:
        raise APIError('Please add nodes by hostname, not by ip')
    kube_type = data.get('kube_type', 0)
    check_kube_indb(kube_type)


def check_hostname(hostname):
    validator = V()
    if not validator.validate({'Hostname': hostname},
                              {'Hostname': hostname_scheme}):
        raise APIError(validator.errors)
    try:
        socket.inet_pton(socket.AF_INET, hostname)
    except socket.error:
        pass
    else:
        raise APIError('Please, enter hostname, not ip address.')


def check_change_pod_data(data):
    validator = V()
    if not validator.validate(data, change_pod_scheme):
        raise APIError(validator.errors)


def check_new_pod_data(data):
    validator = V()
    if not validator.validate(data, new_pod_scheme):
        raise APIError(validator.errors)
    kube_type = data.get('kube_type', 0)
    check_kube_indb(kube_type)
