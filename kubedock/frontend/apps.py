import yaml
import json

from flask import Blueprint, render_template
from ..utils import APIError
from ..kapi.predefined_apps import PredefinedApps
from ..billing.models import Package

apps = Blueprint('apps', __name__, url_prefix='/apps')

class AppParseError(Exception):
    pass

@apps.route('/<app_hash>', methods=['GET'], strict_slashes=False)
def index(app_hash):
    try:
        app = PredefinedApps().get_by_qualifier(app_hash)
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
        return render_template('apps/index.html',
                               name=name,
                               packages=packages,
                               kubes=json.dumps(kubes),
                               containers=containers)
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