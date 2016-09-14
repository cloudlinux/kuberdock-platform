"""Classes and utilities that handle predefined application"""
import json
import re
import yaml
import random
from collections import Mapping, Sequence
from copy import deepcopy
from numbers import Number
from string import digits, lowercase
from types import NoneType
from kubedock.billing.models import Kube, Package
from kubedock.domains.models import PodDomain
from kubedock.predefined_apps.models import PredefinedApp as PredefinedAppModel
from kubedock.exceptions import NotFound, PermissionDenied, PredefinedAppExc
from kubedock.kapi.podcollection import PodCollection
from kubedock.kd_celery import celery
from kubedock.nodes.models import Node
from kubedock.pods.models import Pod, IPPool
from kubedock.settings import KUBE_API_VERSION
from kubedock.utils import send_event_to_user
from kubedock.validation import V, predefined_app_schema
from kubedock.validation.exceptions import ValidationError
from kubedock.rbac import check_permission
from kubedock.billing import has_billing


FIELD_PARSER = re.compile(ur"""
    \$(?:
        (?P<name>[\w\-]+)
        (?:\|default:
            (?P<default>(?:[^\\\|\$]|\\[\s\S])+|)
            \|
            (?P<label>(?:[^\\\|\$]|\\[\s\S])+|)
        )?
    )?\$
""", re.X)


def check_migratability(pod, new_kube):
    if pod.kube_id == new_kube:
        return
    if pod.has_local_storage:
        raise PredefinedAppExc.AppPackageChangeImpossible(
            details={'message': 'local storage cannot migrate'})
    node_to_migrate = Node.query.filter_by(kube_id=new_kube).first()
    if node_to_migrate is None:
        raise PredefinedAppExc.AppPackageChangeImpossible(
            details={'message': 'there is no node of such kube type'})


def generate(length=8):
    """
    Generates random lowercase+digits string
    :param length: int -> default string length
    :return: string -> random string
    """
    rest = ''.join(random.sample(lowercase + digits, length-1))
    return random.choice(lowercase) + rest


@celery.task(bind=True)
def on_update_error(self, uuid, pod, owner, orig_config, orig_kube_id):
    """
    Asynchronous task error callback
    :param self: obj -> celery task object
    :param uuid: str -> uuid of the celery task
    """
    send_event_to_user(
        'notify:error', {'message': 'Could not change app package'}, owner.id)
    pod.config = orig_config
    pod.kube_id = orig_kube_id
    pod.save()
    pod_collection = PodCollection(owner)
    pod_collection.update(pod.id,
                          {'command': 'start', 'commandOptions': {}})


@celery.task(bind=True, ignore_result=True)
def update_plan_async(self, pod, owner):
    """
    Asynchronous pod updater
    :param self: obj -> celery task object
    """
    PredefinedApp._update_and_restart(pod, owner)


class PredefinedApp(object):
    """Object that handles all predefined app related routines"""

    FIELDS = ('id', 'name', 'template', 'origin', 'qualifier', 'created',
              'modified', 'plans')

    def __init__(self, **kw):
        required_attrs = set(['name', 'template'])
        if required_attrs.intersection(kw.keys()) != required_attrs:
            raise ValidationError('PredefinedApp instance requires at '
                                  'least "name" and "template" fields')

        for k, v in kw.items():
            super(PredefinedApp, self).__setattr__(k, v)

        self.throw = True
        self._entities = {}
        self._entities_by_uid = {}
        self._used_entities = {}
        self._used_entities_by_plans = {}
        self._filled_templates = {}

    @classmethod
    def all(cls, as_dict=False):
        """
        Class method which returns all predefined applications
        :param as_dict bool -> if True returns PA objects as dicts
        :return: list of PA objects or dicts
        """
        query = PredefinedAppModel.query.order_by(PredefinedAppModel.id)
        if as_dict:
            return [app.to_dict() for app in query.all()]
        apps = []
        for dbapp in query.all():
            apps.append(cls(**dbapp.to_dict()))
        return apps

    def to_dict(self, with_plans=False):
        """Instance method that returns PA object as dict"""
        data = dict((k, v) for k, v in vars(self).items() if k in self.FIELDS)
        if with_plans:
            data['plans'] = self.get_plans()
        return data

    @classmethod
    def create(cls, **kw):
        """
        Class method which creates PA instance, saves it and returns it
        Gets key-value pairs
        :return: object -> PA instance
        """
        dbapp = PredefinedAppModel(**kw)
        dbapp.save()
        return cls(**dbapp.to_dict())

    @classmethod
    def delete(cls, id):
        """
        Class method which deletes PA
        :param id: int -> PA database ID
        """
        app = PredefinedAppModel.query.get(id)
        if app is not None:
            app.delete()

    @classmethod
    def get(cls, id):
        """
        Class method to return instance by ID
        :param id: int -> PA database ID
        :return: PA intance
        """
        dbapp = PredefinedAppModel.query.get(id)
        if dbapp is None:
            raise PredefinedAppExc.NoSuchPredefinedApp
        return cls(**dbapp.to_dict())

    @classmethod
    def get_by_qualifier(cls, qualifier):
        """
        Class method to return instance by qualifier (hash)
        :param qualifier: string -> PA database qualifier (unique string)
        :return: PA intance
        """
        dbapp = PredefinedAppModel.query.filter_by(qualifier=qualifier).first()
        if dbapp is None:
            raise PredefinedAppExc.NoSuchPredefinedApp
        return cls(**dbapp.to_dict())

    def get_filled_template_for_plan(self, plan_id, values, as_yaml=False,
                                     with_id=True, user=None):
        """
        Returns template filled with values for particular plan
        :param plan_id: int -> plan index in appPackage list
        :param values: dict -> values for filling templates
        :param as_yaml: bool -> if True returns template as YAML
        :param with_id: bool -> if True add template_id to pod config
        :param user: obj -> user to take ownership of the pod
        :return: dict or YAML document(string)
        """
        self._check_permissions(user)
        filled = self._get_filled_template_for_plan(plan_id, values)
        self._expand_plans(filled, with_info=False)
        plans = filled.setdefault('kuberdock', {}).pop('appPackages', [{}])
        if with_id:
            filled['kuberdock']['kuberdock_template_id'] = self.id
        if as_yaml:
            return self._dump_yaml(self._apply_package(filled, plans[0]))
        return self._apply_package(filled, plans[0])

    def get_filled_template_for_plan_by_name(self, name, values, as_yaml=False,
                                             with_id=True, user=None):
        """
        Wrapper helper function that finds plan by name and calls
        'get_filled_template_for_plan' for found plan
        :param name: string -> plan name (e.g. 'S')
        :param values: dict -> values for filling templates
        :param as_yaml: bool -> if True returns template as YAML
        :param with_id: bool -> if True add template_id to pod config
        :param user: obj -> user to take ownership of the pod
        :return: dict or YAML document(string)
        """
        idx = self._get_plan_by_name(name, index_only=True)
        return self.get_filled_template_for_plan(idx, values, as_yaml, with_id,
                                                 user)

    def get_loaded_plans(self):
        """
        Helper instance method returning appPackages structure
        :return: list -> list of dicts
        """
        loaded = self._get_loaded_template()
        return loaded.get('kuberdock', {}).get('appPackages', [])

    def get_plan(self, index):
        """
        Returns predefined application plan by index
        :param index: int -> plan index
        :return: dict
        """
        try:
            return self.get_plans()[index]
        except (IndexError, TypeError):
            raise PredefinedAppExc.NoSuchAppPackage

    def get_plans(self):
        """
        Returns all predefined application plans
        :return: list -> list of plans
        """
        return self._get_expanded_plans()

    def get_predescription(self):
        """
        Helper instance method which returns predescription key from PA dict
        :return: string
        """
        filled = self._get_filled_template()
        return filled.get('kuberdock', {}).get('preDescription')

    def get_postdescription(self):
        """Currently stub"""
        pass

    def get_used_plan_entities(self, plan_id):
        """
        Method which returns entities for particular plan
        :param plan_id: int -> plan index
        :return: dict -> PA entities by names
        """
        if plan_id in self._used_entities_by_plans:
            return self._used_entities_by_plans[plan_id]
        self._get_filled_template_for_plan(plan_id)
        return self._used_entities_by_plans[plan_id]

    def is_template_for(self, derived):
        """
        Fills own template objects and compares it to already filled template
        :param derived: dict -> template to be compared
        :return: bool
        """
        loaded = self._get_loaded_template()
        derived = deepcopy(derived)

        kuberdock = derived.get('kuberdock')
        kuberdock.pop('kuberdock_template_id', None)

        if (not isinstance(kuberdock, Mapping) or
                not isinstance(kuberdock.get('appPackage'), Mapping)):
            return False
        packages_by_name = dict((pkg['name'], pkg) for
                                pkg in loaded['kuberdock']['appPackages'])
        package = kuberdock.get('appPackage')
        package = packages_by_name.get(package.get('name'))
        if package is None:
            return False
        self._apply_package(loaded, package)
        entities_set = set(self._entities.values())
        any_entity_regex = re.compile('(?:%USER_DOMAIN%|{0})'.format(
            '|'.join(entity.uid for entity in entities_set)))
        stack = [(loaded, derived)]
        while stack:
            left, right = stack.pop()
            if left == right:
                continue
            elif all([isinstance(i, Mapping) for i in (left, right)]):
                for key, val in left.items():
                    if key not in right:
                        return False
                    stack.append((val, right.pop(key)))
                if right:
                    return False
            elif all([isinstance(i, basestring) for i in (left, right)]):
                if not re.match(
                        any_entity_regex.sub('.*', re.escape(left)),
                        right):
                    return False
            elif all([isinstance(i, Sequence) for i in (left, right)]):  # list
                if len(left) != len(right):
                    return False
                stack.extend(zip(left, right))
            elif (left in entities_set and
                    isinstance(right, (Number, basestring, NoneType))):
                if not hasattr(left, 'value'):
                    left.value = right
                elif left.value != right:
                    return False
            else:
                return False
        return True

    def set_package(self, package_id):
        """
        Helper instance method that sets object package
        :param package_id: int -> package ID
        """
        if isinstance(package_id, basestring) and not package_id.isdigit():
            raise ValidationError('Incorrect package ID provided')
        package = Package.query.get(package_id)
        if package is not None:
            self._package = package

    @classmethod
    def update(cls, id, **kw):
        """
        Class method that updates one or more PA object fields
        :param id: int -> PA database ID
        :return: object -> PA instance
        """
        app = PredefinedAppModel.query.get(id)
        if app is None:
            return
        allowed_fields = set(cls.FIELDS) - {'id', 'created', 'modified'}
        fields_to_update = allowed_fields & set(kw)
        for attr in fields_to_update:
            setattr(app, attr, kw[attr])
        app.save()
        return cls(**app.to_dict())

    @classmethod
    def update_pod_to_plan(cls, pod_id, plan_id, values=None, async=True,
                           user=None):
        """
        Class method that updates predefined app pod to a particular plan
        :param pod_id: string -> uuid, pod (database) ID
        :param plan_id: int -> plan ID
        :param values: dict -> values to fill defaults
        :param async: bool -> not to wait for result if async
        :param user: obj -> user on behalf of whom action is taken
        """
        app, pod = cls._get_instance_from_pod(pod_id)
        cls._check_permissions(user, pod)
        filled = app.get_filled_template_for_plan(plan_id, values)
        app._update_pod_config(pod, filled, async)
        return app.get_plan(plan_id)

    @classmethod
    def update_pod_to_plan_by_name(cls, pod_id, plan_name, values=None,
                                   async=True, user=None):
        """
        Class method that updates predefined app pod to a particular plan
        :param pod_id: string -> uuid, pod (database) ID
        :param plan_name: string -> plan name
        :param values: dict -> values to fill defaults
        :param async: bool -> not to wait for result if async
        :param user: obj -> user on behalf of whom action is taken
        """
        app, pod = cls._get_instance_from_pod(pod_id)
        cls._check_permissions(user, pod)
        filled = app.get_filled_template_for_plan_by_name(plan_name, values)
        app._update_pod_config(pod, filled, async)
        return app.get_plan(app._get_plan_by_name(plan_name, index_only=True))

    @staticmethod
    def _check_permissions(user, pod=None):
        """
        Makes some checks to make sure user is allowed requested action
        An exception is expected to be raised when check failed
        :param user: obj -> usually current user object
        :param
        """
        if user is None:
            return
        if pod is not None:
            check_permission('own', 'pods', user=pod.owner).check()
            if pod.owner == user:
                check_permission('edit', 'pods').check()
            else:
                check_permission('edit_non_owned', 'pods').check()

        if user.is_administrator():
            return
        if not has_billing():
            return
        if not user.fix_price:
            return
        raise PermissionDenied

    @staticmethod
    def _dump_yaml(applied):
        """
        Dumps dict correctly processing multiline pre & postDescription string
        :param applied: dict -> filled config ready to be converted to yaml
        :return: str -> yaml config
        """

        def str_presenter(dumper, data):
            # check for multiline strings
            if len(data.splitlines()) == 1 and data[-1] == '\n':
                return dumper.represent_scalar(
                    'tag:yaml.org,2002:str', data, style='>')
            if len(data.splitlines()) > 1:
                return dumper.represent_scalar(
                    'tag:yaml.org,2002:str', data, style='|')
            return dumper.represent_scalar(
                'tag:yaml.org,2002:str', data.strip())

        yaml.add_representer(unicode, str_presenter)
        yaml.add_representer(str, str_presenter)
        return yaml.dump(applied, default_flow_style=False, width=1000)

    @staticmethod
    def _update_IPs(pod, root, pod_config):
        """
        Toggles pod publicIP
        :param pod: obj -> pod to be processed
        :param root: dict -> modified pod config spec
        :param pod_config: dict -> current pod config spec
        """
        wanted = PodCollection.needs_public_ip(root)
        curr_IP = pod_config.get('public_ip')
        if wanted and curr_IP is None:
            if not IPPool.has_public_ips():
                raise PredefinedAppExc.AppPackageChangeImpossible(
                    details={'message': 'Unable to pick up public IP'})
            PodCollection._prepare_for_public_address(pod, root)
            pod_config['public_ip'] = root.get('public_ip')
        elif not wanted and curr_IP is not None:
            ip = pod_config.pop('public_ip', None)
            PodCollection._remove_public_ip(pod_id=pod.id, ip=ip)

    @staticmethod
    def _update_and_restart(pod, owner):
        pod_collection = PodCollection(owner)
        pod_ = pod_collection._get_by_id(pod.id)
        pod_collection._stop_pod(pod_, raise_=False, block=True)
        pod.save()
        pod_collection.update(pod.id,
                              {'command': 'start', 'commandOptions': {}})

    def _update_pod_config(self, pod, new_config, async=True):
        """
        Updates existing pod config to switch to new plan
        :param pod: obj -> pod object retrieved from DB
        :param new_config: dict -> filled config with applied values
        """
        root = self._get_template_spec(new_config)
        plan = new_config['kuberdock']['appPackage']
        kube_id = plan['kubeType']
        check_migratability(pod, kube_id)
        domain = plan.get('baseDomain')
        pod_domain = PodDomain.query.filter(
            PodDomain.pod_id == pod.id).first()
        old_domain = pod_domain and pod_domain.base_domain.name
        if domain != old_domain:
            raise PredefinedAppExc.AppPackageChangeImpossible(details={
                'message': 'public access type cannot be changed'})

        orig_config = pod.config
        orig_kube_id = pod.kube_id
        pod_config = json.loads(orig_config)
        if pod_config.get('forbidSwitchingAppPackage'):
            raise PredefinedAppExc.AppPackageChangeImpossible(details={
                'message': pod_config.get('forbidSwitchingAppPackage')})

        self._update_kubes(root, pod_config)
        self._update_IPs(pod, root, pod_config)
        try:
            pod.kube_id = kube_id
            pod.template_plan_name = plan['name']
            pod.config = json.dumps(pod_config)
            if async:
                update_plan_async.apply_async(
                    args=[pod, pod.owner],
                    link_error=on_update_error.s(
                        pod, pod.owner, orig_config, orig_kube_id))
                return
            self._update_and_restart(pod, pod.owner)

        except Exception:
            pod.config = orig_config
            pod.kube_id = orig_kube_id
            pod.save()
            pod_collection = PodCollection(pod.owner)
            pod_collection.update(pod.id,
                                  {'command': 'start', 'commandOptions': {}})
            raise

    @classmethod
    def validate(cls, template):
        """
        Class helper method which fills arbitrary template and sees
        if an exceptions raised
        :param template: string -> YAML document
        """
        app = cls(name=generate(), template=template)
        app._validate_template()

    @staticmethod
    def _update_kubes(left, right):
        """
        Updates right list kubes amounts with left list values
        :param left: list -> list to take values from
        :param right: list -> list to apply values to
        """
        kubes_by_container = {}
        for container in left.get('containers', []):
            kubes_by_container[container.get('name')] = container.get('kubes')

        for container in right.get('containers', []):
            if container.get('name') in kubes_by_container:
                container['kubes'] = kubes_by_container[container.get('name')]

    @staticmethod
    def _update_volumes(left, right):
        """
        Updates right list kubes amounts with left list values
        :param left: list -> list to take values from
        :param right: list -> list to apply values to
        """
        pd_by_volname = {}
        for pd in left.get('persistentDisks', []):
            pd_by_volname[pd.get('name')] = pd.get('pdSize')
        for vol in right.get('volumes', []):
            if vol.get('persistentDisk'):
                vol_size = pd_by_volname.get(vol.get('name'), 1)
                vol['persistentDisk']['pdSize'] = vol_size

    def _apply_package(self, tpl, plan):
        """
        Removes appPackages structure from PA object and applies a particular
        plan settings for whole PA object
        :param tpl: dict -> template object
        :param plan: dict -> plan object
        :return: dict -> filled template object
        """
        plan_pod, spec = plan['pods'][0], self._get_template_spec(tpl)
        kuberdock = tpl.setdefault('kuberdock', {})
        kuberdock.pop('appPackages', None)

        kuberdock['appPackage'] = {
            'name': plan.get('name'),
            'goodFor': plan.get('goodFor', ''),
            'kubeType': plan_pod.get('kubeType')}

        self._update_kubes(plan_pod, spec)
        self._update_volumes(plan_pod, spec)

        if plan.get('publicIP') is False and self._has_public_ports():
            for container in spec.get('containers', []):
                for port in container.get('ports', []):
                    port['isPublic'] = False
        if plan.get('baseDomain'):
            kuberdock['appPackage']['baseDomain'] = plan.get('baseDomain')

        if plan.get('packagePostDescription'):
            kuberdock['postDescription'] += \
                '\n{0}'.format(plan['packagePostDescription'])
        return tpl

    def _calculate_info(self, plan):
        """
        Helper instance method completes preparing for plans for displaying
        in web-interface
        :param plan: dict -> plan object
        """
        if type(plan.get('info')) is dict:
            return
        plan['info'] = {'totalKubes': 0, 'totalPD': 0}
        plan['info']['publicIP'] = (plan.get('publicIP', True) and
                                    self._has_public_ports() and
                                    not plan.get('baseDomain'))
        for pod in plan.get('pods', []):
            plan['info']['totalKubes'] += reduce(
                lambda t, x: t + int(x['kubes']), pod['containers'], 0)
            plan['info']['totalPD'] += reduce(
                lambda t, x: t + int(x['pdSize']), pod['persistentDisks'], 0)
            # TODO: we have now only one pod but what if we have more?
            plan['info']['kubeType'] = self._get_kube_by_id(
                pod.get('kubeType', Kube.get_default_kube_type()))
        if 'kubeType' not in plan['info']:
            plan['info']['kubeType'] = self._get_kube_by_id(
                Kube.get_default_kube_type())
        kt = plan['info']['kubeType']
        kd_package = self._get_package()
        plan['info']['cpu'] = plan['info']['totalKubes'] * kt['cpu']
        plan['info']['memory'] = plan['info']['totalKubes'] * kt['memory']
        plan['info']['diskSpace'] = (plan['info']['totalKubes'] *
                                     kt['disk_space'])
        plan['info']['price'] = \
            plan['info']['totalKubes'] * kt.get('price', 0) + \
            kd_package.price_pstorage * plan['info']['totalPD'] + \
            kd_package.price_ip * int(plan['info']['publicIP'])
        for attr in ('period', 'prefix', 'suffix'):
            plan['info'][attr] = getattr(kd_package, attr, None)

    @staticmethod
    def _check_names(spec, plans, err_collection, err_name):
        """
        Helper method to compare spec entities names with plan ones
        :param spec: list -> spec entities
        :param plans: list -> plan entities
        :param err_collection: string -> just name to name collection on error
        :param err_name: string -> just name to name collection item on error
        """
        used_names = set()
        names = set(item.get('name') for item in spec)
        for plan_item in plans:
            name = plan_item.get('name')
            if name not in names:
                raise PredefinedAppExc.InvalidTemplate(
                    '{0} "{1}" not found in pod "{2}"'.format(
                        err_collection.capitalize(), name, err_name))
            if name in used_names:
                raise PredefinedAppExc.InvalidTemplate(
                    'Duplicate {0} name in appPackage'.format(err_collection))
            used_names.add(name)

    @staticmethod
    def _equalize_containers(spec, pod):
        """
        Helper method comparing plan containers to spec containers
        :param spec: dict -> PA spec object
        :param pod: dict -> PA plan object
        """
        spec_names = [c.get('name') for c in spec.get('containers', [])]
        for container in pod['containers']:
            if type(container.get('kubes')) is not int:
                container['kubes'] = 1
            if container['name'] in spec_names:
                spec_names.remove(container['name'])
        pod['containers'].extend([{'name': n, 'kubes': 1} for n in spec_names])

    def _expand_plans(self, filled, with_info=True):
        """
        Helper method which prepares plans for web-interface
        """
        plans = self._get_plans(filled)
        for plan in plans:
            plan.setdefault('goodFor', '')
            plan['publicIP'] = plan.get('publicIP') is not False
            if type(plan.get('pods')) is not list:
                plan['pods'] = [{}]
            for pod in plan['pods']:
                if pod.get('kubeType') is None:
                    pod['kubeType'] = Kube.get_default_kube_type()
                pod['name'] = pod.get('metadata', {}).get('name')
                for attr in 'containers', 'persistentDisks':
                    if type(pod.get(attr)) is not list:
                        pod[attr] = []
                spec = self._get_template_spec(filled)
                self._equalize_containers(spec, pod)
                self._fill_persistent_disks(spec, pod)
            if with_info:
                self._calculate_info(plan)
        return plans

    def _get_expanded_plans(self):
        """
        Wrapper method that returns prepared plans for web-interface
        :return: list -> list of dicts
        """
        if hasattr(self, '_extended_plans'):
            return self._extended_plans
        filled = self._get_filled_template()
        self._extended_plans = self._expand_plans(deepcopy(filled))
        return self._extended_plans

    def _get_filled_template(self):
        """
        Wrapper method that returns template filled with defaults
        :return: dict
        """
        if hasattr(self, '_filled_template'):
            return self._filled_template
        self._filled_template = self._fill_template()
        return self._filled_template

    def _get_filled_template_for_plan(self, plan_id, values=None):
        """
        Wrapper method that returns filled template for a particular plan
        :param plan_id: int -> plan index
        :param values: dict -> values to fill template or None
        :return:
        """
        if values is not None:
            return self._fill_template(
                loaded=self._squeeze_plans(plan_id), values=values)
        if plan_id in self._filled_templates:
            return self._filled_templates[plan_id]
        if plan_id not in self._used_entities_by_plans:
            self._used_entities_by_plans[plan_id] = {}
        copied = self._squeeze_plans(plan_id)
        self._filled_templates[plan_id] = self._fill_template(
            loaded=copied,
            used_entities=self._used_entities_by_plans[plan_id])
        return self._filled_templates[plan_id]

    def _get_kube_by_id(self, kube_id):
        """
        Returns kube object by kube ID and merges some external values into
        :param kube_id: int -> kube id
        :return: obj -> kube object
        """
        if hasattr(self, '_package_kubes'):
            return self._package_kubes.get(kube_id)
        self._package_kubes = {}
        package = self._get_package()
        for k in package.kubes:
            kube_data = k.kube.to_dict()
            kube_data['price'] = k.kube_price
            self._package_kubes[k.kube_id] = kube_data
        return self._package_kubes.get(kube_id)

    def _get_loaded_template(self):
        """
        Converts template document to dict replacing entities UIDs with objects
        :return: dict -> loaded YAML document
        """
        if hasattr(self, '_loaded_template'):
            return self._loaded_template
        preprocessed = self._get_preprocessed_template()

        class CustomLoader(yaml.SafeLoader):
            pass

        class TemplateObject(yaml.YAMLObject):
            yaml_tag = '!kd'
            yaml_loader = CustomLoader

            @classmethod
            def from_yaml(cls, loader, node):
                return self._entities_by_uid[loader.construct_scalar(node)]

        patt = re.compile(r'^(?:{0})$'.format('|'.join(self._entities_by_uid)))
        CustomLoader.add_implicit_resolver('!kd', patt, None)
        try:
            self._loaded_template = yaml.load(preprocessed,
                                              Loader=CustomLoader)
        except (yaml.scanner.ScannerError, yaml.parser.ParserError):
            raise PredefinedAppExc.UnparseableTemplate
        return self._loaded_template

    def _get_package(self, template=None):
        """
        Helper method that resolves and returns KD package
        :param template: dict
        """
        if template is None:
            if hasattr(self, '_package'):
                return self._package
            if hasattr(self, '_loaded_template'):
                template = self._loaded_template
            else:
                try:
                    template = yaml.safe_load(self.template)
                except (yaml.scanner.ScannerError, yaml.parser.ParserError):
                    raise PredefinedAppExc.UnparseableTemplate
        package_id = template.get('kuberdock', {}).get('packageID')
        package = self._get_package_by_id(package_id)
        if template is None:
            self._package = package
        return package

    @staticmethod
    def _get_package_by_id(package_id):
        """
        Helper method to avoid excessive logic complexity
        :param package_id: int -> KD package id
        """
        if package_id is None:
            return Package.get_default()
        package = Package.query.get(package_id)
        if package is None:
            return Package.get_default()
        return package

    def _get_plans(self, template=None, validate=False):
        """
        Helper method that returns appPackages structure from template object
        and makes preliminary checks for validity
        :param template: dict -> template object or None
        :param
        """
        if template is None:
            template = yaml.safe_load(self.template)
        try:
            plans = template['kuberdock']['appPackages']
        except KeyError:
            raise PredefinedAppExc.InvalidTemplate
        if validate:
            if (len(plans) != 1 and
                    len([p for p in plans if p.get('recommended')]) != 1):
                raise PredefinedAppExc.InvalidTemplate(
                    'Exactly one package must be "recommended"')
        return plans

    def _get_plan_by_name(self, name, index_only=False):
        """
        Returns either plan or plan index by name
        :param name: str -> plan name to be resolved (e.g. 'S')
        :param index_only: bool -> set return value to index instead of plan
        :return: int if index_only=True otherwise dict
        """
        plans = self._get_plans()
        for idx, plan in enumerate(plans):
            if plan['name'] == name:
                if index_only:
                    return idx
                return plan
        raise PredefinedAppExc.NoSuchAppPackage

    def _get_preprocessed_template(self):
        """
        Method that populates entities replacing template ones with random UIDs
        :return: string -> processed yaml document
        """
        def processor(m):
            full_match = m.group()
            if full_match == '$$':
                return '$'
            grps = m.groupdict()
            name, default, label = map(grps.get, ['name', 'default', 'label'])
            if name in self._entities:
                entity = self._entities[name]
                if full_match != '${0}$'.format(name) and not entity.defined:
                    entity.set_up(default, label)
            else:
                start = m.start()
                line = m.string[:start].count('\n') + 1
                col = len(m.string[:start].split('\n')[-1])
                entity = self.TemplateField(name, default, label, line, col)
                self._entities[name] = entity
                self._entities_by_uid[entity.uid] = entity
            return entity.uid

        if hasattr(self, '_preprocessed_template'):
            return self._preprocessed_template
        preprocessed = FIELD_PARSER.sub(processor, self.template)
        if self.throw:
            # check for $VAR$ without full definition ($VAR|default:...$)
            for entity in self._entities.itervalues():
                if not entity.defined:
                    raise PredefinedAppExc.InvalidTemplate("""
                        'Variable {0} not defined [line:{1}, col:{2}].
                        At least one occurence of full form like
                        ${0}|default:...$ is expected.
                        """.format(entity.name, entity.line, entity.col,
                                   entity.name))

        self._preprocessed_template = preprocessed
        return self._preprocessed_template

    @classmethod
    def _get_instance_from_pod(cls, pod_id):
        """
        Helper method that returns instance by pod_id if pod created from PA
        :param pod_id: str -> pod UUID
        :return: tuple (obj, dict) -> PredefinedApp instance, pod config
        """
        pod = Pod.query.get(pod_id)
        if pod is None:
            raise NotFound('Pod not found')
        if pod.template_id is None:
            raise PredefinedAppExc.NotPredefinedAppPod
        return cls.get(pod.template_id), pod

    def _get_template_spec(self, tpl=None):
        """
        Helper method that returns spec root with elementary validity check
        :param tpl: dict -> template to get spec from
        :return: dict -> spec root
        """
        if tpl is None:
            tpl = self._get_filled_template()
        try:
            if tpl['kind'] == 'ReplicationController':
                return tpl['spec']['template']['spec']
            if tpl['kind'] == 'Pod':
                return tpl['spec']
        except (TypeError, KeyError):
            raise PredefinedAppExc.InvalidTemplate

    def _fill_template(self, loaded=None, used_entities=None, values=None):
        """
        Fills template with entities default values
        :param loaded: dict -> template with entities as objects
        :param entities: dict -> entities name:object dict
        :param values: dict -> values to be filled instead of defaults
        :return: dict -> template with entities replaces with default values
        """
        if values is None:
            values = {}
        if used_entities is None:
            used_entities = self._used_entities
        if loaded is None:
            loaded = self._get_loaded_template()

        def fill(target):
            if isinstance(target, self.TemplateField):
                used_entities[target.name] = target
                if target.name in values:
                    if type(values[target.name]) is not target.type:
                        return target.coerce(values[target.name])
                    return values[target.name]
                return target.default
            if isinstance(target, basestring):
                for entity in self._entities.itervalues():
                    if entity.uid in target:
                        used_entities[entity.name] = entity
                        if entity.name in values:
                            subst = values[entity.name]
                        else:
                            subst = entity.default
                        target = target.replace(entity.uid, unicode(subst))
                return target
            if isinstance(target, Mapping):
                return {fill(k): fill(v) for k, v in target.iteritems()}
            if isinstance(target, Sequence):
                return [fill(v) for v in target]
            return target
        return fill(loaded)

    @staticmethod
    def _fill_persistent_disks(spec, pod):
        """
        Helper method comparing spec persistent disk entries with plan pod ones
        and equalizing them if necessary
        :param spec: dict -> spec data
        :param pod: dict -> plan pod data
        """
        spec_names = [v.get('name') for v in spec.get('volumes', [])
                      if v.get('persistentDisk')]
        for pd in pod['persistentDisks']:
            if type(pd.get('pdSize')) is not int:
                pd['pdSize'] = 1
            if pd['name'] in spec_names:
                spec_names.remove(pd['name'])
        pod['persistentDisks'].extend(
            [{'name': n, 'pdSize': 1} for n in spec_names])

    def _has_public_ports(self):
        """
        Helper method that checks if template is expected to have exposed ports
        :return: bool
        """
        if hasattr(self, '_public_ports'):
            return self._public_ports
        pod = self._get_template_spec()
        for container in pod.get('containers', []):
            for port in container.get('ports', []):
                if port.get('isPublic') is True:
                    self._public_ports = True
                    return True
        self._public_ports = False
        return False

    def _squeeze_plans(self, plan_id):
        """
        Helper method that reduces plans list to one plan
        :param plan_id: int -> plan index
        :return: dict -> template with only one plan
        """
        copied = deepcopy(self._get_loaded_template())
        plans = copied.get('kuberdock', {}).get('appPackages')
        try:
            copied['kuberdock']['appPackages'] = [plans[plan_id]]
        except IndexError:
            raise PredefinedAppExc.NoSuchAppPackage
        return copied

    def _validate_template(self):
        """
        Method for validating PA template structure
        If template has errors an exception is expected to be raised
        """
        validator = V(allow_unknown=True)
        validated = validator.validated(self._get_filled_template(),
                                        predefined_app_schema)
        if validator.errors:
            raise PredefinedAppExc.InvalidTemplate(
                details={'schemaErrors': validator.errors})
        plans = self._get_plans(validated, validate=True)
        package = self._get_package(validated)
        available_kubes = set(kube.kube_id for kube in package.kubes)
        spec = self._get_template_spec(validated)

        for plan in plans:
            for plan_pod in plan.get('pods', []):
                if plan_pod['name'] != validated['metadata']['name']:
                    raise PredefinedAppExc.InvalidTemplate(
                        'Pod "{0}" not found in spec'.format(plan_pod['name']))

                kube_id = plan_pod.get('kubeType')
                if kube_id is not None and kube_id not in available_kubes:
                    raise PredefinedAppExc.InvalidTemplate(
                            'kube ID "{0}" not found in "{1}" package'.format(
                                kube_id, package.name))

                self._check_names(spec.get('containers', []),
                                  plan_pod.get('containers', []),
                                  'container', plan_pod['name'])
                self._check_names(spec.get('volumes', []),
                                  plan_pod.get('persistentDisks', []),
                                  'volume', plan_pod['name'])

    class TemplateField(object):
        """PA entity representation"""
        uid_length = 32

        def __init__(self, name, default, label, line=None, col=None):
            self.uid = generate(self.uid_length)
            self.defined = False
            self.name = name
            self.line, self.col = line, col    # for message on exception
            if default is not None:
                self.set_up(default.lstrip('\\'), label)

        def set_up(self, default, label):
            """
            Method which embodies PA entity
            :param default: string -> default value for entity
            :param label: string -> description label
            """
            self.label = (label or '').lstrip('\\')
            if default == 'autogen':
                self.hidden = True
                self.default = generate()
                self.type = type(self.default)
            else:
                self.type = self._resolve_type(default)
                self.hidden = False
                self.default = yaml.safe_load(default) if default else ''
            self.defined = True

        @staticmethod
        def _resolve_type(value):
            """
            Determines type of string-wrapped value
            :param value: str -> value to be resolved
            :return: type obj
            """
            if value.isdigit():
                return int
            if re.match(r'\d*?\.\d+$', value):
                return float
            if re.match(r'(?:[Tt]rue|[Ff]alse$)', value):
                return bool
            return type(value)

        def coerce(self, value):
            """
            Casts string-wrapped valued to actual type
            :param value: str -> value to be cast
            :return: value of wanted type
            """
            if self.type in (int, float, str, unicode):
                return self.type(value)
            elif self.type is bool:
                if re.match(r'[Ff]alse', value):
                    return False
                return True
            return value


def dispatch_kind(docs, template_id=None):
    if not docs or not docs[0]:     # at least one needed
        raise ValidationError("No objects found in data")
    pod, rc, service = None, None, None
    for doc in docs:
        if not isinstance(doc, dict):
            raise ValidationError('Document must describe an object, '
                                  'not just string or number')
        kind = doc.get('kind')
        if not kind:
            raise ValidationError('No object kind information')
        api_version = doc.get('apiVersion')
        if api_version != KUBE_API_VERSION:
            raise ValidationError(
                'Not supported apiVersion. Must be {0}'.format(
                    KUBE_API_VERSION))
        if kind == 'Pod':
            if pod is not None:
                raise ValidationError('Only one Pod per yaml is allowed')
            pod = doc
        elif kind == 'ReplicationController':
            if rc is not None:
                raise ValidationError(
                    'Only one ReplicationController per yaml is allowed')
            rc = doc
        elif kind == 'Service':
            if service is not None:
                raise ValidationError('Only one Service per yaml is allowed')
            service = doc
        else:
            raise ValidationError('Unsupported object kind')
    if not pod and not rc:
        raise ValidationError(
            'At least Pod or ReplicationController is needed')
    if pod and rc:
        raise ValidationError('Only one Pod or ReplicationController '
                              'is allowed but not both')
    return process_pod(pod, rc, service, template_id)


def process_pod(pod, rc, service, template_id=None):
    # TODO for now Services are useless and ignored
    if rc:
        doc = rc
        rc_spec = rc.get('spec', {})
        spec_body = rc_spec.get('template', {}).get('spec', {})
        replicas = rc_spec.get('replicas', 1)
    else:
        doc = pod
        spec_body = pod.get('spec', {})
        replicas = spec_body.get('replicas', 1)

    spec_body = deepcopy(spec_body)
    kdSection = doc.get('kuberdock', {})
    plan = kdSection.get('appPackage', {})

    new_pod = {
        'name': doc.get('metadata', {}).get('name', ''),
        'restartPolicy': spec_body.get('restartPolicy', "Always"),
        'replicas': replicas,
        'kube_type': kdSection.get(
            'kubeType', plan.get('kubeType', Kube.get_default_kube_type())),
        'postDescription': kdSection.get('postDescription'),
        'kuberdock_template_id': kdSection.get('kuberdock_template_id',
                                               template_id),
        'kuberdock_plan_name': plan.get('name'),
        'kuberdock_resolve': kdSection.get('resolve') or spec_body.get(
            'resolve', []),
    }

    if plan.get('baseDomain'):
        new_pod['domain'] = plan.get('baseDomain')

    if 'containers' in spec_body:
        containers = spec_body['containers'] or []
        for c in containers:
            for p in c.get('ports', []):
                p.pop('name', '')
                if 'podPort' in p:
                    p['hostPort'] = p.pop('podPort')
        new_pod['containers'] = containers

    if 'volumes' in spec_body:
        new_pod['volumes'] = spec_body['volumes'] or []
    return new_pod
