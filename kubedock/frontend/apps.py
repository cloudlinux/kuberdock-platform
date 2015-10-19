import json
import re
import yaml
import random
import string
import hashlib

from flask import Blueprint, request, render_template
from ..utils import APIError
from ..kapi.predefined_apps import PredefinedApps
from ..billing.models import Package
from ..system_settings.models import SystemSettings


apps = Blueprint('apps', __name__, url_prefix='/apps')

class AppParseError(Exception):
    pass

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
        template, kube_type = set_defaults(template, mutables, kubes)

        return render_template('apps/index.html',
            name=name, jfields=jfields, billing_url=billing_url, packages=packages,
            template=template, jmutables=json.dumps(mutables), kubes=json.dumps(kubes),
            mutables=mutables, fields=fields, kube_type=kube_type, jpackages=json.dumps(packages),
            jkubes_data=json.dumps(kubes_data), kubes_data=kubes_data, package_id=package_id)

    except yaml.scanner.ScannerError:
        return render_template('apps/error.html', message='Could not parse App config'), 500

    except AppParseError:
        return render_template('apps/error.html', message='Unsupported App'), 500

    except APIError:
        return render_template('apps/error.html', message='No such application'), 404


def package_exists(packages, package_id):
    for package in packages:
        if package_id == package['id']:
            return True
    return False


def find_root(app):
    if app['kind'] == 'ReplicationController':
        return app['spec']['template']['spec']
    elif app['kind'] == 'Pod':
        return app['spec']
    else:
        raise AppParseError


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


def get_value(value,  patt=re.compile(r"""\$([^\$]+?)\$""")):
    if not isinstance(value, basestring):
        value = str(value)
    m = patt.search(value)
    if m is None:
        return value, None
    _, dflt, title = [i.strip() for i in m.group(1).split('|')]
    return dflt[1], hashlib.sha1(value).hexdigest()


def set_defaults(app, mutables, kubes, default_kube_type=0, default_kubes_num=1):
    yml = yaml.safe_load(app)
    root = find_root(yml)
    kube_type = None

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
    return yaml.safe_dump(yml, default_flow_style=False), kube_type


def generate(length=8):
    return ''.join(
        random.choice(string.lowercase+string.digits+string.uppercase)
            for i in range(length))


def find_custom(text, length=8, patt=re.compile(r"""\$[^\$]+?\$""")):
    custom = patt.findall(text)
    data = {}
    for item in custom:
        name, default, title = [i.strip() for i in item.strip('$').split('|')]
        _, value = [i.strip() for i in default.split(':')]
        if value == 'autogen':
            value = generate()
        data[item] = {
            'title': title, 'value': value,
            'hashsum': hashlib.sha1(item).hexdigest()}
    return data
