#!/usr/bin/env python2

from __future__ import print_function

import re
import os
import sys
import json
import subprocess
from ConfigParser import ConfigParser
from StringIO import StringIO

import ipaddress
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


PUBLIC_IP_RULE = 'iptables -w -{0} KUBERDOCK-PUBLIC-IP -t nat -d {1} ' \
                 '-p {2} --dport {3} -j DNAT --to-destination {4}:{5}'

PUBLIC_IP_MANGLE_RULE = \
    'iptables -w -{0} KUBERDOCK-PUBLIC-IP -t mangle -d {1} ' \
    '-p {2} --dport {3} -j MARK --set-mark 2'

# MARKS:
# 1 - traffic to reject/drop
# 2 - traffic for public ip (will be added and used later)

# Possibly to stderr if in daemon mode or to our log-file
LOG_TO = sys.stdout


def glog(*args):
    print(*args, file=LOG_TO)


class ETCD(object):
    ignore = ('createdIndex', 'dir', 'key', 'modifiedIndex')

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
        for k, v in self._get('users', user).items():
            try:
                value = json.loads(v['value'])
            except ValueError:
                value = {'node': None, 'service': None}
            pods_list.append((k, value))
        pods = dict(pods_list)
        return pods

    def users(self):
        users = map(int, self._get('users'))
        return users

    def delete(self, user, pod):
        requests.delete(self._url('users', user, pod), **self._args())

    def registered_hosts(self):
        registered_hosts = list(self._get('registered_hosts'))
        return registered_hosts

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
        glog('Error {0} ip: {1} on iface: {2}'.format(cmd, ip, iface))
        return 1
    if cmd == 'add':
        subprocess.call(['arping', '-I', iface, '-A', ip, '-c', '10', '-w', '1'])
    return 0


def handle_public_ip(action, public_ip, pod_ip, iface, namespace, pod_spec_file):
    if action not in ('add', 'del',):
        glog('Unknown action for public ip. Skip call.')
        return 1
    if not os.path.exists(pod_spec_file):
        glog('Pod spec file is not exists. Skip call')
        return 2
    with open(pod_spec_file) as f:
        try:
            ports_s = json.load(f)['metadata']['annotations']['kuberdock-pod-ports']
            ports = json.loads(ports_s)
        except (TypeError, ValueError, KeyError) as e:
            glog('Error loading ports from spec "{0}" Skip call.'.format(e))
            return 3
    if not ports:
        return 4
    for container in ports:
        for port_spec in container:
            is_public = port_spec.get('isPublic', False)
            if not is_public:
                continue
            container_port = port_spec.get('containerPort')
            if not container_port:
                glog('Something went wrong and bad spec of pod has come. Skip')
                return 5
            proto = port_spec.get('protocol', 'tcp')
            host_port = port_spec.get('hostPort', None) or container_port
            if action == 'add':
                if subprocess.call(PUBLIC_IP_RULE.format('C', public_ip, proto, host_port, pod_ip, container_port).split(' ')):
                    subprocess.call(PUBLIC_IP_RULE.format('I', public_ip, proto, host_port, pod_ip, container_port).split(' '))
                if subprocess.call(PUBLIC_IP_MANGLE_RULE.format('C', public_ip, proto, host_port).split(' ')):
                    subprocess.call(PUBLIC_IP_MANGLE_RULE.format('I', public_ip, proto, host_port).split(' '))
            elif action == 'del':
                subprocess.call(PUBLIC_IP_RULE.format('D', public_ip, proto, host_port, pod_ip, container_port).split(' '))
                subprocess.call(PUBLIC_IP_MANGLE_RULE.format('D', public_ip, proto, host_port).split(' '))
    modify_ip(action, public_ip, iface)
    return 0


def init():
    config = get_config('/run/flannel/subnet.env')
    config_network = config['flannel_network']
    config_subnet = config['flannel_subnet']
    _update_ipset('kuberdock_flannel', [config_network], set_type='hash:net')
    _update_ipset('kuberdock_nodes', [])
    _update_ipset('kuberdock_cluster', ['kuberdock_flannel', 'kuberdock_nodes'],
                  set_type='list:set')
    network = ipaddress.ip_network(unicode(config_network))
    subnet = ipaddress.ip_network(unicode(config_subnet), strict=False)
    etcd = ETCD()
    for user in etcd.users():
        for pod in etcd.pods(user):
            pod_ip = ipaddress.ip_address(pod)
            if pod_ip not in network or pod_ip in subnet:
                etcd.delete(user, pod)
    update_ipset()


def watch(callback, args=None, path=None):
    if args is None:
        args = ()
    etcd = ETCD(path)
    while True:
        try:
            etcd.wait()
        except KeyboardInterrupt:
            break
        else:
            callback(*args)


def main(action, *args):
    if action == 'init':
        # TODO must be called after each restart service and flush/restore
        # correct iptables rules and chains (incl. public ip chains)
        init()
    elif action == 'setup':
        handle_public_ip('add', *args)
    elif action == 'teardown':
        handle_public_ip('del', *args)
    elif action == 'update':
        update_ipset()
    elif action == 'watch':
        watch(update_ipset)


if __name__ == '__main__':
    main(*sys.argv[1:])
