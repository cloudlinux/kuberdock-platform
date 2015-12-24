import re
import string
import random

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


#:Custom variable pattern
# Everything in form '$sometext$' will be treated as custom variable definition
# Escaped $ signs will not be treated as variable pattern
CUSTOM_VAR_PATTERN = re.compile(r'[^\\](\$[^\$\\]+\$)')
# Valid variable must be in form:
CORRECT_VARIABLE_FORMAT_DESCRIPTION = \
"$<VARIABLE_NAME|default:<word 'autogen' or some default value>|VAR_DESCRIPTION>$"
VARIABLE_PATTERN = \
    re.compile(r'^\$([^\|\$\\]+)\|default:([^\|\$\\]+)\|([^\|\$\\]+)\$$')
REUSED_VARIABLE_PATTERN = re.compile(r'^\$([^\|\$\\]+)\$$')


def validate_template(template):
    """Validates saving template text.
    Now checks:
        - validity of custom variables in template;
        - plans section, including kube type check.
            If it is specified, then it must be one of existing types.

    """
    check_custom_variables(template)
    try:
        parsed_template = yaml.safe_load(template)
    except (yaml.scanner.ScannerError, yaml.parser.ParserError):
        raise_validation_error(u'common', u'Invalid yaml format')
    if not isinstance(parsed_template, (dict, list)):
        raise_validation_error(
            u'common',
            u'Invalid yaml template: top level element must be list or dict'
        )

    filled_template = yaml.safe_load(fill(template, parse_fields(template)))
    try:
        find_root(filled_template)
    except AppParseError as err:
        raise_validation_error(
            u'common', u'Invalid application structure: {}'.format(str(err))
        )

    check_plans(filled_template)


def check_custom_variables(template):
    """Checks validity of custom variables in template.
    :param template: string with template content
    :raise: APIError in case of invalid variables.

    """
    custom_vars = find_custom_vars(template)
    if not custom_vars:
        return

    valid_vars = {}
    unknown_vars = []
    for var in custom_vars:
        try:
            name, _, _ = get_value(var, True)
            valid_vars[name] = var
        except AppParseError:
            unknown_vars.append({
                'name': get_reused_variable_name(var),
                'item': var
            })
    unknown_vars = [
        item['item'] for item in unknown_vars
        if item['name'] not in valid_vars
    ]
    if unknown_vars:
        raise_validation_error('customVars', unknown_vars)


def find_custom_vars(text):
    custom = CUSTOM_VAR_PATTERN.findall(text)
    return custom


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
    try:
        if app_struct['kind'] == 'ReplicationController':
            return app_struct['spec']['template']['spec']
        if app_struct['kind'] == 'Pod':
            return app_struct['spec']
    except (TypeError, KeyError):
        pass
    raise AppParseError("Not found 'spec' section")


def generate(length=8, symbols=string.lowercase+string.digits):
    rv = ''.join(random.choice(symbols) for i in range(length-1))
    return random.choice(string.lowercase) + rv


def parse_fields(text):
    custom = find_custom_vars(text)
    fields = {}
    for item in custom:
        hidden = False
        name, value, title = get_value(item, with_reused=True)
        if not name:
            continue
        if value == 'autogen':
            value = generate()
            hidden = True
        elif value is not None and value.lower() == 'user_domain_list':
            value = item
            hidden = True
        if name in fields:
            field = fields[name]
            field['occurrences'].append(item)
            if field['value'] is None:  # $VAR_NAME$ was before full definition
                field['value'], field['title'], field['hidden'] = value, title, hidden
        else:
            fields[name] = {'title': title, 'value': value, 'name': name,
                            'hidden': hidden, 'occurrences': [item]}
    return fields


def fill(template, fields):
    for field in fields.values():
        for text in field['occurrences']:
            template = template.replace(text, field['value'], 1)
    return template


def get_value(value, strict=False, with_reused=False):
    if not isinstance(value, basestring):
        if strict:
            raise AppParseError(u'Invalid custom variable: {}'.format(value))
        return (None, value, None)
    m = VARIABLE_PATTERN.match(value)
    if m is None:
        if strict:
            raise AppParseError(u'Invalid custom variable: {}'.format(value))
        if with_reused:
            return get_reused_variable_name(value, strict), None, None
        return (None, value, None)
    varname, defaultvalue, description = m.groups()
    return (varname, defaultvalue, description)


def get_reused_variable_name(value, strict=False):
    if not isinstance(value, basestring):
        if strict:
            raise AppParseError(u'Invalid custom variable: {}'.format(value))
        return None
    m = REUSED_VARIABLE_PATTERN.match(value)
    if m is None:
        if strict:
            raise AppParseError(u'Invalid custom variable: {}'.format(value))
        return None
    return m.groups()[0]


# TODO: this is a weird schema. If you need to specify,
# that this is a validation error, use APIError.type
# If you need to validate smth, use stuff in kubedock.validation
def raise_validation_error(key, error):
    raise ValidationError({'validationError': {key: error}})


def unescape(text):
    """Removes escaping characters '\' from escaped delimiters of custom
    variables: '\$' -> '$'.
    """
    return text.replace(r'\$', r'$')
