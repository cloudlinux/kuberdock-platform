from .. import kdclick

from ..kdclick.access import ADMIN


@kdclick.group('predefined-apps',
               help='Commands for predefined applications management.',
               available_for=ADMIN)
def pa():
    pass


@pa.command()
@kdclick.option('--file-only', is_flag=True)
@kdclick.pass_obj
def list(obj, **params):
    return obj.kdctl.predefined_apps.list(**params)


@pa.command()
@kdclick.argument('app-id')
@kdclick.option('--file-only', is_flag=True)
@kdclick.pass_obj
def get(obj, **params):
    return obj.kdctl.predefined_apps.get(**params)


@pa.command()
@kdclick.data_argument('template', type=kdclick.types.text)
@kdclick.option('--name', required=True, help='Application name.')
@kdclick.option('--origin', required=False, help='Origin of application.')
@kdclick.option('--validate', is_flag=True,
                help='Provide if validation is needed.')
@kdclick.pass_obj
def create(obj, **params):
    return obj.kdctl.predefined_apps.create(**params)


@pa.command()
@kdclick.argument('app-id')
@kdclick.data_argument('template', type=kdclick.types.text)
@kdclick.option('--name', required=False, help='Application name.')
@kdclick.option('--validate', is_flag=True,
                help='Provide if validation is needed.')
@kdclick.pass_obj
def update(obj, **params):
    return obj.kdctl.predefined_apps.update(**params)


@pa.command()
@kdclick.argument('app-id')
@kdclick.pass_obj
def delete(obj, **params):
    return obj.kdctl.predefined_apps.delete(**params)


@pa.command('validate-template')
@kdclick.data_argument('template', type=kdclick.types.text)
@kdclick.pass_obj
def validate_template(obj, **params):
    return obj.kdctl.predefined_apps.validate_template(**params)
