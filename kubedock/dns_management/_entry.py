import importlib

from flask import current_app

from . import plugins
from ..constants import KUBERDOCK_INGRESS_POD_NAME
from ..pods.models import Pod
from ..system_settings import keys
from ..system_settings.models import SystemSettings
from ..users.models import User


def _get_ingress_controller_pod():
    """Returns Pod model object for ingress controller pod.
    None if there are no such pod.
    """
    owner = User.get_internal()
    ingress_controller = Pod.filter_by(name=KUBERDOCK_INGRESS_POD_NAME,
                                       owner=owner).first()
    return ingress_controller


class _IngressController(object):
    """Simple class to cache Ingress controller pod data"""

    def __init__(self):
        self._dbpod = _get_ingress_controller_pod()
        self._public_ip = None

    def get_public_ip(self):
        if self._public_ip is not None:
            return self._public_ip
        if self._dbpod is None:
            return None
        if current_app.config['AWS']:
            self._public_ip = self._dbpod.get_dbconfig('public_aws')
        else:
            self._public_ip = self._dbpod.get_dbconfig('public_ip')
        return self._public_ip

    def is_ready(self):
        if self._dbpod is None:
            return False, u'Ingress controller pod not found'
        if self.get_public_ip() is None:
            return False, u'Ingress controller pod has no public IP'
        return True, None


class _Plugin(object):
    """Simple class to access dns management plugin.
    Caches loaded plugin and it's parameters.
    """

    def __init__(self):
        self.name = SystemSettings.get_by_name(keys.DNS_MANAGEMENT_SYSTEM)
        self._plugin = None
        self._plugin_kwargs = None

    def get_plugin(self):
        """Tries to load plugin.
        :return: loaded plugin or None
        """
        if self._plugin is not None:
            return self._plugin
        try:
            self._plugin = importlib.import_module(
                '{0}.{1}'.format(plugins.__name__, self.name)
            )
        except ImportError:
            current_app.logger.exception(
                u'Failed to load plugin "{}"'.format(self.name))
            return None
        return self._plugin

    def get_kwargs(self):
        """Returns arguments for loaded plugin."""
        if self._plugin_kwargs is not None:
            return self._plugin_kwargs
        plugin = self.get_plugin()
        if plugin is None:
            return None
        args = plugin.ALLOWED_ARGS
        kwargs = {}
        for key in args:
            setting_name = u'dns_management_{0}_{1}'.format(self.name, key)
            value = SystemSettings.get_by_name(setting_name)
            valid, message = plugin.is_valid_arg(key, value)
            if not valid:
                current_app.logger.error(
                    u'DNS Management is misconfigured, '
                    u'setting name: {}. Reason: {}'.format(
                        setting_name, message))
                return None
            kwargs.update({key: value})
        self._plugin_kwargs = kwargs
        return self._plugin_kwargs

    def is_ready(self):
        """Check if current plugin is ready and properly configured
        :return: tuple of success flag, and error message or None
        """
        if self.name not in plugins.__all__:
            return (False,
                    u'Unknown DNS management system: "{0}"'.format(self.name))
        if self.get_plugin() is None:
            return False, u'Failed to load plugin "{}"'.format(self.name)

        if self.get_kwargs() is None:
            return False, u'Plugin "{}" is misconfigured'.format(self.name)

        return True, None


def _are_components_ready(*components):
    """Checks if DNS management system is ready for assignment pod's domains.
    :param ingress_controller: optional object of _IngressController class
    :param plugin: optional object of _Plugin class

    :return: tuple of Readiness flag (True/False), string (description if it
        is not ready yet)
    """
    for component in components:
        if component is None:
            continue
        is_ready, message = component.is_ready()
        if not is_ready:
            return is_ready, message
    return True, None


def is_domain_system_ready():
    """Checks if domain subsystem is ready and properly configured.
    :return: tuple of success flag and error description.
    """
    return _are_components_ready(_IngressController(), _Plugin())


def create_or_update_record(domain, record_type):
    """Create or Update DNS record

    :param domain: Pod Domain Name
    :type domain: str
    :return: tuple of success flag and error description If something goes
        wrong in DNS Management plugin or system is not properly configured.
    """
    ingress_controller = _IngressController()
    plugin = _Plugin()
    isready, message = _are_components_ready(ingress_controller, plugin)
    if not isready:
        return (
            False,
            u'Failed to create domain {}. Reason: {}'.format(domain, message))

    plugin_module = plugin.get_plugin()
    kwargs = plugin.get_kwargs()
    try:
        if record_type == 'A':
            plugin_module.entry.delete_type_CNAME_record(domain, **kwargs)
            new_ips = [ingress_controller.get_public_ip()]
            plugin_module.entry.create_or_update_type_A_record(
                domain, new_ips, **kwargs)
        elif record_type == 'CNAME':
            plugin_module.entry.delete_type_A_record(domain, **kwargs)
            plugin_module.entry.create_or_update_type_CNAME_record(
                domain, ingress_controller.get_public_ip(), **kwargs)
    except Exception as err:
        current_app.logger.exception(
            u'Failed to run plugin create_or_update_type_{}_record, '
            u'domain: "{}"'.format(record_type, domain))
        return False, u'Exception from plugin "{}":\n{}'.format(
            plugin.name, repr(err))
    return True, None


def delete_record(domain, record_type):
    """Delete DNS record given its type

    :param domain: Pod Domain Name
    :type domain: str
    :type record_type: either A or CNAME string at the moment
    :return: tuple of success flag and error description If something goes
        wrong in DNS Management plugin
    """
    plugin = _Plugin()
    isready, message = plugin.is_ready()
    if not isready:
        return (
            False,
            u'Failed to delete domain record "{}": {}'.format(domain, message))
    try:
        p = plugin.get_plugin()
        if record_type == 'A':
            p.entry.delete_type_A_record(domain, **plugin.get_kwargs())
        elif record_type == 'CNAME':
            p.entry.delete_type_CNAME_record(domain, **plugin.get_kwargs())
        return True, None
    except Exception as err:
        current_app.logger.exception(
            u'Failed to run plugin delete_type_{}_record, domain: "{}"'
            .format(record_type, domain))
        return False, u'Exception from plugin "{}":\n{}'.format(
            plugin.name, repr(err))


def check_if_zone_exists(domain):
    """Check if zone exists.

    :param domain: Domain name
    :type domain: str
    :return: tuple of exists flag and error description If something goes
        wrong in DNS Management plugin
    """
    plugin = _Plugin()
    is_ready, message = plugin.is_ready()
    if not is_ready:
        return (
            False,
            u'Failed to check zone existence "{}": {}'.format(domain, message))
    try:
        rv = plugin.get_plugin().entry.check_if_zone_exists(
            domain, **plugin.get_kwargs())
    except Exception as err:
        current_app.logger.exception(
            u'Failed to run plugin check_if_zone_exists, domain: "{}"'
            .format(domain))
        return False, u'Exception from plugin "{}":\n{}'.format(
            plugin.name, repr(err))
    else:
        return rv, None
