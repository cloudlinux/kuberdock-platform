import yaml
from copy import deepcopy

from flask import Blueprint, request, render_template, current_app
from ..login import current_user
from ..exceptions import APIError
from ..kapi.predefined_apps import PredefinedApps
from ..billing.models import Package, Kube
from ..users.models import User
from ..system_settings.models import SystemSettings
from ..kapi import predefined_apps as kapi_papps


PLAN_FIELDS_ORDER = {'kubeType': 0, 'kube': 1, 'pdSize': 2}


apps = Blueprint('apps', __name__, url_prefix='/apps')


@apps.route('/<app_hash>', methods=['GET'], strict_slashes=False)
def index(app_hash):
    try:
        plan_id = request.args.get('plan', None)
        if plan_id is not None:
            plan_id = int(plan_id)

        app = PredefinedApps().get_by_qualifier(app_hash)
        billing_type, billing_url, max_pd_size = map(
            SystemSettings.get_by_name,
            ['billing_type', 'billing_url', 'persitent_disk_max_size'])
        if billing_type.lower() != 'no billing' and billing_url:
            billing_url += current_app.billing_factory.get_app_url(billing_type)
        if not max_pd_size:
            max_pd_size = 10
        name = app.get('name', 'app')
        template = app.get('template', '')

        fields, filled_template, parsed_template, _ = \
            kapi_papps.validate_template(template)

        kuberdock = parsed_template['kuberdock']
        plans = kuberdock.get('appPackages')

        package = get_package(kuberdock)

        plan = None
        if plan_id is not None:
            try:
                plan = plans[int(plan_id)]
            except (IndexError, TypeError):
                raise kapi_papps.AppParseError
        elif len(plans) == 1:
            plan = plans[0]

        data = dict(
            name=name, package=package, template=template,
            default_kube_type_id=Kube.get_default_kube_type(),
        )

        if plan is None:  # display plans
            page = 'apps/plans.html'
            static_plans = filled_template['kuberdock']['appPackages']
            check_package_has_kubes(package, static_plans)
            data.update(plans=static_plans)
        else:  # display additional configuration
            page = 'apps/index.html'
            plan_fields = get_plan_fields(plan)
            fields = fields_not_from_plans(parsed_template, fields, plan)
            sort_key = lambda field: PLAN_FIELDS_ORDER.get(plan_fields.get(field.name))
            data.update(
                appPackageID=kuberdock['appPackages'].index(plan),
                billing_url=billing_url,
                billing_type=billing_type,
                template_id=app['id'],
                max_pd_size=max_pd_size,
                fields=sorted(fields.itervalues(), key=sort_key),
                plan_fields=plan_fields,
                has_simple=bool(set(field.name for field in fields.itervalues()
                                    if not field.hidden) - set(plan_fields)),
            )
        data['token2'] = request.args.get('token2')

        return render_template(page, **data)

    except (yaml.scanner.ScannerError, yaml.parser.ParserError) as e:
        current_app.logger.debug(e)
        return render_template('apps/error.html', message='Could not parse App config'), 500

    except kapi_papps.AppParseError as e:
        current_app.logger.debug(e)
        return render_template('apps/error.html', message='Unsupported App'), 500

    except APIError as e:
        current_app.logger.debug(e)
        msg = (e.message if isinstance(e.message, basestring) else
               yaml.safe_dump(e.message, default_flow_style=False))
        return render_template('apps/error.html', message=msg), e.status_code


def check_package_has_kubes(package, static_plans):
    kube_types = set(kube['id'] for kube in package['kubes'])
    for plan in static_plans:
        for pod in (plan.get('pods') or [{}]):
            if pod.get('kubeType', Kube.get_default_kube_type()) not in kube_types:
                raise APIError('You have no access to such type of package. '
                               'Please, contact your service provider.')


def get_package(kuberdock):
    if current_user.is_authenticated():
        user = User.get(current_user.username)
        if user is not None:
            package = user.package
    else:
        package_id = request.args.get('pkgid')
        if package_id is None:
            package_id = kuberdock.get('packageID')
        if package_id is None:
            package_id = kuberdock.get('userPackage')

        if package_id is None:
            package = Package.get_default()
        else:
            package = Package.query.get(package_id) or Package.get_default()

    return package.to_dict(with_kubes=True)


def get_plan_fields(plan):
    fields = {}
    for pod in plan.get('pods', []):
        if isinstance(pod.get('kubeType'), kapi_papps.TemplateField):
            fields[pod['kubeType'].name] = 'kubeType'
        for container in pod.get('containers', []):
            if isinstance(container.get('kubes'), kapi_papps.TemplateField):
                fields[container['kubes'].name] = 'kube'
        for pd in pod.get('persistentDisks', []):
            if isinstance(pd.get('pdSize'), kapi_papps.TemplateField):
                fields[container['pdSize'].name] = 'pdSize'
    return fields


def fields_not_from_plans(parsed_template, fields, plan):
    parsed_template = deepcopy(parsed_template)
    # remove all packages except current
    parsed_template['kuberdock']['appPackages'] = plan
    # get set of fields in this structure
    _, used_fields = kapi_papps.fill(parsed_template, fields)
    return used_fields
