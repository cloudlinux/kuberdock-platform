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
        kube_type, pre_desc = get_defaults(template, mutables, kubes)
        has_simple = True if [v for v in fields.values() if v.get('hashsum') not in mutables] else False

        template = kapi_papps.unescape(template)

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
        packages.append(p.to_dict())
        for k in p.kubes:
            if p.id not in kubes:
                kubes[p.id] = []
            kube = {'id': k.kube.id,
                    'name': k.kube.name,
                    'price': k.kube_price,
                    'cpu': k.kube.cpu,
                    'cpu_units': k.kube.cpu_units,
                    'memory': k.kube.memory,
                    'memory_units': k.kube.memory_units,
                    'disk_space': k.kube.disk_space,
                    'disk_space_units': k.kube.disk_space_units}
            kubes[p.id].append(kube)
    return packages, kubes


def get_value(value):
    varname, dflt, _ = kapi_papps.get_value(value)
    hs = None
    if varname is not None:
        hs = hashlib.sha1(str(varname)).hexdigest()
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
    kuberdock = yml.get('kuberdock', {})
    kube_type = None
    pre_desc = kuberdock.get('preDescription')

    if 'kube_type' not in kuberdock:
        kuberdock['kube_type'] = default_kube_type
        kube_type = default_kube_type
    else:
        kube_type, hashsum = get_value(kuberdock['kube_type'])
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
    return kube_type, pre_desc


def generate(length=8):
    rv = ''.join(random.choice(string.lowercase+string.digits)
                 for i in range(length-1))
    return random.choice(string.lowercase) + rv


def find_custom(text):
    custom = kapi_papps.find_custom_vars(text)
    data = {}
    definitions = set()
    for item in custom:
        hidden = False
        try:
            name, value, title = kapi_papps.get_value(item, strict=True)
        except kapi_papps.AppParseError:
            name = kapi_papps.get_reused_variable_name(item)
            value = None
            title = None
        if not name:
            continue
        if value == 'autogen':
            value = generate()
            hidden = True
        if title:
            # Use only the first definition of a variable, all other
            # definitions with the same name will be reusable variables
            if name in definitions:
                title = None
                value = None
            else:
                definitions.add(name)
        data[item] = {
            'title': title, 'value': value, 'name': name, 'hidden': hidden,
            'hashsum': hashlib.sha1(name).hexdigest()}
    return data
