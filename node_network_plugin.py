#!/usr/bin/env python2

from __future__ import print_function

import os
import socket
import sys
import tarfile
import time
import json
import subprocess
from ConfigParser import ConfigParser
from StringIO import StringIO
from collections import OrderedDict, namedtuple
from contextlib import contextmanager
from tempfile import NamedTemporaryFile

import ipaddress
import requests
import shutil
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

FSLIMIT_PATH = '/var/lib/kuberdock/scripts/fslimit.py'
PLUGIN_PATH = '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/'
INI_PATH = PLUGIN_PATH + 'kuberdock.ini'

PUBLIC_IP_RULE = 'iptables -w -{0} KUBERDOCK-PUBLIC-IP -t nat -d {1} ' \
                 '-p {2} --dport {3} -j DNAT --to-destination {4}:{5}'

PUBLIC_IP_MANGLE_RULE = \
    'iptables -w -{0} KUBERDOCK-PUBLIC-IP -t mangle -d {1} ' \
    '-p {2} --dport {3} -j MARK --set-mark 2'

PUBLIC_IP_POSTROUTING_RULE = 'iptables -w -{0} KUBERDOCK-PUBLIC-IP-SNAT ' \
                             '-t nat -s {1} -o {2} -j SNAT --to-source {3}'

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
        config = get_config('/etc/sysconfig/flanneld')
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


def get_config(filename):
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
    config = get_config(INI_PATH)
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
                    add_ip(container_port, host_port, pod_ip, proto, public_ip,
                           iface)
                elif action == 'del':
                    delete_ip(container_port, host_port, pod_ip, proto,
                              public_ip, iface)
        # Temporarily disable check. Maybe will be removed completely
        # if not (nonfloating or is_nonfloating_ip_mode_enabled()):
        #    modify_ip(action, public_ip, iface)
        modify_ip(action, public_ip, iface)
        return 0
    return 1


def is_nonfloating_ip_mode_enabled():
    enabled_options = ('1', 'on', 't', 'true', 'y', 'yes')
    config = get_config(INI_PATH)
    return config['nonfloating_public_ips'].lower() in enabled_options


def delete_ip(container_port, host_port, pod_ip, proto, public_ip, iface):
    subprocess.call(
        PUBLIC_IP_RULE.format('D', public_ip, proto, host_port,
                              pod_ip, container_port).split(
            ' '))
    subprocess.call(
        PUBLIC_IP_MANGLE_RULE.format('D', public_ip, proto,
                                     host_port).split(' '))
    subprocess.call(
        PUBLIC_IP_POSTROUTING_RULE.format('D', pod_ip, iface,
                                          public_ip).split(' '))


def add_ip(container_port, host_port, pod_ip, proto, public_ip, iface):
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
            PUBLIC_IP_POSTROUTING_RULE.format('C', pod_ip, iface,
                                              public_ip).split(' ')):
        subprocess.call(
            PUBLIC_IP_POSTROUTING_RULE.format('I', pod_ip, iface,
                                              public_ip).split(' '))


def init():
    config = get_config('/run/flannel/subnet.env')
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


class Volume(object):
    def __init__(self, path, size, name):
        self.path, self.size, self.name = path, size, name

    def restore(self, backup_url, user_id):
        """
        Downloads the backup archive from a given base URL and extracts it
        into a volume path

        :param backup_url: URL which contains backup archives. It is expected
        that the particular volume backup is found at:
                        base_url/backups/<user_id>/<volume_name>
        :param user_id: user ID which is used to construct the final URL to
        the backup archive
        """
        archive_name = '{}.tar.gz'.format(self.name)
        url = '/'.join([backup_url, 'backups', user_id, archive_name])

        try:
            r = requests.get(url, stream=True, verify=False)
            r.raise_for_status()

            with NamedTemporaryFile('w+b') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)

                f.seek(0)
                self._extract_archive(f)

        except (requests.exceptions.RequestException, socket.timeout):
            raise VolumeRestoreException(
                'Connection failure while downloading backup from {}'.format(
                    url))
        except tarfile.TarError:
            raise VolumeRestoreException(
                'An error occurred while extracting {}'.format(archive_name))

    def create(self):
        """
        Creates a folder for the volume and sets correct SELinux type on it
        """
        try:
            os.makedirs(self.path)
            subprocess.call(
                ['chcon', '-Rt', 'svirt_sandbox_file_t', self.path])
        except os.error:
            raise PluginException(
                'Failed to create local storage dir "{}"'.format(self.path)
            )

    def remove(self):
        """
        Physically removes directory
        """
        shutil.rmtree(self.path, True)

    def _extract_archive(self, file_obj):
        with tarfile.open(fileobj=file_obj, mode='r:gz') as archive:
            archive.extractall(self.path)


class LocalStorage(object):
    @classmethod
    def init(cls, pod_spec_file):
        annotations, metadata, vol_annotations = cls._parse_pod_spec(
            pod_spec_file)

        volumes = [cls.create_volume(a) for a in vol_annotations
                   if cls.check_annotation(a)]

        backup_url = annotations.get('kuberdock-volumes-backup-url')
        try:
            if backup_url:
                cls.restore_backup(backup_url, volumes, metadata)
        except VolumeRestoreException:
            cls._cleanup(volumes)
            raise

        cls.set_xfs_volume_size_limits(volumes)

    @classmethod
    def set_xfs_volume_size_limits(cls, volumes):
        if not volumes:
            return
        subprocess.call(
            ['/usr/bin/env', 'python2', FSLIMIT_PATH, 'storage'] +
            ['{0}={1}'.format(v.path, v.size) for v in volumes]
        )

    @classmethod
    def restore_backup(cls, backup_url, volumes, metadata):
        user_id = metadata['labels']['kuberdock-user-uid']

        for v in volumes:
            v.restore(backup_url, user_id)

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
    def create_volume(cls, annotation):
        """
        Instantiates a Volume object given volume annotation and creates a
        volume
        :param annotation: POD's volume annotation
        :return: Volume object
        """
        ls = annotation['localStorage']
        path, size, name = ls['path'], ls.get('size', 1), ls['name']
        v = Volume(path=path, size='{}g'.format(size), name=name)

        glog("Making directory for local storage: {}".format(annotation))
        v.create()
        return v

    @classmethod
    def _cleanup(cls, volumes):
        for v in volumes:
            v.remove()

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


if __name__ == '__main__':
    main(*sys.argv[1:])
