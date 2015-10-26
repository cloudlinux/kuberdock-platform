import re

from ..utils import APIError
from ..predefined_apps.models import PredefinedApp as PredefinedAppModel


class PredefinedApps(object):
    def __init__(self, user=None):
        if user is not None and not isinstance(user, int):
            user = user.id
        self.user = user

        self.apps = PredefinedAppModel.query
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

    def create(self, name, template, validate=False):
        if template is None:
            raise APIError('Template not specified')
        if validate:
            validate_template(template)
        app = PredefinedAppModel(user_id=self.user, name=name, template=template)
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
CUSTOM_VAR_PATTERN = re.compile(r'\$[^\$]+\$')
# Valid variable must be in form:
CORRECT_VARIABLE_FORMAT_DESCRIPTION = \
"$<VARIABLE_NAME|default:<word 'autogen' or some default value>|VAR_DESCRIPTION>$"
VARIABLE_PATTERN = re.compile(r'^\$([^\|\$]+)\|default:([^\|\$]+)\|([^\|\$]+)\$$')


def validate_template(template):
    """Validates saving template text.
    Now checks only validity of custom variables in template.

    """
    custom_vars = find_custom_vars(template)
    if not custom_vars:
        return
    errors = []
    for var in custom_vars:
        if not VARIABLE_PATTERN.match(var):
            errors.append(var)
    if errors:
        raise APIError({'validationError': {'customVars': errors}})


def find_custom_vars(text):
    custom = CUSTOM_VAR_PATTERN.findall(text)
    return custom
