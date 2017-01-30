#!/usr/bin/python

# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import json
from argparse import ArgumentParser, RawDescriptionHelpFormatter
import requests
import random
import string
from requests.auth import HTTPBasicAuth
import warnings
#import threading
import multiprocessing
import time
import logging
import subprocess
import sys
logging.basicConfig(level=logging.INFO)

urllib3_logger = logging.getLogger('urllib3')
urllib3_logger.setLevel(logging.CRITICAL)
requests_logger = logging.getLogger('requests.packages.urllib3.connectionpool')
requests_logger.setLevel(logging.CRITICAL)

_workloads = {}

ANNOTATION = r"""
For tests 'ab' and 'net' you may need to install packages: httpd-tools, iperf
Public IPs should be enabled to expose ports.

Example 1: run nginx pods with 64 user accounts:
{0} -t 1 -n 64 -c 1 -w nginx -u admin -p passw0rd -S --duration 300

Example 2: run nginx pods for 4 users and test with 32 ab concurrent connections:
{0} -t 1 --ab-concurrency 32 -n 4 -c 1 -w ab -u admin -p passw0rd -S --duration 300

Example 3: run 8 iperf pods and perform network throughput tests:
{0} -t 1 -n 8 -c 1 -w net -u admin -p passw0rd -S --duration 300

Example 4: Delete all test users after performing tests (may be dangerous on production cluster!)
{0} -u admin -p passw0rd --delete-all-test-users
""".format(sys.argv[0])

def api_resp_handler(resp):
    if resp.status_code != 200:
        logging.error("Response to {1} ({0}): {2}".format(resp.status_code,
                                                          resp.request.method,
                                                          resp.text))
    logging.info("Response to {1} ({0}) {2} took {3}s ".format(resp.status_code,
                                                             resp.request.method,
                                                             resp.request.url,
                                                             resp.elapsed.total_seconds()))
    logging.debug(resp.text)


class Workload(object):
    """
    Workload definition.
    :param object:
    :return:
    """
    def __init__(self, name, config_generator):
        self.config_generator = config_generator
        self.pods = []
    def misc_tests(self, args, user, pod_id):
        pass

def _process_args():
    parser = ArgumentParser("KuberDock test command line utilities",
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('-n', '--number', default=1, type=int, help="Number of users to create")
    parser.add_argument('-c', '--cycles', default=1, type=int, help="Number of cycles to run")
    parser.add_argument('-t', '--kube-type', default=1, type=int, help="Kube type")
    parser.add_argument('-w', '--workload', choices=_workloads.keys(), help="Test to perform")
    parser.add_argument('-u', '--user', default='admin', help="KuberDock admin user name")
    parser.add_argument('-p', '--password', default='admin', help="KuberDock admin user password")
    parser.add_argument('-H', '--host', default='https://127.0.0.1', help="KuberDock http url")
    parser.add_argument('-l', '--linear', action='store_true', help="linear mode")
    parser.add_argument('--ab-concurrency', action='store', type=int,
                        help='concurrency for ab (default=64)',default=64)
    parser.add_argument('-S', '--start', action='store_true', help="start a pod")
    parser.add_argument('--duration', type=int, action='store', help='duration in seconds (default=60)', default=60)
    parser.add_argument('--delete-all-test-users', action='store_true', help='delete all users with prefix "test"')
    parser.epilog = ANNOTATION
    return parser.parse_args()


def _get_workload(name):
    return _workloads[name] or None


def _compose_args(args, user=None, rest=False):
    params = {}
    if user is not None:
        params['auth'] = HTTPBasicAuth(user, user)
    else:
        params['auth'] = HTTPBasicAuth(args.user, args.password)
    if args.host.startswith('https'):
        params['verify'] = False
    if rest:
        params['headers'] = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    return params


def _get_pod(args, user, pod_id):
    params = _compose_args(args, user=user)
    r = requests.get(args.host.rstrip('/')+'/api/podapi/'+pod_id, **params).json()['data']
    return r

def _get_container_state(args, pod_id, container=0):
    params = _compose_args(args)
    resp = requests.get(args.host.rstrip('/')+'/api/podapi/'+pod_id, **params).json()
    state = resp['data']['containers'][container]['state']
    return state

def _wait_pod_active(args, user, pod_id):
    while _get_pod(args, user, pod_id)['status'] != "running":
        logging.info("Pod "+pod_id+": waiting for pod to become running")
        time.sleep(10)

def _generate_name(prefix='test', length=10):
    seq = string.lowercase + string.digits
    rnd = []
    for i in range(length):
        rnd.append(random.choice(seq))
    return prefix + ''.join(rnd)


def create_users(args):
    users = []
    params = _compose_args(args, rest=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for i in range(args.number):
            user = _generate_name()
            params['data'] = json.dumps({'username': user,
                              'password': user,
                              'email': user+'@'+user+'.com',
                              'package': 'Standard package',
                              'rolename': 'User',
                              'active': True})
            r = requests.post(args.host.rstrip('/')+'/api/users/all', **params)
            try:
                logging.debug(r.text)
                resp = r.json()
                if resp.get('status') == 'OK':
                    users.append({'name': resp['data']['username'], 'id': resp['data']['id']})
            except ValueError:
                pass
    return users

def _get_all_test_users(args):
    users = []
    params = _compose_args(args)
    r = requests.get(args.host.rstrip('/')+'/api/users/all', **params)
    resp = r.json()
    if resp.get('status') == 'OK':
        test_users = filter(lambda x: x['username'].startswith('test'), resp['data'])
        for u in test_users:
            users.append({'name': u['username'], 'id': u['id']})
    else:
        pass
    return users

def delete_users(users, args):
    params = _compose_args(args)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for u in users:
            r = requests.delete(args.host.rstrip('/')+'/api/users/all/'+str(u['id']), **params)
            api_resp_handler(r)


def _generate_config(args, user):
    random_string = _generate_name(prefix='')
    data = {
        'name': 'test-nginx-'+user+'-'+random_string,
        'volumes': [{'name':'var-cache-nginx'+random_string,'localStorage': True}],
        'replicas': 1,
        'restartPolicy': 'Always',
        'kube_type': args.kube_type,
        'containers': [
            {
                'args':['nginx', '-g', 'daemon off;'],
                'command':[],
                'env': [
                    {'name': 'PATH', 'value': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'},
                    {'name': 'NGINX_VERSION', 'value': '1.9.9-1~jessie'}],
                'image': 'nginx',
                'ports': [
                    {'containerPort': 443, 'protocol': 'tcp', 'isPublic': False},
                    {'containerPort': 80, 'protocol': 'tcp', 'isPublic': True}],
                'sourceUrl': 'hub.docker.com/_/nginx',
                'volumeMounts':[
                    {"name":"var-cache-nginx"+random_string, "mountPath":"/var/cache/nginx"}],
                'workingDir':'',
                "name": random_string,
                "kubes": 1,
                'terminationMessagePath': None}]}
    return json.dumps(data)

def _generate_io_config(args, user):
    random_string = _generate_name(prefix='')
    data = {
        'name': 'test-io-'+user+'-'+random_string,
        'volumes': [],
        'replicas': 1,
        'restartPolicy': 'Never',
        'kube_type': args.kube_type,
        'containers': [
            {
                'args':['bash', '-c',
                        'while true; do dd if=/dev/zero of=/zero bs=4M count=200;\
                        tar -cf /dev/null /; done'],
                'command':[],
                'env': [
                    {'name': 'PATH', 'value': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'},],
                'image': 'debian',
                'ports': [],
                'sourceUrl': 'hub.docker.com/_/debian',
                'volumeMounts':[],
                'workingDir':'',
                "name": random_string,
                "kubes": 1,
                'terminationMessagePath': None}]}
    return json.dumps(data)


def _generate_net_config(args, user):
    random_string = _generate_name(prefix='')
    data = {
        'name': 'test-net-'+user+'-'+random_string,
        'volumes': [],
        'kuberdock_resolve': [random_string+"s"],
        'replicas': 1,
        'restartPolicy': 'Always',
        'kube_type': args.kube_type,
        'containers': [
            {
                'args':["-s"],
                'command':["/usr/bin/iperf"],
                'env': [
                    {'name': 'PATH', 'value': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'},],
                'image': 'moutten/iperf',
                'ports': [{'containerPort': 5001,
                           'protocol': 'tcp',
                           'isPublic': True}],
                'sourceUrl': 'docker.io/moutten/iperf',
                'volumeMounts':[],
                'workingDir':'',
                "name": random_string+"s",
                "kubes": 1,
                'terminationMessagePath': None},
            {
                'args':["-c", random_string+"s"],
                'command':["/usr/bin/iperf"],
                'env': [
                    {'name': 'PATH', 'value': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'},],
                'image': 'moutten/iperf',
                'ports': [],
                'sourceUrl': 'docker.io/moutten/iperf',
                'volumeMounts':[],
                'workingDir':'',
                "name": random_string+"c",
                "kubes": 1,
                'terminationMessagePath': None},
            ]}
    return json.dumps(data)

def create_pod(args, user, config=None):
    params = _compose_args(args, user=user, rest=True)
    params['data'] = _generate_config(args, user) if not config else config
    r = requests.post(args.host.rstrip('/')+'/api/podapi', **params)
    api_resp_handler(r)
    try:
        rv = r.json()
        pod_id = rv.get('data', {}).get('id')
        return pod_id
    except ValueError:
        print r.text


def delete_pod(pod_id, args, user):
    params = _compose_args(args, user=user)
    r = requests.delete(args.host.rstrip('/')+'/api/podapi/'+pod_id, **params)
    api_resp_handler(r)
    try:
        if r.json().get('status') != 'OK':
            print "Could not delete pod {0}".format(pod_id)
    except ValueError:
        print r.text


def process_pods(args, user, workload):
    work = _get_workload(workload)
    if args.linear:
        pods = []
        for i in range(args.cycles):
            pod_id = create_pod(args, user, work.config_generator(args, user))
            if not pod_id:
                continue
            pods.append(pod_id)
        for i in pods:
            delete_pod(i, args, user)
    else:
        for i in range(args.cycles):
            logging.info("Creating pod for user {0}".format(user))
            pod_id = create_pod(args, user, work.config_generator(args, user))
            logging.info("Pod created (id={0})".format(pod_id))
            if pod_id is None:
                continue
            if args.start:
                params = _compose_args(args, user=user, rest=True)
                params['data'] = json.dumps({'command': 'start'})
                r = requests.put(args.host.rstrip('/')+'/api/podapi/'+pod_id, **params)
                api_resp_handler(r)
                work.misc_tests(args, user, pod_id)
                time.sleep(args.duration)
            delete_pod(pod_id, args, user)


# Simple workload definitions
# Just run nginx
_workloads.update({'nginx': Workload('nginx', _generate_config)})
# Run dd write for 800 mb then cyclic reads
_workloads.update({'io': Workload('io', _generate_io_config)})


# Workloads with additional actions
# Run Iperf network load test
class IperfWorkload(Workload):
    def misc_tests(self, args, user, pod_id):
        _wait_pod_active(args, user, pod_id)
        cmd = "iperf -d -t "+str(args.duration)+" -c "+_get_pod(args, user, pod_id)['public_ip']
        logging.info("Running: "+cmd)
        subprocess.Popen(cmd, shell=True)

_workloads.update({'net': IperfWorkload('net', _generate_net_config)})

# Run ab http load test
class AbWorkload(Workload):
    def misc_tests(self, args, user, pod_id):
        _wait_pod_active(args, user, pod_id)
        ip = _get_pod(args, user, pod_id)['public_ip']
        cmd = ' '.join(["ab -n 1000000 -c", str(args.ab_concurrency),
                        "http://"+ip+'/'])
        logging.info("Running: "+cmd)
        subprocess.Popen(cmd, shell=True)

_workloads.update({'ab': AbWorkload('ab', _generate_config)})


def main(args):
    threads = []
    if not args.host.startswith('http'):
        raise SystemExit('HTTP URL is expected for host parameter')

    if args.workload:
        users = create_users(args)
        for u in users:
            #t = threading.Thread(target=process_pods, args=(args, u['name']))
            t = multiprocessing.Process(target=process_pods, args=(args, u['name'], args.workload))
            t.start()
            threads.append(t)
        for t in threads: t.join()
        delete_users(users, args)
    if args.delete_all_test_users:
        params = _compose_args(args)
        delete_users(_get_all_test_users(params), params)

if __name__ == '__main__':
    args = _process_args()
    main(args)
