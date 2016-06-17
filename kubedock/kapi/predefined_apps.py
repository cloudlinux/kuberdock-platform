import re
import string
import random
from collections import Mapping, Sequence
from numbers import Number
from copy import deepcopy

import yaml

from ..billing.models import Kube, Package
from ..exceptions import APIError
from ..predefined_apps.models import PredefinedApp as PredefinedAppModel
from ..validation import ValidationError, V, predefined_app_schema


class AppParseError(Exception):
    pass


class PredefinedApps(object):
    def __init__(self, user=None):
        if user is not None and not isinstance(user, int):
            user = user.id
        self.user = user

        self.apps = PredefinedAppModel.query.order_by(PredefinedAppModel.id)
        if self.user is not None:
            self.apps = self.apps.filter_by(user_id=self.user)

    def get(self, app_id=None):
        if app_id is None:
            return [app.to_dict() for app in self.apps]

        app = self.apps.filter_by(id=app_id).first()
        if app is None:
            raise APIError('Not found', status_code=404)
        return app.to_dict()

    def get_by_qualifier(self, qualifier):
        app = self.apps.filter_by(qualifier=qualifier).first()
        if app is None:
            raise APIError('Not found', status_code=404)
        return app.to_dict()

    def create(self, name, template, origin, validate=False):
        if template is None:
            raise APIError('Template not specified')
        if validate:
            validate_template(template)
        app = PredefinedAppModel(
            user_id=self.user, name=name, template=template, origin=origin
        )
        app.save()
        return app.to_dict()

    def update(self, app_id, name, template, validate=False):
        app = self.apps.filter_by(id=app_id).first()
        if app is None:
            raise APIError('Not found', status_code=404)
        if validate:
            validate_template(template)
        if name is not None:
            app.name = name
        if template is not None:
            app.template = template
        app.save()
        return app.to_dict()

    def delete(self, app_id):
        app = self.apps.filter_by(id=app_id).first()
        if app is None:
            raise APIError('Not found', status_code=404)
        app.delete()


FIELD_PARSER = re.compile(ur'''
    \$(?:                  # match $$ (escaped $) or $VAR[|default:<>|Label]$
        (?P<name>[\w\-]+)  # name: alphanumeric, -, _
        (?:\|default:      # default and label: any symbol except \,|,$; or any escaped symbol
            (?P<default>(?:[^\\\|\$]|\\[\s\S])+|)
            \|
            (?P<label>(?:[^\\\|\$]|\\[\s\S])+|)
        )?                 # default and label are optional
    )?\$
''', re.X)  # NOQA


def validate_template(template):
    """Validates saving template text.
    Now checks:
        - customFields: validity of custom variables in template
        - schema: schema validation of "kuberdock" section
            TODO: validate schema of the whole template
        - appPackages: appPackages section check, including kube type,
            package, existence of containers and  etc.
        - common: invalid yaml syntax and other errors
    """
    try:  # find all variables and prepare YAML for loading
        template, fields = preprocess(template, raise_=True)
    except AppParseError as err:
        raise ValidationError({'customFields': err.args[0]})
    try:  # load
        parsed_template = load(template, fields)
    except (yaml.scanner.ScannerError, yaml.parser.ParserError):
        raise ValidationError({'common': 'Invalid yaml format'})

    # fill template with defaults and leave only fields that are necessary for
    # filling template (filter out fields in YAML-comments, for example)
    filled_template, fields = fill(parsed_template, fields)
    try:
        find_root(filled_template)
    except AppParseError as err:
        raise ValidationError({'common': err.args[0]})

    check_kuberdock_section(filled_template)

    return fields, filled_template, parsed_template, template


def check_kuberdock_section(filled_template):
    """Checks validity of kuberdock section in application structure.
    :param filled_template: dict or list for application structure.
    :raise: APIError in case of invalid kube type.

    """
    validator = V(allow_unknown=True)
    yml = validator.validated(filled_template, predefined_app_schema)
    if validator.errors:
        raise ValidationError({'schema': validator.errors})

    def error(msg):
        raise ValidationError({'appPackages': msg})

    plans = yml['kuberdock']['appPackages']
    if len([plan for plan in plans if plan.get('recommended')]) != 1:
        error('Exactly one appPackage must be recommended.')


    package_id = yml['kuberdock'].get('packageID')
    if package_id is None:
        package = Package.get_default()
    else:
        package = Package.query.get(package_id) or Package.get_default()
    available_kubes = set(kube.kube_id for kube in package.kubes)

    pod = find_root(yml)
    for plan in plans:
        for podPlan in plan.get('pods', []):
            if podPlan['name'] != yml['metadata']['name']:
                error({'Pod was not found in spec': podPlan['name']})

            names = set(c['name'] for c in pod['containers'])
            used = set()
            for containersPlan in podPlan.get('containers', []):
                name = containersPlan['name']
                if name not in names:
                    error('Container "{0}" was not found in pod "{1}"'
                          .format(name, podPlan['name']))
                if name in used:
                    error({'Duplicate container name in appPackage': name})
                used.add(name)

            names = set(c['name'] for c in pod.get('volumes', []))
            used = set()
            for pdPlan in podPlan.get('persistentDisks', []):
                volume_name = pdPlan['name']
                if volume_name not in names:
                    error('Volume "{0}" not found in pod "{1}"'
                          .format(volume_name, podPlan['name']))
                if volume_name in used:
                    error({'Duplicate volume name in appPackage': volume_name})
                used.add(volume_name)

            kube_id = podPlan.get('kubeType')
            if kube_id is not None and kube_id not in available_kubes:
                error('Package with id "{0}" does not contain Kube Type '
                      'with id "{1}"'.format(package.id, kube_id))


def find_root(app_struct):
    if not isinstance(app_struct, (dict, list)):
        raise AppParseError({
            'Invalid application structure': 'top level element must be list '
                                             'or dict'
        })
    try:
        if app_struct['kind'] == 'ReplicationController':
            return app_struct['spec']['template']['spec']
        if app_struct['kind'] == 'Pod':
            return app_struct['spec']
    except (TypeError, KeyError):
        pass
    raise AppParseError(
        {'Invalid application structure': 'not found "spec" section'})


def generate(length=8, symbols=string.lowercase + string.digits):
    rv = ''.join(random.choice(symbols) for i in range(length - 1))
    return random.choice(string.lowercase) + rv


def preprocess(template, raise_=True):
    """
    Find all fields and prepare yaml for loading.
    Unescape all escaped $ ($$) and replace fields with UIDs.
    """
    fields = {}

    def replace(match):
        entire_match = match.group()
        groups = match.groupdict()
        name, default, label = groups['name'], groups['default'], groups['label']

        if entire_match == '$$':  # escaped
            return '$'  # unescape

        if name in fields:  # have met it before
            field = fields[name]
            if entire_match != '${0}$'.format(name):  # full format
                if not field.defined:
                    field.setup(default, label)
        else:  # first appearing of this variable
            start = match.start()
            line = match.string[:start].count('\n') + 1
            column = len(match.string[:start].split('\n')[-1])
            field = TemplateField(name, default, label, line, column)
            fields[name] = field

        # replace with unique aplphanum string
        # it's unique enough to say that collision won't apper ever
        return field.uid

    # replace all escaped $$ with $ and all $fields$ with UIDs
    template = FIELD_PARSER.sub(replace, template)


    if raise_:
        # check for $VAR$ without full definition ($VAR|default:...$)
        for field in fields.itervalues():
            if not field.defined:
                raise AppParseError({
                    'Variable is not defined': {
                        'line': field.line,
                        'column': field.column,
                        'message': 'found a short form ${0}$, but never full, '
                                   'like ${0}|default:...$'.format(field.name),
                    }
                })

    return template, fields


def load(template, fields):
    """Parse YAML, converting plain fields to links to TemplateField objects"""
    fields_by_uid = {field.uid: field for field in fields.itervalues()}

    class Loader(yaml.SafeLoader):
        pass

    class TemplateValue(yaml.YAMLObject):
        yaml_tag = '!kd'
        yaml_loader = Loader

        @classmethod
        def from_yaml(cls, loader, node):
            return fields_by_uid[loader.construct_scalar(node)]
    Loader.add_implicit_resolver(
        '!kd', re.compile('^(?:{0})$'.format('|'.join(fields_by_uid))), None)

    return yaml.load(template, Loader=Loader)


def fill(target, fields):
    """
    Replace all TemplateField instancies and fields inside strings with values.
    :param target: parsed (loaded) template
    :param fields:
    :returns: filled template and used fields
    """
    used_fields = {}

    def _fill(target):
        if isinstance(target, TemplateField):
            used_fields[target.name] = target
            return target.default
        if isinstance(target, basestring):
            for field in fields.itervalues():
                if field.uid in target:
                    used_fields[field.name] = field
                    target = target.replace(field.uid, unicode(field.default))
            return target
        if isinstance(target, Mapping):
            return {_fill(key): _fill(value) for key, value in target.iteritems()}
        if isinstance(target, Sequence):
            return [_fill(value) for value in target]
        return target
    return _fill(target), used_fields


def apply_package(target, pkg):
    kuberdock = target['kuberdock']
    spec = find_root(target)
    kuberdock.pop('appPackages', None)
    kuberdock['appPackage'] = {'name': pkg['name'],
                               'goodFor': pkg['goodFor']}

    if pkg.get('packagePostDescription') is not None:
        kuberdock['postDescription'] = (kuberdock.get('postDescription', '') +
                                        '\n' + pkg['packagePostDescription'])

    pods = pkg.get('pods')
    if pods:
        pod_plan = pods[0]

        if pod_plan.get('kubeType') is not None:
            kuberdock['kube_type'] = pod_plan.get('kubeType')
        elif kuberdock.get('kube_type') is None:
            kuberdock['kube_type'] = Kube.get_default_kube().id


        kubes_by_container = {c['name']: c.get('kubes')
                              for c in pod_plan.get('containers') or []}
        for container in spec['containers']:
            container['kubes'] = (kubes_by_container.get(container['name']) or
                                  container.get('kubes') or 1)

        pd_by_volume = {pd['name']: pd.get('pdSize')
                        for pd in pod_plan.get('persistentDisks') or []}
        for volume in spec.get('volumes') or []:
            pd = volume.get('persistentDisk')
            if pd:
                pd['pdSize'] = (pd_by_volume.get(volume['name']) or
                                pd.get('pdSize') or 1)

        if 'publicIP' in pkg and not pkg.get('publicIP'):
            for container in spec['containers']:
                for port in container.get('ports') or []:
                    port['isPublic'] = False

    return target


def compare(template, filled_yaml):
    preprocessed_tpl, fields = preprocess(template)
    loaded_tpl = load(preprocessed_tpl, fields)
    filled_yaml = deepcopy(filled_yaml)

    kuberdock = filled_yaml.get('kuberdock')
    kuberdock.pop('kuberdock_template_id', None)
    if (not isinstance(kuberdock, Mapping) or
            not isinstance(kuberdock.get('appPackage'), Mapping)):
        return False
    package = kuberdock.get('appPackage')
    packages_by_name = {pkg['name']: pkg
                        for pkg in loaded_tpl['kuberdock']['appPackages']}
    package = packages_by_name.get(package.get('name'))
    if package is None:
        return False
    apply_package(loaded_tpl, package)

    fields_set = set(fields.itervalues())
    any_field_regex = re.compile('(?:%USER_DOMAIN%|{0})'.format(
        '|'.join(field.uid for field in fields_set)))
    stack = [(loaded_tpl, filled_yaml)]
    while stack:
        tpl, filled = stack.pop()
        if tpl == filled:
            continue
        elif isinstance(tpl, Mapping) and isinstance(filled, Mapping):  # dict
            for key, a_value in tpl.iteritems():
                if key not in filled:
                    return False
                stack.append((a_value, filled.pop(key)))
            if filled:  # filled yaml has keys that aren't presented in template
                return False
        elif isinstance(tpl, basestring) and isinstance(filled, basestring):
            # string that contains $VARS$
            if not re.match(any_field_regex.sub('.*', re.escape(tpl)), filled):
                return False
        elif isinstance(tpl, Sequence) and isinstance(filled, Sequence):  # list
            if len(tpl) != len(filled):
                return False
            stack.extend(zip(tpl, filled))
        elif tpl in fields_set:  # plain $VAR$ (not in sting)
            if isinstance(filled, (Number, basestring)) or filled is None:
                if not hasattr(tpl, 'value'):
                    tpl.value = filled
                elif tpl.value != filled:
                    return False
        else:  # unknown type or type mismatch
            return False
    return True


class TemplateField(object):
    """Used to represent each unique variable in template"""
    def __init__(self, name, default=None, label=None, line=None, column=None):
        self.line, self.column = line, column  # for debug and validation
        self.name = name
        self.uid = generate(32)
        self.defined = False

        self.hidden = None
        self.default = None

        if default is not None:  # full definition
            self.setup(default, label)

    def setup(self, default, label):
        self.default = self.unescape(default)
        self.label = self.unescape(label or '')

        if self.default == 'autogen':
            self.hidden = True
            self.default = generate()
        else:
            self.hidden = False
            self.default = yaml.safe_load(self.default) if self.default else ''

        self.defined = True

    @staticmethod
    def unescape(value=None, _patt=re.compile(r'\\([\s\S])')):
        return _patt.sub('\1', value)
