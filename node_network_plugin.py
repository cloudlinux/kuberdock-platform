#!/usr/bin/env python2

import re
import json
import subprocess
import sys
from ConfigParser import ConfigParser
from StringIO import StringIO

import ipaddress
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


PUBLIC_IP_RULE = 'iptables -w -{0} KUBERDOCK-PUBLIC-IP -t nat -d {1} ' \
                 '-p {2} --dport {3} -j DNAT --to-destination {4}:{3}'


class ETCD(object):
    ignore = ('createdIndex', 'dir', 'key', 'modifiedIndex')

    def __init__(self, path=None):
        config = get_config('/etc/sysconfig/flanneld')
        self.server = config['flannel_etcd']
        self.cert = config['etcd_certfile']
        self.key = config['etcd_keyfile']
        if path is None:
            path = '/'.join([config['flannel_etcd_key'].strip('/'), 'users'])
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
        for k, v in self._get(user).items():
            try:
                value = json.loads(v['value'])
            except ValueError:
                value = {'node': None, 'service': None}
            pods_list.append((k, value))
        pods = dict(pods_list)
        return pods

    def users(self):
        users = map(int, self._get())
        return users

    def delete(self, user, pod):
        requests.delete(self._url(user, pod), **self._args())

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
    shared_ips = ['10.254.0.10']
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
    _update_ipset('kuberdock_nodes', nodes_ips)


def get_ports_info(pod_uid):
    try:
        s = subprocess.check_output(['iptables', '-w', '-L', '-nt', 'nat'])
    except subprocess.CalledProcessError as e:
        print >> sys.stderr, e
        return []
    patt = re.compile(r'^DNAT .*/\* {0}.*/.*-public.* \*/ (.+) dpt:(\d+) .*$'
                      .format(pod_uid), re.MULTILINE)
    res = patt.findall(s.strip('\n'))
    return res


def modify_ip(cmd, ip, iface):
    if cmd not in ('add', 'del',):
        print >> sys.stderr, 'Unknown command for ip addr. Skip call.'
        return 1
    if subprocess.call(['ip', 'addr', cmd, ip + '/32', 'dev', iface]):
        print >> sys.stderr, 'Error {0} ip: {1} on iface: {2}'\
            .format(cmd, ip, iface)
        return 2
    if cmd == 'add':
        subprocess.call(['arping', '-I', iface, '-A', ip, '-c', '10', '-w', '1'])


def compose_public_ip_rule():
    pass


def setup_public_ip(public_ip, pod_ip, iface, namespace):
    ports = get_ports_info(namespace)
    for proto, port in ports:
        if subprocess.call(PUBLIC_IP_RULE.format('C', public_ip, proto, port, pod_ip, port).split(' ')):
            subprocess.call(PUBLIC_IP_RULE.format('A', public_ip, proto, port, pod_ip, port).split(' '))
    if ports:
        modify_ip('add', public_ip, iface)


def remove_public_ip(public_ip, pod_ip, iface, namespace):
    ports = get_ports_info(namespace)
    for proto, port in ports:
        subprocess.call(PUBLIC_IP_RULE.format('D', public_ip, proto, port, pod_ip, port).split(' '))
    if ports:
        modify_ip('del', public_ip, iface)


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


def _watcher(callback, args=None, path=None):
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


# TODO useless abstraction
def watch():
    _watcher(update_ipset)


def main(action, *args):
    if action == 'init':
        init()
    elif action == 'setup':
        setup_public_ip(*args)
    elif action == 'teardown':
        remove_public_ip(*args)
    elif action == 'update':
        update_ipset()
    elif action == 'watch':
        watch()


if __name__ == '__main__':
    main(*sys.argv[1:])
