import json
import yaml

from flask import Blueprint, request, render_template, current_app
from flask.ext.login import current_user
from ..utils import APIError
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
        billing_url = SystemSettings.get_by_name('billing_url')
        if billing_url:
            billing_url += '/cart.php'
        max_pd_size = SystemSettings.get_by_name('persitent_disk_max_size') or 10
        name = app.get('name', 'app')
        template = app.get('template', '')
        kapi_papps.validate_template(template)

        parsed = yaml.safe_load(template)
        kuberdock = parsed['kuberdock']
        plans = kuberdock.get('appPackages')
        fields = kapi_papps.parse_fields(template)

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
            name=name, package=package, template=kapi_papps.unescape(template),
            default_kube_type_id=Kube.get_default_kube_type(),
        )

        if plan is None:  # display plans
            page = 'apps/plans.html'
            parsed_static = yaml.safe_load(kapi_papps.fill(template, fields))
            static_plans = parsed_static['kuberdock']['appPackages']
            check_package_has_kubes(package, static_plans)
            data.update(plans=static_plans)
        else:  # display additional configuration
            page = 'apps/index.html'
            plan_fields = get_plan_fields(plan)
            filter_fields_from_plans(fields, [p for p in plans if p != plan])
            sort_key = lambda field: PLAN_FIELDS_ORDER.get(plan_fields.get(field['name']))
            data.update(
                appPackageID=kuberdock['appPackages'].index(plan),
                billing_url=billing_url,
                max_pd_size=max_pd_size,
                fields=sorted(fields.itervalues(), key=sort_key),
                plan_fields=plan_fields,
                has_simple=bool(set(field['name'] for field in fields.itervalues()
                                    if not field['hidden']) - set(plan_fields)),
            )

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
            package_id = kuberdock.get('userPackage', 0)
        package = Package.query.get(package_id)
        if package is None:
            package = Package.query.get(0)
    return dict(package.to_dict(),
                kubes=[dict(pk.kube.to_dict(), price=pk.kube_price)
                       for pk in package.kubes])


def get_plan_fields(plan):
    fields = {}
    for pod in plan.get('pods', []):
        name, _, _ = kapi_papps.get_value(pod.get('kubeType', ''), with_reused=True)
        fields[name] = 'kubeType'
        for container in pod.get('containers', []):
            name, _, _ = kapi_papps.get_value(container.get('kubes', ''), with_reused=True)
            fields[name] = 'kube'
        for pd in pod.get('persistentDisks', []):
            name, _, _ = kapi_papps.get_value(pd.get('pdSize', ''), with_reused=True)
            fields[name] = 'pdSize'

    fields.pop(None, None)  # if name was None
    return fields


def filter_fields_from_plans(fields, plans):
    in_plans = kapi_papps.parse_fields(json.dumps(plans))
    for name in set(fields) & set(in_plans):
        for text in in_plans[name]['occurrences']:
            fields[name]['occurrences'].remove(text)
        if not fields[name]['occurrences']:
            fields.pop(name)
