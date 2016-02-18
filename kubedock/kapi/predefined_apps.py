import re
import string
import random
from collections import Mapping, Sequence

import yaml

from ..utils import APIError
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


FIELD_PARSER = re.compile(
    r'\$(?:'                  # match $$ (escaped $) or $VAR[|default:<>|Label]$
        r'(?P<name>[\w\-]+)'  # name: alphanumeric, -, _
        r'(?:\|default:'      # default and label: any symbol except \,|,$; or any escaped symbol
            r'(?P<default>(?:[^\\\|\$]|\\[\s\S])+|)'
            r'\|'
            r'(?P<label>(?:[^\\\|\$]|\\[\s\S])+|)'
        r')?'                 # default and label are optioanl
    r')?\$'
)  # NOQA


def validate_template(template):
    """Validates saving template text.
    Now checks:
        - validity of custom variables in template;
        - plans section, including kube type check.
            If it is specified, then it must be one of existing types.

    """
    try:  # find all variables and prepare YAML for loading
        template, fields = preprocess(template, raise_=True)
    except AppParseError as err:
        raise_validation_error('customFields', str(err))
    try:  # load
        parsed_template = load(template, fields)
    except (yaml.scanner.ScannerError, yaml.parser.ParserError):
        raise_validation_error(u'common', u'Invalid yaml format')

    # fill template with defaults and leave only fields that are necessary for
    # filling template (filter out fields in YAML-comments, for example)
    filled_template, fields = fill(parsed_template, fields)
    try:
        find_root(filled_template)
    except AppParseError as err:
        raise_validation_error(
            u'common', u'Invalid application structure: {}'.format(str(err))
        )

    check_plans(filled_template)

    return fields, filled_template, parsed_template, template


def check_plans(yml):
    """Checks validity of plans in application structure.
    :param app_struct: dict or list for application structure.
    :raise: APIError in case of invalid kube type.

    """
    validator = V(allow_unknown=True)
    validator.validate(yml, predefined_app_schema)
    if validator.errors:
        # TODO: remove legacy error schema.
        # See TODO for raise_validation_error
        key, val = validator.errors.items()[0]
        raise_validation_error(key, val)

    error = lambda msg: raise_validation_error('appPackages', msg)

    plans = yml['kuberdock']['appPackages']
    if len([plan for plan in plans if plan.get('recommended')]) != 1:
        error('Exactly one appPackage must be recommended.')

    pod = find_root(yml)
    for plan in plans:
        for podPlan in plan.get('pods', []):
            if podPlan['name'] != yml['metadata']['name']:
                error('Pod {0} not found in spec'.format(podPlan['name']))

            names = set(c['name'] for c in pod['containers'])
            used = set()
            for containersPlan in podPlan.get('containers', []):
                if containersPlan['name'] not in names:
                    error('Container "{0}"" not found in pod "{1}"'
                          .format(containersPlan['name'], podPlan['name']))
                if containersPlan['name'] in used:
                    error('Dublicate container name in appPackage: "{0}"'
                          .format(containersPlan['name']))
                used.add(containersPlan['name'])

            names = set(c['name'] for c in pod.get('volumes', []))
            used = set()
            for pdPlan in podPlan.get('persistentDisks', []):
                if pdPlan['name'] not in names:
                    error('Volume "{0}" not found in pod "{1}"'
                          .format(pdPlan['name'], podPlan['name']))
                if pdPlan['name'] in used:
                    error('Dublicate volume name in appPackage: "{0}"'.format(pdPlan['name']))
                used.add(pdPlan['name'])


def find_root(app_struct):
    if not isinstance(app_struct, (dict, list)):
        raise AppParseError('Invalid yaml template: top level element must be '
                            'list or dict')
    try:
        if app_struct['kind'] == 'ReplicationController':
            return app_struct['spec']['template']['spec']
        if app_struct['kind'] == 'Pod':
            return app_struct['spec']
    except (TypeError, KeyError):
        pass
    raise AppParseError("Not found 'spec' section")


def generate(length=8, symbols=string.lowercase + string.digits):
    rv = ''.join(random.choice(symbols) for i in range(length - 1))
    return random.choice(string.lowercase) + rv


# TODO: this is a weird schema. If you need to specify,
# that this is a validation error, use APIError.type
# If you need to validate smth, use stuff in kubedock.validation
def raise_validation_error(key, error):
    raise ValidationError({'validationError': {key: error}})


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
            field = TemplateField(name, default, label)
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
                raise AppParseError(
                    'Variable is not defined (found a short form ${0}$, but '
                    'never full ${0}|default:...$)'.format(field.name))

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


class TemplateField(object):
    """Used to represent each unique variable in template"""
    def __init__(self, name, default=None, label=None):
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
