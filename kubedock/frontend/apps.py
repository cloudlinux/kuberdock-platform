import yaml
import json

from flask import Blueprint, render_template
from ..utils import APIError
from ..kapi.predefined_apps import PredefinedApps
from ..billing.models import Package
from ..system_settings.models import SystemSettings


apps = Blueprint('apps', __name__, url_prefix='/apps')

class AppParseError(Exception):
    pass

@apps.route('/<app_hash>', methods=['GET'], strict_slashes=False)
def index(app_hash):
    try:
        app = PredefinedApps().get_by_qualifier(app_hash)
        billing_url = SystemSettings.read_setting('billing_apps_link')
        if billing_url is None:
            billing_url = ''
        try:
            name = app.get('name', 'app')
            app = yaml.safe_load(app.get('template'))
        except yaml.scanner.ScannerError:
            return render_template('apps/error.html', message='Could not parse App config'), 500
    except APIError:
        return render_template('apps/error.html', message='No such application'), 404
    try:
        root = find_root(app)
        containers = root['containers']
        packages, kubes = get_kubes()
        template, kube_type, kubes_data = process_yaml(app)
        return render_template('apps/index.html',
                               name=name,
                               packages=packages,
                               kubes=json.dumps(kubes),
                               containers=containers,
                               template=template,
                               kube_type=kube_type,
                               kubes_data=kubes_data,
                               billing_url=billing_url)
    except (AppParseError, KeyError):
        return render_template('apps/error.html', message='Invalid or incomplete App'), 500


def find_root(app):
    if app['kind'] == 'ReplicationController':
        return app['spec']['template']['spec']
    elif app['kind'] == 'Pod':
        return app['spec']
    else:
        raise AppParseError


def get_kubes():
    packages = []
    kubes = {}
    for p in Package.query.all():
        packages.append({'id': p.id, 'name': p.name})
        for k in p.kubes:
            if p.id not in kubes:
                kubes[p.id] = []
            kube = {'id': k.kubes.id,
                    'name': k.kubes.name,
                    'price': k.kube_price,
                    'cpu': k.kubes.cpu,
                    'cpu_units': k.kubes.cpu_units,
                    'memory': k.kubes.memory,
                    'memory_units': k.kubes.memory_units,
                    'disk_space': k.kubes.disk_space,
                    'disk_space_units': k.kubes.disk_space_units}
            kubes[p.id].append(kube)
    return packages, kubes


def process_yaml(app):
    root = find_root(app)
    kubes_data = {};
    kube_type = root.get('kube_type', 0)
    root['kube_type'] = '$$KUBETYPE|{0}$$'.format(kube_type)
    for container in root.get('containers', []):
        kubes = container.get('kubes', 1)
        kubes_data[container.get('image', '')] = kubes
        container['kubes'] = '$$KUBES|{0}:{1}$$'.format(container['image'], kubes)
    return yaml.safe_dump(app, default_flow_style=False), kube_type, kubes_data