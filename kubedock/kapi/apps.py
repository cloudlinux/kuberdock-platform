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
from kubedock.core import db
from kubedock.domains.models import PodDomain
from kubedock.kapi.pstorage import STORAGE_CLASS
from kubedock.predefined_apps.models import \
    PredefinedApp as PredefinedAppModel, PredefinedAppTemplate
from kubedock.exceptions import NotFound, PermissionDenied, PredefinedAppExc, \
    APIError
from kubedock.kapi.podcollection import PodCollection, change_pv_size
from kubedock.kd_celery import celery
from kubedock.nodes.models import Node
from kubedock.pods.models import Pod, IPPool, PersistentDisk
from kubedock.settings import KUBE_API_VERSION
from kubedock.utils import send_event_to_user, atomic
from kubedock.validation import V, predefined_app_schema
from kubedock.validation.exceptions import ValidationError
from kubedock.validation.validators import check_new_pod_data
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
    rest = ''.join(random.sample(lowercase + digits, length - 1))
    return random.choice(lowercase) + rest


@celery.task()
def on_update_error(uuid, pod, owner, orig_config, orig_kube_id):
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


@celery.task(ignore_result=True)
def update_plan_async(*args, **kwargs):
    """
    Asynchronous pod updater
    :param self: obj -> celery task object
    """
    PredefinedApp._update_and_restart(*args, **kwargs)


class PredefinedApp(object):
    """Object that handles all predefined app template related routines"""

    FIELDS = ('id', 'name', 'template', 'origin', 'qualifier', 'created',
              'modified', 'plans', 'activeVersionID')

    FIELD_VERSION = ('active', 'switchingPackagesAllowed')

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
        query = PredefinedAppModel.query.order_by(PredefinedAppModel.id) \
            .filter(PredefinedAppModel.is_deleted.isnot(True))
        if as_dict:
            return [app.to_dict(exclude=('templates',)) for app in query.all()]
        apps = []
        for dbapp in query.all():
            apps.append(cls(**dbapp.to_dict(exclude=('templates',))))
        return apps

    def to_dict(self, with_plans=False):
        """Instance method that returns PA object as dict"""
        data = dict((k, v) for k, v in vars(self).items()
                    if k in self.FIELDS + self.FIELD_VERSION)

        if with_plans:
            data['plans'] = self.get_plans()
        return data

    @classmethod
    @atomic()
    def create(cls, **kw):
        """
        Class method which creates PA instance, saves it and returns it
        Gets key-value pairs
        :return: object -> PA instance
        """
        dbapp = PredefinedAppModel(**kw)
        db.session.flush()
        return cls(**dbapp.to_dict())

    @classmethod
    @atomic()
    def delete(cls, id_, version_id=None):
        """
        Class method which deletes PA
        :param id_: int -> PA database ID
        :param version_id: int -> PA version id
        """
        app = PredefinedAppModel.query\
            .filter_by(is_deleted=False, id=id_).first()
        if app is None:
            raise PredefinedAppExc.NoSuchPredefinedApp
        if version_id:
            app_template = app.templates\
                .filter_by(is_deleted=False, id=version_id).first()
            if not app_template:
                raise PredefinedAppExc.NoSuchPredefinedAppVersion
            if app_template.active:
                raise PredefinedAppExc.ActiveVersionNotRemovable()
            app_template.is_deleted = True
            if app_template.active:
                app_template.active = False
                # find new template for active
                new_active_template = app.templates\
                    .filter_by(is_deleted=False)\
                    .order_by(PredefinedAppTemplate.id.desc()).first()
                if new_active_template:
                    new_active_template.active = True
                    db.session.flush()
            db.session.flush()

        else:
            app.is_deleted = True
            db.session.flush()

    @classmethod
    def get(cls, app_id, version_id=None):
        """
        Class method to return instance by ID
        :param app_id: int -> PA database ID
        :return: PA intance
        """
        dbapp = PredefinedAppModel.query\
            .filter_by(is_deleted=False, id=app_id).first()
        if dbapp is None:
            raise PredefinedAppExc.NoSuchPredefinedApp
        if version_id is not None:
            dbapp.select_version(version_id)
        return cls(**dbapp.to_dict())

    @classmethod
    def get_by_qualifier(cls, qualifier):
        """
        Class method to return instance by qualifier (hash)
        :param qualifier: string -> PA database qualifier (unique string)
        :return: PA intance
        """
        dbapp = PredefinedAppModel.query\
            .filter_by(qualifier=qualifier).first()
        if dbapp is None:
            raise PredefinedAppExc.NoSuchPredefinedApp
        return cls(**dbapp.to_dict())

    def get_filled_template_for_plan(self, plan_id, values, as_yaml=False,
                                     with_id=True):
        """
        Returns template filled with values for particular plan
        :param plan_id: int -> plan index in appPackage list
        :param values: dict -> values for filling templates
        :param as_yaml: bool -> if True returns template as YAML
        :param with_id: bool -> if True add template_id to pod config
        :return: dict or YAML document(string)
        """
        filled = self._get_filled_template_for_plan(plan_id, values)
        self._expand_plans(filled, with_info=False)
        plans = filled.setdefault('kuberdock', {}).pop('appPackages', [{}])
        if with_id:
            filled['kuberdock']['kuberdock_template_id'] = self.id
        if as_yaml:
            return self._dump_yaml(self._apply_package(filled, plans[0]))
        return self._apply_package(filled, plans[0])

    def get_filled_template_for_plan_by_name(self, name, values, as_yaml=False,
                                             with_id=True):
        """
        Wrapper helper function that finds plan by name and calls
        'get_filled_template_for_plan' for found plan
        :param name: string -> plan name (e.g. 'S')
        :param values: dict -> values for filling templates
        :param as_yaml: bool -> if True returns template as YAML
        :param with_id: bool -> if True add template_id to pod config
        :return: dict or YAML document(string)
        """
        idx = self.get_plan_by_name(name, index_only=True)
        return self.get_filled_template_for_plan(idx, values, as_yaml, with_id)

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

        if derived.get('appVariables'):
            # we can just fill teplate with provided values
            values = derived.get('appVariables')
            filled = self._fill_template(loaded, values=values)
            stack = [(filled, derived)]
            while stack:
                left, right = stack.pop()
                if left == right:
                    continue
                elif all(isinstance(i, Mapping) for i in (left, right)):
                    for key, val in left.items():
                        if key not in right:
                            return False
                        stack.append((val, right.pop(key)))
                    if right:
                        return False
                elif all(isinstance(i, basestring) for i in (left, right)):
                    if not re.match(re.escape(left).replace(
                            '\\%USER\\_DOMAIN\\%', '.*'), right):
                        return False
                elif all(isinstance(i, Sequence) for i in (left, right)):
                    if len(left) != len(right):
                        return False
                    stack.extend(zip(left, right))
                else:
                    return False
            return True

        entities_set = set(self._entities.values())
        any_entity_regex = re.compile('(?:\\%USER\\_DOMAIN\\%|{0})'.format(
            '|'.join(entity.uid for entity in entities_set)))
        stack = [(loaded, derived)]
        while stack:
            left, right = stack.pop()
            if left == right:
                continue
            elif all(isinstance(i, Mapping) for i in (left, right)):
                for key, val in left.items():
                    if key not in right:
                        return False
                    stack.append((val, right.pop(key)))
                if right:
                    return False
            elif all(isinstance(i, basestring) for i in (left, right)):
                if not re.match(
                        any_entity_regex.sub('.*', re.escape(left)),
                        right):
                    return False
            elif all(isinstance(i, Sequence) for i in (left, right)):  # list
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
    @atomic()
    def update(cls, app_id, version_id=None, new_version=None, **kw):
        """
        Class method that updates one or more PA object fields
        :param new_version: save as new version
        :param version_id: None edit active version
        :param app_id: int -> PA database ID
        :return: object -> PA instance
        """
        app = PredefinedAppModel.query.get(app_id)
        if app is None:
            return
        if version_id or new_version:
            app.select_version(version_id, new_version)
        allowed_fields = set(cls.FIELDS + cls.FIELD_VERSION) - \
            {'id', 'created', 'modified'}
        fields_to_update = allowed_fields & set(kw)
        if not kw.get('origin'):
            kw['origin'] = 'unknown'
        if not kw.get('template'):
            fields_to_update = fields_to_update - {'template'}
        elif new_version:  # create new version before updating other fields
            app.template = kw['template']
            fields_to_update = fields_to_update - {'template'}
        for attr in fields_to_update:
            setattr(app, attr, kw[attr])
        db.session.flush()
        return cls(**app.to_dict())

    # TODO: move to AppInstance
    @classmethod
    def get_plans_info_for_pod(cls, pod_id, user=None):
        """
        Class method that returns info about packages available for the pod.
        :param pod_id: string -> uuid, pod (database) ID
        """
        app_instance = AppInstance(pod_id, user)
        perm = 'get' if app_instance.db_pod.owner == user else 'get_non_owned'
        check_permission(perm, 'pods').check()

        return app_instance.predefined_app._get_plans_info_for_pod(
            app_instance.db_pod)

    def _get_plans_info_for_pod(self, pod):
        """
        Get info about packages available for the pod.
        :param obj -> pod object retrieved from DB
        """
        plans = self._expand_plans(self._get_filled_template(),
                                   with_info=False)
        pod_config = pod.get_dbconfig()

        disks_size = {vol.get('name'): vol.get('persistentDisk')['pdSize']
                      for vol in pod_config.get('volumes_public', [])
                      if vol.get('persistentDisk')}
        resize_available = STORAGE_CLASS.is_pv_resizable()

        for plan in plans:
            for plan_pod in plan['pods']:
                if not resize_available:
                    for pd in plan_pod.get('persistentDisks', []):
                        pd['pdSize'] = disks_size[pd['name']]
            self._calculate_info(plan)
        return plans

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
    def _update_IPs(pod, root, pod_config, dry_run=False):
        """
        Toggles pod publicIP
        :param pod: obj -> pod to be processed
        :param root: dict -> modified pod config spec
        :param pod_config: dict -> current pod config spec
        """
        wanted = PodCollection.has_public_ports(root)
        curr_IP = pod_config.get('public_ip')
        if wanted and curr_IP is None:
            if not IPPool.has_public_ips():
                raise PredefinedAppExc.AppPackageChangeImpossible(
                    details={'message': 'Unable to pick up public IP'})
            if not dry_run:
                PodCollection._prepare_for_public_address(pod, root)
            pod_config['public_ip'] = root.get('public_ip')
        elif not wanted and curr_IP is not None:
            ip = pod_config.pop('public_ip', None)
            if not dry_run:
                PodCollection._remove_public_ip(pod_id=pod.id, ip=ip)

    @staticmethod
    def _update_and_restart(pod, owner):
        pod_collection = PodCollection(owner)
        pod_ = pod_collection._get_by_id(pod.id)
        pod_collection._stop_pod(pod_, raise_=False, block=True)
        pod.save()
        pod_collection.update(pod.id,
                              {'command': 'start', 'commandOptions': {}})

    @staticmethod
    def _update_pv_sizes(pod, new_pv_sizes=None, dry_run=False):
        if new_pv_sizes:
            # save old values
            old_pv_sizes = pod.get_volumes_size()
            shared_items = (set(old_pv_sizes.items()) &
                            set(new_pv_sizes.items()))
            if not STORAGE_CLASS.is_pv_resizable() and \
               len(shared_items) != len(old_pv_sizes):
                raise APIError("Resize persistent disks not allowed")

            pv_query = PersistentDisk.get_all_query().filter(
                PersistentDisk.name.in_(new_pv_sizes.keys()))
            pv_id_dict = {pv.name: pv.id for pv in pv_query}
            try:
                for (pv_name, new_size) in new_pv_sizes.iteritems():
                    pv_id = pv_id_dict.get(pv_name)
                    change_pv_size(pv_id, new_size, dry_run=dry_run)
            except APIError as err:
                send_event_to_user(
                    'notify:error', {'message': "Error while resize "
                                                "persistent storage"},
                    pod.owner_id)
                # revert resize volumes
                for (pv_name, old_size) in old_pv_sizes.iteritems():
                    pv_id = pv_id_dict.get(pv_name)
                    change_pv_size(pv_id, old_size)
                raise err
        db_pod = Pod.query.get(pod.id)
        pod_config = db_pod.get_dbconfig()
        pod.volumes = pod_config['volumes']
        return pod_config

    def _update_pod_config(self, pod, new_config, async=True, dry_run=False):
        """
        Updates existing pod config to switch to new plan
        :param pod: obj -> pod object retrieved from DB
        :param new_config: dict -> filled config with applied values
        """
        if not PredefinedAppModel.query.get(self.id).switchingPackagesAllowed:
            raise PredefinedAppExc.AppPackageChangeImpossible(
                details={'message': (
                    "switching app package isn't supported for this version")})
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

        new_pd_sizes = None
        if STORAGE_CLASS.is_pv_resizable():
            vol_sizes = {}
            for vol in root.get('volumes', []):
                if vol.get('persistentDisk'):
                    new_size = vol['persistentDisk']['pdSize']
                    vol_name = vol['name']
                    vol_sizes[vol_name] = new_size
            # merge with current volumes
            new_pd_sizes = {pd['persistentDisk']['pdName']:
                            vol_sizes[pd['name']]
                            for pd in pod_config['volumes_public']
                            if pd['name'] in vol_sizes and
                            pd.get('persistentDisk')}

        pod_config = self._update_pv_sizes(pod, new_pd_sizes,
                                           dry_run=dry_run)
        self._update_kubes(root, pod_config)
        self._update_ports(root, pod_config)
        self._update_IPs(pod, root, pod_config, dry_run=dry_run)
        try:
            pod.kube_id = kube_id
            pod.template_plan_name = plan['name']
            pod.config = json.dumps(pod_config)
            if not dry_run:
                db.session.commit()
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
            if not dry_run:
                db.session.flush()
                pod_collection = PodCollection(pod.owner)
                pod_collection.update(pod.id, {
                    'command': 'start', 'commandOptions': {}})
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
    def _update_ports(left, right):
        """
        Updates right list ports with left list values
        :param left: list -> list to take values from
        :param right: list -> list to apply values to
        """
        ports_by_container = {}
        for container in left.get('containers', []):
            ports_by_container[container.get('name')] = container.get('ports')

        for container in right.get('containers', []):
            if container.get('name') in ports_by_container:
                container['ports'] = ports_by_container[container.get('name')]

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

    def get_plan_by_name(self, name, index_only=False):
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

        if not isinstance(loaded, Mapping):
            raise PredefinedAppExc.InvalidTemplate()

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

        filled = fill(loaded)
        filled['appVariables'] = {
            entity.name: entity.coerce(values.get(entity.name, entity.default))
            for entity in used_entities.values()}
        return filled

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
            self.line, self.col = line, col  # for message on exception
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


class AppInstance(object):
    """Object that handles all predefined app instance related routines"""

    def __init__(self, pod_id, user=None):
        """
        :param pod_id: id of the instance
        :type pod_id: str
        :param user: user that performs all actions (may be owner or admin)
        :type user: kubedock.users.models.User
        """
        self.pod_id = pod_id
        self.user = user
        self.predefined_app, self.db_pod = self.get_template_from_pod_id()

    def get_template_from_pod_id(self):
        """
        Helper method that returns PredefinedApp instance and DBPod by pod_id.

        :returns: PredefinedApp instance, pod model
        :rtype: (kubedock.kapi.apps.PredefinedApp, kubedock.pods.models.Pod)
        :raises: NotFound, PredefinedAppExc.NotPredefinedAppPod
        """
        if hasattr(self, 'db_pod') and hasattr(self, 'predefined_app'):
            return self.predefined_app, self.db_pod
        pod = Pod.query.get(self.pod_id)
        if pod is None:
            raise NotFound('Pod not found')
        if pod.template_id is None:
            raise PredefinedAppExc.NotPredefinedAppPod
        return PredefinedApp.get(pod.template_id), pod

    def update_plan(self, plan_id, values=None, async=True, dry_run=False):
        """
        Update predefined app pod to a particular plan.
        :param plan_id: int -> plan ID
        :param values: dict -> values to fill defaults
        :param async: bool -> not to wait for result if async
        """
        self._check_permissions()
        filled = self.predefined_app.get_filled_template_for_plan(
            plan_id, values)
        self.predefined_app._update_pod_config(
            self.db_pod, filled, async, dry_run=dry_run)
        return self.predefined_app.get_plan(plan_id)

    def update_plan_by_name(self, plan_name, values=None, async=True,
                            dry_run=False):
        """
        Update predefined app pod to a particular plan.
        :param plan_name: string -> plan name
        :param values: dict -> values to fill defaults
        :param async: bool -> not to wait for result if async
        """
        plan_id = self.predefined_app.get_plan_by_name(
            plan_name, index_only=True)
        return self.update_plan(plan_id, values, async, dry_run)

    def _check_permissions(self):
        """
        Makes some checks to make sure user is allowed requested action
        An exception is expected to be raised when check failed
        :raises: PermissionDenied
        """
        if not self.user:
            return

        if self.db_pod.owner == self.user:
            check_permission('edit', 'pods').check()
        else:
            check_permission('edit_non_owned', 'pods').check()

        if (not self.user.is_administrator() and has_billing() and
                self.user.fix_price):
            raise PermissionDenied

    def check_for_updates(self):
        """Compare current version and the active version"""
        current_version_id = self.db_pod.template_version_id
        active_version_id = self.predefined_app.activeVersionID
        return {
            'updateAvailable': current_version_id != active_version_id,
            'currentVersionID': current_version_id,
            'activeVersionID': active_version_id,
        }

    def update_version(self):
        """
        Update the pod by saving new config as `edited_config` and applying
            those changes.
        """
        update = self.check_for_updates()
        if not update['updateAvailable']:
            return
        pod_collection = PodCollection(self.db_pod.owner)

        plan_id = self.predefined_app.get_plan_by_name(
            self.db_pod.template_plan_name, index_only=True)
        app_variables = self.db_pod.get_dbconfig().get('appVariables', {})

        pod_data = self.predefined_app.get_filled_template_for_plan(
            plan_id, app_variables, with_id=False)
        if not isinstance(pod_data, list):
            pod_data = [pod_data]  # should be list of docs
        not_editable_attributes = {
            'appVariables',
            'name',
            'kuberdock_template_id',
            'kuberdock_plan_name',
            'kuberdock_template_version_id',
        }
        pod_data = {k: v for k, v in dispatch_kind(pod_data).items()
                    if k not in not_editable_attributes}

        pod_collection.edit(pod_collection._get_by_id(self.db_pod.id),
                            {'edited_config': pod_data})
        self.db_pod.template_version_id = update['activeVersionID']

        pod_collection.update(self.db_pod.id, {
            'command': 'redeploy', 'commandOptions': {
                'applyEdit': True,
                'internalEdit': True,
            }})


def start_pod_from_yaml(pod_data, user=None, template_id=None, dry_run=False):
    if not isinstance(pod_data, list):
        pod_data = [pod_data]  # should be list of docs
    new_pod = dispatch_kind(pod_data, template_id)
    new_pod = check_new_pod_data(new_pod, user)

    if template_id is None and user and user.role.rolename == 'LimitedUser':
        # legacy check that filled yaml is created from template
        # TODO: remove after AC-4516
        template_id = new_pod.get('kuberdock_template_id')
        if template_id is None:
            raise PredefinedAppExc.NotPredefinedAppPod
        pa = PredefinedApp.get(template_id)
        if not pa.is_template_for(pod_data[0]):
            raise PredefinedAppExc.NotPredefinedAppPod

    return PodCollection(user).add(new_pod, dry_run=dry_run)


def dispatch_kind(docs, template_id=None):
    if not docs or not docs[0]:  # at least one needed
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
        'appVariables': doc.get('appVariables', {}),  # $VAR$ to value mapping
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
    if new_pod.get('kuberdock_template_id') is not None:
        app = PredefinedAppModel.query.get(new_pod['kuberdock_template_id'])
        new_pod['kuberdock_template_version_id'] = app.get_template_object().id

    if spec_body.get('domain'):
        new_pod['domain'] = spec_body.get('domain')
    elif plan.get('baseDomain'):
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
