import re
from copy import deepcopy

import pytz

from kubedock.users import User
from kubedock.constants import DOMAINNAME_LENGTH
from .coerce import extbool, get_user

PATH_LENGTH = 512

container_image_name_schema = {
    'type': 'string',
    'empty': False,
    'required': True,
    'maxlength': 128,
    'regex': {
        'regex': r'^[a-zA-Z0-9_]+[a-zA-Z0-9/:_!.\-]*$',
        'message': 'image URL must be in format [registry/]image[:tag]',
    },
}

image_search_schema = {
    'type': 'string',
    'empty': False,
    'required': True,
    'maxlength': 128,
}

ascii_string = {
    'type': 'string', 'regex': {
        'regex': re.compile(ur'^[\u0000-\u007f]*$'),  # ascii range
        'message': 'must be an ascii string'}}

image_request_schema = {
    'image': dict(ascii_string, empty=False, required=True),
    'auth': {
        'type': 'dict',
        'required': False,
        'nullable': True,
        'schema': {
            'username': dict(ascii_string, empty=False, required=True),
            'password': dict(ascii_string, empty=False, required=True)
        },
    },
    'podID': {'type': 'string', 'empty': False, 'nullable': True},
    'refresh_cache': {'coerce': bool},
}

# http://stackoverflow.com/questions/1418423/the-hostname-regex
hostname_regex = re.compile(
    r"^(?=.{1,255}$)[0-9A-Z](?:(?:[0-9A-Z]|-){0,61}[0-9A-Z])?"
    r"(?:\.[0-9A-Z](?:(?:[0-9A-Z]|-){0,61}[0-9A-Z])?)*\.?$", re.IGNORECASE)
hostname_schema = {
    'type': 'string',
    'empty': False,
    'required': True,
    'maxlength': 255,
    'regex': {
        'regex': hostname_regex,
        'message': 'invalid hostname'
    },
    'resolvable': True,
}

domain_schema = {
    'type': 'string',
    'empty': False,
    'required': False,
    'maxlength': DOMAINNAME_LENGTH,
    'regex': {
        'regex': hostname_regex,
        'message': 'invalid domain'
    },
}

email_local_regex = re.compile(
    r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+"
    r"(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*\Z"  # dot-atom
    r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|'
    r'\\[\001-\011\013\014\016-\177])*"\Z)',  # quoted-string
    re.IGNORECASE)
email_domain_regex = re.compile(
    r'^(?=.{1,255}$)(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'
    r'(?P<root>[A-Z0-9-]{2,63}(?<![-0-9]))\Z',
    re.IGNORECASE)
email_literal_regex = re.compile(
    # literal form, ipv4 or ipv6 address (SMTP 4.1.3)
    r'\[([A-f0-9:\.]+)\]\Z',
    re.IGNORECASE)

#: Restriction for environment variables names - uppercase letters, underscore,
# digits and must not start with digits.
# Do not compile it, because there is no support to deep copy of compiled
# regexps since 2.6, and this regex is participating in further deepcopy of
# schemas.
envvar_name_regex = {
    'regex': r'^[A-Za-z_]+[A-Za-z0-9_]*',
    'message': 'Latin letters, digits, undescores are expected only. '
               'Must not start with digit'
}

pdname_regex = {
    'regex': r'^[A-Za-z]+[A-Za-z0-9_\-]*',
    'message': 'Latin letters, digits, '
               'undescores and dashes are expected only. '
               'Must start with a letter'
}

# Kubernetes restriction, names must be dns-compatible
# pod_name = r"^(([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])+$"
pod_name_schema = {
    'type': 'string',
    'empty': False,
    'maxlength': 63,  # kubernetes restriction (was)
    # 'regex': pod_name,
}

port_schema = {
    'type': 'integer',
    'min': 1,
    'max': 65535,
}
nullable_port_schema = deepcopy(port_schema)
nullable_port_schema['nullable'] = True

name_schema = {
    'type': 'string',
    'nullable': True,
    'maxlength': 25,
    'regex': {
        'regex': re.compile(r'^[^\W\d]{,25}$', re.U),
        'message': 'only alphabetic characters allowed'
    }
}

user_schema = {
    'username': {
        'type': 'username',
        'required': True,
        'empty': False,
        'unique_case_insensitive': User.username,
        'maxlength': 50,
        'regex': {
            'regex': re.compile(r'.*\D'),
            'message': 'Usernames containing digits only are forbidden.',
        }
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
        'maxlength': 64,
        'role_exists': True,
    },
    'package': {
        'type': 'string',
        'required': True,
        'empty': False,
        'maxlength': 64,
        'package_exists': True,
    },
    'active': {
        'type': 'boolean',
        'required': True,
        'coerce': extbool,
    },
    'suspended': {
        'type': 'boolean',
        'required': False,
        'coerce': extbool,
    },
    'timezone': {
        'type': 'string',
        'required': False,
        'allowed': pytz.common_timezones
    },
    'clientid': {
        'type': 'integer',
        'required': False
    },
}

args_list_schema = {'type': 'list', 'schema': {'type': 'string'}}
env_schema = {'type': 'list', 'schema': {'type': 'dict', 'anyof': [
    {
        'schema': {
            'name': {
                'type': 'string',
                'required': True,
                'empty': False,
                'maxlength': 255,
                'regex': envvar_name_regex
            },
            'value': {'type': 'string', 'coerce': str, 'required': True},
        }
    },
    {
        'schema': {
            'name': {
                'type': 'string',
                'required': True,
                'empty': False,
                'maxlength': 255,
                'regex': envvar_name_regex
            },
            # TODO: The following is potentially insecure place.
            # it can expose to user ALL of the pod's fields, even those used
            # for our internal usage.
            'valueFrom': {
                'type': 'dict', 'schema': {
                    'fieldRef': {
                        'type': 'dict', 'schema': {
                            'fieldPath': {
                                'type': 'string',
                                'coerce': str,
                                'required': True
                            },
                        }
                    }
                }
            }
        }
    },
]}}
path_schema = {'type': 'string', 'maxlength': PATH_LENGTH}
protocol_schema = {'type': 'string', 'allowed': ['TCP', 'tcp', 'UDP', 'udp']}
kubes_qty_schema = {'type': 'integer', 'min': 1,
                    'max_kubes_per_container': True}
container_name_schema = {'type': 'string', 'empty': False, 'maxlength': 255}
pdsize_schema = {'type': 'integer', 'coerce': int, 'min': 1,
                 'pd_size_max': True}
pdname_schema = {'type': 'string', 'required': True, 'empty': False,
                 'maxlength': 36, 'regex': pdname_regex}
kube_type_schema = {'type': 'integer', 'coerce': int, 'kube_type_in_db': True}
volume_name_schema = {'type': 'string', 'coerce': str, 'empty': False,
                      'maxlength': 255}
restart_policy_schema = {'type': 'string',
                         'allowed': ['Always', 'OnFailure', 'Never']}
pod_resolve_schema = {'type': 'list', 'schema': {'type': 'string'}}

base_pod_config_schema = {
    'podIP': {
        'type': 'ipv4',
        'nullable': True,
        'internal_only': True,
    },
    'replicas': {'type': 'integer', 'min': 0, 'max': 1},
    'kube_type': dict(kube_type_schema, kube_type_in_user_package=True,
                      kube_type_exists=True, required=True),
    'kuberdock_resolve': pod_resolve_schema,
    'node': {
        'type': 'string',
        'nullable': True,
        'internal_only': True,
    },
    'restartPolicy': dict(restart_policy_schema, required=True),
    'volumes': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'name': dict(volume_name_schema),
                'persistentDisk': {
                    'type': 'dict',
                    'nullable': True,
                    'pd_backend_required': False,
                    'schema': {
                        'pdName': pdname_schema,
                        'pdSize': pdsize_schema,
                        'used': {
                            'type': 'boolean',
                            'required': False,
                        }
                    }
                },
                'localStorage': {
                    'nullable': True,
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
                'lifecycle': {
                    'type': 'dict',
                    'required': False
                },
                'readinessProbe': {
                    'type': 'dict',
                    'required': False
                },
                'command': args_list_schema,
                'args': args_list_schema,
                'kubes': kubes_qty_schema,
                'image': container_image_name_schema,
                'name': container_name_schema,
                'env': env_schema,
                'ports': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'containerPort': dict(port_schema, required=True),

                            # null if not public
                            # "hostPort" is deprecated, use "podPort"
                            'hostPort': dict(port_schema, nullable=True),
                            'podPort': dict(port_schema, nullable=True),

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
                                'required': True,
                            },
                            'name': {
                                'type': 'string',
                                'required': True,
                            },
                        },
                    }
                },
                'workingDir': path_schema,
                "livenessProbe": {'type': 'dict'},
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
    },
    'serviceAccount': {
        'type': 'boolean',
        'required': False,
        'internal_only': True,
    },
}
edited_pod_config_schema = deepcopy(base_pod_config_schema)
edited_pod_config_schema.update({
    'domain': domain_schema,
})

new_pod_schema = deepcopy(base_pod_config_schema)
new_pod_schema.update({
    'name': dict(pod_name_schema, required=True),
    'postDescription': {
        'type': 'string',
        'nullable': True,
    },
    'kuberdock_template_id': {
        'type': 'integer',
        'min': 0,
        'nullable': True,
        'template_exists': True,
    },
    'kuberdock_plan_name': {
        'type': 'string',
        'nullable': True,
    },
    'dnsPolicy': {
        'type': 'string', 'required': False,
        'allowed': ['ClusterFirst', 'Default']
    },
    'status': {
        'type': 'string', 'required': False,
        'allowed': ['stopped', 'unpaid']
    },
    'domain': domain_schema,
})


command_pod_schema = {
    'command': {'type': 'string', 'allowed': ['start', 'stop', 'redeploy',
                                              'set', 'edit']},
    'commandOptions': {
        'type': 'dict',
        'schema': {
            'wipeOut': {'type': 'boolean', 'nullable': True},
            'status': {'type': 'string', 'required': False,
                       'allowed': ['unpaid', 'stopped']},
            'name': pod_name_schema,
            'postDescription': {'type': 'string', 'nullable': True},
        }
    },

    'edited_config': {
        'type': 'dict',
        'match_volumes': True,
        'nullable': True,
        'schema': edited_pod_config_schema,
    },

    # things that user allowed to change during pod's redeploy
    'containers': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'kubes': kubes_qty_schema,
                'name': dict(container_name_schema, required=True),
            }
        }
    }
}


pd_schema = {
    'name': pdname_schema,
    'size': dict(pdsize_schema, required=True),
}

# billing

positive_float_schema = {'coerce': float, 'min': 0}
positive_integer_schema = {'coerce': int, 'min': 0}
positive_non_zero_integer_schema = {'coerce': int, 'min': 1}
billing_name_schema = {'type': 'string', 'maxlength': 64,
                       'required': True, 'empty': False}

kube_name_schema = {
    'type': 'string',
    'maxlength': 25,
    'required': True,
    'empty': False,
    'regex': {
        'regex': r'^(?:[A-Za-z0-9]+[A-Za-z0-9 ]*)?$',
        'message': 'Name may contain Latin alphabet letters, digits, spaces '
                   'and should not start with a space'
    }
}

package_schema = {
    'name': billing_name_schema,
    'first_deposit': positive_float_schema,
    'currency': {'type': 'string', 'maxlength': 16, 'empty': False},
    'period': {'type': 'string', 'maxlength': 16, 'empty': False,
               'allowed': ['hour', 'month', 'quarter', 'annual']},
    'prefix': {'type': 'string', 'maxlength': 16},
    'suffix': {'type': 'string', 'maxlength': 16},
    'price_ip': positive_float_schema,
    'price_pstorage': positive_float_schema,
    'price_over_traffic': positive_float_schema,
    'is_default': {'type': 'boolean', 'coerce': extbool, 'required': False},
    'count_type': {'type': 'string', 'maxlength': 5, 'required': False,
                   'allowed': ['payg', 'fixed']},
}

kube_schema = {
    'name': kube_name_schema,
    'cpu': {'coerce': float, 'min': 0.01, 'max': 9.99, 'required': True},
    'memory': {'coerce': int, 'min': 1, 'max': 99999, 'required': True},
    'disk_space': {'coerce': int, 'min': 1, 'max': 999, 'required': True},
    'included_traffic': {
        'coerce': int, 'min': 0, 'max': 99999, 'required': True
    },
    'cpu_units': {'type': 'string', 'maxlength': 32, 'empty': False,
                  'allowed': ['Cores']},
    'memory_units': {'type': 'string', 'maxlength': 3, 'empty': False,
                     'allowed': ['MB']},
    'disk_space_units': {'type': 'string', 'maxlength': 3, 'empty': False,
                         'allowed': ['GB']},
    'is_default': {'type': 'boolean', 'coerce': extbool, 'required': False}
}

packagekube_schema = {
    'kube_price': dict(positive_float_schema, required=True),
    'id': positive_integer_schema
}

cpu_multiplier_schema = {
    'coerce': float, 'min': 1, 'max': 100
}

memory_multiplier_schema = {
    'coerce': float, 'min': 1, 'max': 100
}

app_package_schema = {
    'name': {
        'type': 'string',
        'empty': False,
        'required': True,
        'maxlength': 32,
    },
    'recommended': {
        'type': 'boolean',
        'coerce': extbool,
    },
    'goodFor': {
        'type': 'string',
        'maxlength': 64,
    },
    'publicIP': {
        'type': 'boolean',
        'coerce': extbool,
    },
    'pods': {
        'type': 'list',
        'maxlength': 1,  # we don't support multiple pods in one app yet
        'schema': {
            'type': 'dict',
            'schema': {
                'name': dict(pod_name_schema, required=True),
                'kubeType': kube_type_schema,
                'containers': {
                    'type': 'list',
                    'empty': False,
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'name': container_name_schema,
                            'kubes': kubes_qty_schema,
                        },
                    },
                },
                'persistentDisks': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'name': volume_name_schema,
                            'pdSize': pdsize_schema,
                        },
                    },
                },
            },
        },
    },
}
predefined_apps_kuberdock_schema = {
    'preDescription': {'type': 'string'},
    'postDescription': {'type': 'string'},
    'packageID': {
        'type': 'integer',
        'coerce': int,
        'package_id_exists': True,
    },
    'appPackages': {
        'type': 'list',
        'required': True,
        'empty': False,
        'maxlength': 4,
        'schema': {
            'type': 'dict',
            'schema': app_package_schema,
        },
    },
    'resolve': pod_resolve_schema,
}
predefined_apps_spec_schema = {
    'restartPolicy': restart_policy_schema,
    'resolve': pod_resolve_schema,
    'containers': new_pod_schema['containers'],
    'volumes': new_pod_schema['volumes'],
}
predefined_app_schema = {
    'apiVersion': {
        'type': 'string',
        'allowed': ['v1'],
    },
    'metadata': {
        'type': 'dict',
        'required': True,
        'schema': {
            'name': {
                'type': 'string',
                'required': True,
            },
        },
    },
    'kuberdock': {
        'type': 'dict',
        'required': True,
        'schema': predefined_apps_kuberdock_schema,
    },
    'kind': {
        'type': 'string',
        'allowed': ['ReplicationController', 'Pod'],
    },
    'spec': {
        'type': 'dict',
        'anyof': [{
            'match_volumes': True,
            'schema': dict(predefined_apps_spec_schema, **{
                'replicas': {'type': 'integer', 'min': 1, 'max': 1},
            }),
        }, {
            'schema': {
                'template': {
                    'type': 'dict',
                    'schema': {
                        'replicas': {'type': 'integer', 'min': 1, 'max': 1},
                        'spec': {
                            'type': 'dict',
                            'match_volumes': True,
                            'schema': predefined_apps_spec_schema,
                        },
                    },
                },
            },
        }],
    },
}

node_schema = {'hostname': hostname_schema, 'kube_type': kube_type_schema}

ippool_schema = {
    'network': {'type': 'ipv4_net', 'required': True},
    'autoblock': {
        'type': 'string',
        'nullable': True,
    },
    'node': {
        'type': 'string',
        'nullable': True,
        # Optional because schema should be the same both when
        # NONFLOATING_PUBLIC_IPS is either True and False.
        'required': False,
    },
}

owner_optional_schema = {
    'coerce': get_user,
    'required': False,
    'nullable': True
}

owner_mandatory_schema = {
    'coerce': get_user,
    'required': True,
    'nullable': False
}
