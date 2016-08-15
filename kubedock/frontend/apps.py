from flask import Blueprint, request, render_template
from collections import namedtuple
from kubedock.kapi.apps import PredefinedApp
from kubedock.exceptions import PredefinedAppExc
from kubedock.login import current_user
from kubedock.system_settings.models import SystemSettings


apps = Blueprint('apps', __name__, url_prefix='/apps')

PLAN_FIELDS_ORDER = {'kubeType': 0, 'kube': 1, 'pdSize': 2}


@apps.route('/<app_hash>', methods=['GET'], strict_slashes=False)
def index(app_hash):
    plan_id = request.args.get('plan')
    try:
        app = PredefinedApp.get_by_qualifier(app_hash)
        set_package_if_present(app)
        data = dict(name=app.name, predesc=app.get_predescription())
        data['package_id'] = app._get_package().id
        data['token2'] = request.args.get('token2')
        data['plans'] = app.get_plans()
        if plan_id is None or not plan_id.isdigit():
            if len(data['plans']) > 1:
                return render_template('apps/plans.html', **data)
            data['plan_id'] = 0
        data.setdefault('plan_id', int(plan_id))
        prepare(app, data)
        return render_template('apps/index.html', **data)
    except PredefinedAppExc.InvalidTemplate, e:
        return render_template('apps/error.html', message=str(e)), 500


def prepare(app, data):
    """
    Prefills template data
    :param app: obj -> PredefinedApp instance
    :param data: dict -> data to be fed to template
    """
    prepare_system_settings(data)
    data['template_id'] = app.id
    loaded_plans = app.get_loaded_plans()
    data['plan_entities'] = get_plan_entities(loaded_plans[data['plan_id']])
    sort_key = (lambda field:
                PLAN_FIELDS_ORDER.get(
                    data['plan_entities'].get(field.name)))
    ent = app.get_used_plan_entities(data['plan_id'])
    data['entities'] = sorted(ent.values(), key=sort_key)
    data['has_simple'] = bool(set(ent.name for ent in data['entities']
                              if not ent.hidden) - set(data['plan_entities']))


def prepare_system_settings(data):
    """
    Process system settings and puts'em into data
    :param data: dict -> data to be fed to template
    """
    keys = ('billing_type', 'persitent_disk_max_size')
    n = namedtuple('N', 'billing maxsize')._make(keys)
    data.update({k: SystemSettings.get_by_name(k) for k in keys})
    if not data[n.maxsize]:
        data[n.maxsize] = 10
    if data[n.billing].lower() == 'no billing':
        return


def set_package_if_present(app):
    if current_user.is_authenticated():
        return app.set_package(current_user.package.id)
    pkg_id = request.args.get('pkgid')
    if pkg_id is not None:
        app.set_package(pkg_id)


def get_plan_entities(plan):
    entities = {}
    cls = PredefinedApp.TemplateField
    for pod in plan.get('pods', []):
        if isinstance(pod.get('kubeType'), cls):
            entities[pod['kubeType'].name] = 'kubeType'
        for container in pod.get('containers', []):
            if isinstance(container.get('kubes'), cls):
                entities[container['kubes'].name] = 'kube'
        for pd in pod.get('persistentDisks', []):
            if isinstance(pd.get('pdSize'), cls):
                entities[pd['pdSize'].name] = 'pdSize'
    return entities
