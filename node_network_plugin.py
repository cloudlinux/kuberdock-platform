#!/usr/bin/env python2

from __future__ import print_function

import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import urlparse
import zipfile
from ConfigParser import ConfigParser
from StringIO import StringIO
from collections import OrderedDict
from contextlib import contextmanager
from tempfile import NamedTemporaryFile

import ipaddress
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

FSLIMIT_PATH = '/var/lib/kuberdock/scripts/fslimit.py'
PLUGIN_PATH = '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/'
KD_CONF_PATH = PLUGIN_PATH + 'kuberdock.json'

PUBLIC_IP_RULE = 'iptables -w -{0} KUBERDOCK-PUBLIC-IP -t nat -d {1} ' \
                 '-p {2} --dport {3} -j DNAT --to-destination {4}:{5}'

PUBLIC_IP_MANGLE_RULE = \
    'iptables -w -{0} KUBERDOCK-PUBLIC-IP -t mangle -d {1} ' \
    '-p {2} --dport {3} -j MARK --set-mark 2'

PUBLIC_IP_POSTROUTING_RULE = 'iptables -w -{0} KUBERDOCK-PUBLIC-IP-SNAT ' \
                             '-t nat -s {1} -j SNAT --to-source {2}'

# MARKS:
# 1 - traffic to reject/drop
# 2 - traffic for public ip (will be added and used later)

# Possibly to stderr if in daemon mode or to our log-file
LOG_TO = sys.stderr


def glog(*args):
    print(*args, file=LOG_TO)


class PluginException(Exception):
    pass


class ETCD(object):
    ignore = ('createdIndex', 'dir', 'key', 'modifiedIndex')

    extended_statuses = 'extended_statuses'
    users_path = 'users'

    def __init__(self, path=None):
        config = read_config_ini('/etc/sysconfig/flanneld')
        self.server = config['flannel_etcd']
        self.cert = config['etcd_certfile']
        self.key = config['etcd_keyfile']
        if path is None:
            path = '/'.join([config['flannel_etcd_key'].strip('/'), 'plugin'])
        self.path = path

    def _url(self, *args):
        url = '/'.join([self.server, 'v2/keys', self.path] + map(str, args))
        return url

    def _args(self, **kwargs):
        args = dict(cert=(self.cert, self.key), verify=False)
        args.update(kwargs)
        return args

    def _get(self, *args):
        r = requests.get(self._url(*args), **self._args())
        try:
            items = r.json()['node']['nodes']
        except Exception:
            return {}

        res_dict = {}
        for item in items:
            item_key = item['key'].rsplit('/')[-1]
            item_dict = dict(
                [(k, v) for k, v in item.items() if k not in self.ignore]
            )
            res_dict[item_key] = item_dict
        return res_dict

    def pods(self, user):
        pods_list = []
        for k, v in self._get(self.users_path, user).items():
            try:
                value = json.loads(v['value'])
            except ValueError:
                value = {'node': None, 'service': None}
            pods_list.append((k, value))
        pods = dict(pods_list)
        return pods

    def users(self):
        users = []
        for user in self._get(self.users_path):
            try:
                users.append(int(user))
            except ValueError as e:
                glog('Error while try to convert user_id to int: {}'.format(e))
        return users

    def delete_user(self, user, pod):
        url = self._url(self.users_path, user, pod)
        self.delete(url)

    def delete(self, url):
        requests.delete(url, **self._args())

    def registered_hosts(self):
        registered_hosts = list(self._get('registered_hosts'))
        return registered_hosts

    def delete_ex_status(self, namespace, k8s_pod):
        url = self._url(self.extended_statuses, namespace, k8s_pod)
        self.delete(url)

    def put_ex_status(self, namespace, k8s_pod, message):
        url = self._url(self.extended_statuses, namespace, k8s_pod)
        self.put(url, message)

    def put(self, url, value):
        requests.put(url, data={'value': value}, **self._args())

    def wait(self):
        requests.get(
            self._url(),
            **self._args(params=dict(wait=True, recursive=True))
        )


def read_config_ini(filename):
    section = '__section__'

    with open(filename) as config_fp_orig:
        config_raw_orig = config_fp_orig.read()

    config_raw_new = '[{0}]\n'.format(section)
    config_raw_new += config_raw_orig

    config_fp_new = StringIO(config_raw_new)

    config = ConfigParser()
    config.readfp(config_fp_new)

    config_fp_new.close()

    config_dict = dict([(k, v.strip('"')) for k, v in config.items(section)])
    return config_dict


def read_config_json(filename):
    with open(filename) as f:
        return json.loads(f.read())


def set_config(filename, data):
    with open(filename) as f:
        lines = f.read().splitlines()

    d = OrderedDict([l.split('=', 1) for l in lines])
    d.update(data)

    with open(filename, 'w') as f:
        f.writelines(['{0}={1}\n'.format(k, v) for k, v in d.items()])


def _update_ipset(set_name, ip_list, set_type='hash:ip'):
    set_temp = '{0}_temp'.format(set_name)
    subprocess.call(['ipset', '-exist', 'create', set_name, set_type])
    subprocess.call(['ipset', '-exist', 'create', set_temp, set_type])
    subprocess.call(['ipset', 'flush', set_temp])
    for ip in ip_list:
        subprocess.call(['ipset', 'add', set_temp, ip])
    subprocess.call(['ipset', 'swap', set_temp, set_name])
    subprocess.call(['ipset', 'destroy', set_temp])


def update_ipset():
    shared_ips = ['10.254.0.1', '10.254.0.10']
    nodes_ips = set()
    etcd = ETCD()
    for user in etcd.users():
        set_name = 'kuberdock_user_{0}'.format(user)
        user_ip_list = set(shared_ips)
        for pod_ip, value in etcd.pods(user).items():
            user_ip_list.add(pod_ip)
            if value['service']:
                user_ip_list.add(value['service'])
            if value['node']:
                nodes_ips.add(value['node'])
        _update_ipset(set_name, user_ip_list)
    nodes_ips.update(etcd.registered_hosts())
    _update_ipset('kuberdock_nodes', nodes_ips)


def modify_ip(cmd, ip, iface):
    if subprocess.call(['ip', 'addr', cmd, ip + '/32', 'dev', iface]):
        raise PluginException(
            'Error {0} ip: {1} on iface: {2}'.format(cmd, ip, iface))
    if cmd == 'add':
        subprocess.call(
            ['arping', '-I', iface, '-A', ip, '-c', '10', '-w', '1'])
    return 0


def get_pod_spec(pod_spec_file):
    if not os.path.exists(pod_spec_file):
        raise PluginException('Pod spec file is not exists. Skip call')
    with open(pod_spec_file) as f:
        return json.load(f)


def get_public_ip(pod):
    config = read_config_json(KD_CONF_PATH)
    master = config['master']
    node = config['node']
    token = config['token']
    try:
        r = requests.get(
            'https://{0}/api/ippool/get-public-ip/{1}/{2}?token={3}'.format(
                master, node, pod, token
            ),
            verify=False).json()
        if r['status'] == 'OK':
            ip = r['data']
            glog('Requested Public IP {0} for Pod {1}'.format(ip, pod))
            return ip
    except:
        pass


def handle_public_ip(
        action, public_ip, pod_ip, iface, namespace, k8s_pod_id, pod_data,
        pod_spec_file):
    with send_feedback_context(namespace, k8s_pod_id):
        nonfloating = (public_ip == 'true')
        if nonfloating:
            public_ip = get_public_ip(namespace)
            if public_ip is None:
                raise PluginException('Cannot get Public IP for {0}'.format(
                    namespace)
                )
            set_config(pod_data, {'POD_PUBLIC_IP': public_ip})
        if action not in ('add', 'del',):
            raise PluginException('Unknown action for public ip. Skip call.')
        spec = get_pod_spec(pod_spec_file)
        try:
            ports_s = spec['metadata']['annotations']['kuberdock-pod-ports']
            ports = json.loads(ports_s)
        except (TypeError, ValueError, KeyError) as e:
            raise PluginException(
                'Error loading ports from spec "{0}" Skip call.'.format(e))
        if not ports:
            return 4

        for container in ports:
            for port_spec in container:
                is_public = port_spec.get('isPublic', False)
                if not is_public:
                    continue

                container_port = port_spec.get('containerPort')
                if not container_port:
                    raise PluginException(
                        'Something went wrong. Bad pod spec received. Skip')

                proto = port_spec.get('protocol', 'tcp')
                host_port = port_spec.get('hostPort', None) or container_port

                if action == 'add':
                    add_ip(container_port, host_port, pod_ip, proto, public_ip)
                elif action == 'del':
                    delete_ip(container_port, host_port, pod_ip, proto,
                              public_ip)
        # Temporarily disable check. Maybe will be removed completely
        # if not (nonfloating or is_nonfloating_ip_mode_enabled()):
        #    modify_ip(action, public_ip, iface)
        modify_ip(action, public_ip, iface)
        return 0
    return 1


def is_nonfloating_ip_mode_enabled():
    enabled_options = ('1', 'on', 't', 'true', 'y', 'yes')
    config = read_config_json(KD_CONF_PATH)
    return config['nonfloating_public_ips'].lower() in enabled_options


def delete_ip(container_port, host_port, pod_ip, proto, public_ip):
    subprocess.call(
        PUBLIC_IP_RULE.format('D', public_ip, proto, host_port,
                              pod_ip, container_port).split(
            ' '))
    subprocess.call(
        PUBLIC_IP_MANGLE_RULE.format('D', public_ip, proto,
                                     host_port).split(' '))
    subprocess.call(
        PUBLIC_IP_POSTROUTING_RULE.format('D', pod_ip, public_ip).split(' '))


def add_ip(container_port, host_port, pod_ip, proto, public_ip):
    if subprocess.call(
            PUBLIC_IP_RULE.format('C', public_ip, proto,
                                  host_port, pod_ip,
                                  container_port).split(' ')):
        subprocess.call(
            PUBLIC_IP_RULE.format('I', public_ip, proto,
                                  host_port, pod_ip,
                                  container_port).split(' '))
    if subprocess.call(
            PUBLIC_IP_MANGLE_RULE.format('C', public_ip, proto,
                                         host_port).split(
                ' ')):
        subprocess.call(
            PUBLIC_IP_MANGLE_RULE.format('I', public_ip, proto,
                                         host_port).split(' '))
    if subprocess.call(
            PUBLIC_IP_POSTROUTING_RULE.format('C', pod_ip,
                                              public_ip).split(' ')):
        subprocess.call(
            PUBLIC_IP_POSTROUTING_RULE.format('I', pod_ip,
                                              public_ip).split(' '))


def init():
    config = read_config_ini('/run/flannel/subnet.env')
    config_network = config['flannel_network']
    config_subnet = config['flannel_subnet']
    _update_ipset('kuberdock_flannel', [config_network], set_type='hash:net')
    _update_ipset('kuberdock_nodes', [])
    _update_ipset('kuberdock_cluster',
                  ['kuberdock_flannel', 'kuberdock_nodes'],
                  set_type='list:set')
    network = ipaddress.ip_network(unicode(config_network))
    subnet = ipaddress.ip_network(unicode(config_subnet), strict=False)
    etcd = ETCD()
    for user in etcd.users():
        for pod in etcd.pods(user):
            pod_ip = ipaddress.ip_address(pod)
            if pod_ip not in network or pod_ip in subnet:
                etcd.delete_user(user, pod)
    update_ipset()


def watch(callback, args=None, path=None):
    if args is None:
        args = ()
    etcd = ETCD(path)
    while True:
        try:
            callback(*args)
            etcd.wait()
        except KeyboardInterrupt:
            break
        except requests.RequestException as e:
            glog("Error while request etcd: {}".format(e))
            time.sleep(5)


def send_feedback(namespace, k8s_pod, message):
    glog(message)
    etcd = ETCD()
    etcd.put_ex_status(namespace, k8s_pod, message)


@contextmanager
def send_feedback_context(namespace, k8s_pod):
    try:
        yield
    except Exception as e:
        status = "{}: {}".format(type(e).__name__, e.message)
        send_feedback(namespace, k8s_pod, status)
        # Will output exception to the caller and return 1 exit code
        raise


def remove_feedback(namespace, k8s_pod):
    etcd = ETCD()
    etcd.delete_ex_status(namespace, k8s_pod)


def handle_ex_status(action, namespace=None, k8s_pod=None, status=None):
    if action == 'add':
        send_feedback(namespace, k8s_pod, status)
    elif action == 'delete':
        remove_feedback(namespace, k8s_pod)


class VolumeRestoreException(Exception):
    pass


class VolumeSpec(object):
    def __init__(self, path, size, name, backup_url=None):
        """
        :param path: Local path.
        :param size: Size.
        :param name: Name.
        :param backup_url: Optional. URL which contains backup archives.
            Expected archive in format .tar.gz or .zip.
        """
        self.path = path
        self.size = size
        self.name = name
        self.backup_url = backup_url


class VolumeManager(object):
    """Class that creates, restores from backup and deletes volumes."""

    def restore_if_needed(self, volume_spec):
        """If backup url specified, it downloads the backup archive from
        backup url and extracts it into a volume path.
        """
        if not volume_spec.backup_url:
            return

        url_path = urlparse.urlparse(volume_spec.backup_url).path
        extractor = self._ArchiveExtractor()
        try:
            extractor.detect_type_by_extension(url_path)
        except extractor.UnknownType:
            raise VolumeRestoreException(
                'Unknown type of archive got from {url}. '
                'At the moment only {supported_formats} formats '
                'are supported'.format(
                    url=volume_spec.backup_url,
                    supported_formats=', '.join(
                        x.strip('.') for x in extractor.supported_formats)
                ))

        try:
            r = requests.get(volume_spec.backup_url, stream=True, verify=False)
            r.raise_for_status()

            with NamedTemporaryFile('w+b') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)

                f.seek(0)
                extractor.extract(f, volume_spec.path)

        except (requests.exceptions.RequestException, socket.timeout):
            raise VolumeRestoreException(
                'Connection failure while downloading backup from {}'
                    .format(volume_spec.backup_url))
        except extractor.BadArchive:
            raise VolumeRestoreException(
                'An error occurred while extracting archive got from {}'
                    .format(volume_spec.backup_url))

    def create(self, volume_spec):
        """
        Creates a folder for the volume and sets correct SELinux type on it
        """
        try:
            os.makedirs(volume_spec.path)
            subprocess.call(
                ['chcon', '-Rt', 'svirt_sandbox_file_t', volume_spec.path])
        except os.error:
            raise PluginException(
                'Failed to create local storage dir "{}"'
                    .format(volume_spec.path)
            )

    @staticmethod
    def remove(volume_spec):
        """
        Physically removes directory
        """
        shutil.rmtree(volume_spec.path, True)

    class _ArchiveExtractor(object):
        supported_formats = ['.tar.gz', '.zip']

        def __init__(self, archive_type=None):
            self.archive_type = archive_type

        def detect_type_by_extension(self, path):
            for ext in self.supported_formats:
                if path.endswith(ext):
                    self.archive_type = ext
                    return self

            raise self.UnknownType

        def extract(self, file_obj, path):
            assert self.archive_type
            extractors = {
                '.tar.gz': self._extract_tar,
                '.zip': self._extract_zip
            }
            try:
                extract = extractors[self.archive_type]
            except KeyError:
                raise self.UnknownType
            else:
                return extract(file_obj, path)

        def _extract_tar(self, file_obj, path):
            try:
                with tarfile.open(fileobj=file_obj, mode='r:gz') as archive:
                    archive.extractall(path)
            except tarfile.TarError:
                raise self.BadArchive

        def _extract_zip(self, file_obj, path):
            try:
                with zipfile.ZipFile(file_obj) as archive:
                    archive.extractall(path)
            except zipfile.BadZipfile:
                raise self.BadArchive

        class UnknownType(Exception):
            pass

        class BadArchive(Exception):
            pass


class LocalStorage(object):
    volume_manager = VolumeManager()

    @classmethod
    def init(cls, pod_spec_file):
        annotations, metadata, vol_annotations = cls._parse_pod_spec(
            pod_spec_file)

        volumes = [cls.extract_volume_spec(a)
                   for a in vol_annotations if cls.check_annotation(a)]
        cls.create_volumes(volumes)
        try:
            cls.restore_backups(volumes)
        except VolumeRestoreException:
            cls.remove_volumes(volumes)
            raise

        cls.set_xfs_volume_size_limits(volumes)

    @classmethod
    def extract_volume_spec(cls, annotation):
        """
        Extracts volumes specifications from annotation.
        :param annotation: POD's volume annotation.
        :return: Instance of :class:`VolumeSpec`.
        """
        ls = annotation['localStorage']
        backup_url = annotation.get('backupUrl')
        path, size, name = ls['path'], ls.get('size', 1), ls['name']
        volume_spec = VolumeSpec(path=path, size='{}g'.format(size), name=name,
                                 backup_url=backup_url)
        return volume_spec

    @classmethod
    def create_volumes(cls, volume_specs):
        for v in volume_specs:
            cls.volume_manager.create(v)

    @classmethod
    def restore_backups(cls, volume_specs):
        for v in volume_specs:
            cls.volume_manager.restore_if_needed(v)

    @classmethod
    def remove_volumes(cls, volume_specs):
        for v in volume_specs:
            cls.volume_manager.remove(v)

    @classmethod
    def set_xfs_volume_size_limits(cls, volume_specs):
        if not volume_specs:
            return
        subprocess.call(
            ['/usr/bin/env', 'python2', FSLIMIT_PATH, 'storage'] +
            ['{0}={1}'.format(v.path, v.size) for v in volume_specs]
        )

    @staticmethod
    def check_annotation(annotation):
        """
        Verifies if POD's annotation has all necessary information for local
        storage creation and if storage directory was already created

        :param annotation: dictionary containing POD's annotations
        :return: True if annotations are good and False otherwise
        """
        try:
            if os.path.exists(annotation['localStorage']['path']):
                return False
        except (KeyError, TypeError):
            return False
        return True

    @classmethod
    def _parse_pod_spec(cls, pod_spec_file):
        try:
            metadata = get_pod_spec(pod_spec_file)['metadata']
            annotations = metadata['annotations']
            vol_annotations = json.loads(
                annotations.get('kuberdock-volume-annotations', '[]'))
        except (TypeError, ValueError, KeyError) as e:
            raise PluginException(
                'Error loading volume annotations from spec "{0}" '
                'Skip call.'.format(e)
            )
        return annotations, metadata, vol_annotations


def get_k8s_info():
    server = token = ''
    with open('/etc/kubernetes/configfile') as cf:
        for l in cf:
            l = l.strip()
            if l.startswith('server:'):
                server = l.split('server:')[-1].strip()
            if l.startswith('token:'):
                token = l.split('token:')[-1].strip()
            if server and token:
                break
    return server, token


def existing_pods():
    server, token = get_k8s_info()
    r = requests.get('{0}/api/v1/pods'.format(server),
                     headers={'Authorization': 'Bearer {0}'.format(token)},
                     verify=False)
    if r.status_code != 200:
        return
    pods = set()
    for pod in r.json()['items']:
        pod_metadata = pod['metadata']
        pod_namespace = pod_metadata['namespace']
        pod_name = pod_metadata['name']
        pods.add((pod_namespace, pod_name))
    return pods


def node_known_pods():
    data_dir = os.path.join(PLUGIN_PATH, 'data')
    pods = set()
    namespaces = [d for d in os.listdir(data_dir)
                  if os.path.isdir(os.path.join(data_dir, d))]
    for namespace in namespaces:
        name = os.listdir(os.path.join(data_dir, namespace))[0]
        pods.add((namespace, name))
    return pods


def teardown_unexisting():
    pods_to_teardown = node_known_pods() - existing_pods()
    for pod_namespace, pod_name in pods_to_teardown:
        subprocess.call([os.path.join(PLUGIN_PATH, 'kuberdock'),
                         'teardown', pod_namespace, pod_name])


def main(action, *args):
    if action == 'init':
        # TODO must be called after each restart service and flush/restore
        # correct iptables rules and chains (incl. public ip chains)
        init()
    elif action == 'setup':
        handle_public_ip('add', *args)
    elif action == 'initlocalstorage':
        LocalStorage.init(*args)
    elif action == 'teardown':
        handle_public_ip('del', *args)
    elif action == 'update':
        update_ipset()
    elif action == 'watch':
        watch(update_ipset)
    elif action == 'ex_status':
        handle_ex_status(*args)
    elif action == 'teardown_unexisting':
        teardown_unexisting()


if __name__ == '__main__':
    main(*sys.argv[1:])
