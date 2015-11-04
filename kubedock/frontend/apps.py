import json
import re
import yaml
import random
import string
import hashlib

from flask import Blueprint, request, render_template
from ..utils import APIError
from ..kapi.predefined_apps import PredefinedApps
from ..billing.models import Package, Kube
from ..system_settings.models import SystemSettings
from ..billing.models import Kube
from ..kapi import predefined_apps as kapi_papps


apps = Blueprint('apps', __name__, url_prefix='/apps')

@apps.route('/<app_hash>', methods=['GET'], strict_slashes=False)
def index(app_hash):
    package_id = int(request.args.get('pkgid', '0'))
    try:
        app = PredefinedApps().get_by_qualifier(app_hash)
        billing_url = SystemSettings.read_setting('billing_apps_link')
        if billing_url is None:
            billing_url = ''
        mutables = {}
        kubes = []
        name = app.get('name', 'app')
        template = app.get('template', '')
        fields = find_custom(template)
        jfields = json.dumps(fields)
        packages, kubes_data = get_packages()
        if not package_exists(packages, package_id):
            package_id = 0
        template, kube_type, pre_desc = get_defaults(template, mutables, kubes)
        has_simple = True if [v for v in fields.values() if v.get('hashsum') in mutables] else False

        return render_template('apps/index.html',
            name=name, jfields=jfields, billing_url=billing_url, packages=packages,
            template=template, jmutables=json.dumps(mutables), kubes=json.dumps(kubes),
            mutables=mutables, fields=fields, kube_type=kube_type, jpackages=json.dumps(packages),
            jkubes_data=json.dumps(kubes_data), kubes_data=kubes_data, package_id=package_id,
            pre_desc=pre_desc, has_simple=has_simple)

    except (yaml.scanner.ScannerError, yaml.parser.ParserError):
        return render_template('apps/error.html', message='Could not parse App config'), 500

    except kapi_papps.AppParseError:
        return render_template('apps/error.html', message='Unsupported App'), 500

    except APIError:
        return render_template('apps/error.html', message='No such application'), 404


def package_exists(packages, package_id):
    for package in packages:
        if package_id == package['id']:
            return True
    return False


def find_root(app):
    try:
        if app['kind'] == 'ReplicationController':
            return app['spec']['template']['spec']
        if app['kind'] == 'Pod':
            return app['spec']
        raise kapi_papps.AppParseError
    except (TypeError, KeyError):
        raise kapi_papps.AppParseError


def get_packages():
    packages = []
    kubes = {}
    for p in Package.query.all():
        packages.append({'id': p.id, 'name': p.name, 'prefix': p.prefix, 'currency': p.currency})
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


def get_value(value):
    varname, dflt, _ = kapi_papps.get_value(value)
    hs = None
    if varname is not None:
        hs = hashlib.sha1(str(value)).hexdigest()
    return dflt, hs


def get_defaults(app, mutables, kubes,
                 default_kube_type=None,
                 default_kubes_num=1):
    if default_kube_type is None:
        default_kube_type = Kube.get_default_kube_type()
    yml = yaml.safe_load(app)
    if not isinstance(yml, (dict, list)):
        raise kapi_papps.AppParseError
    root = find_root(yml)
    kube_type = None
    pre_desc = yml.get('metadata', {}).get('preDescription')

    if 'kube_type' not in root:
        root['kube_type'] = default_kube_type
        kube_type = default_kube_type
    else:
        kube_type, hashsum = get_value(root['kube_type'])
        if hashsum is not None:
            mutables[hashsum] = {'type': 'kube_type'}

    for container in root.get('containers', []):
        if 'kubes' not in container:
            container['kubes'] = default_kubes_num
            kubes.append(default_kubes_num)
        else:
            kube_num, hashsum = get_value(container['kubes'])
            if hashsum is None:
                kubes.append(kube_num)
            else:
                mutables[hashsum] = {'type': 'kube'}
    return yaml.safe_dump(yml, default_flow_style=False), kube_type, pre_desc


def generate(length=8):
    return ''.join(
        random.choice(string.lowercase+string.digits+string.uppercase)
            for i in range(length))


def find_custom(text):
    custom = kapi_papps.find_custom_vars(text)
    data = {}
    for item in custom:
        _, value, title = kapi_papps.get_value(item, strict=True)
        if value == 'autogen':
            value = generate()
        data[item] = {
            'title': title, 'value': value,
            'hashsum': hashlib.sha1(item).hexdigest()}
    return data
