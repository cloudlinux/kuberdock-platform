import json
import string
import random
import re
import ipaddress
import shlex
import copy
from uuid import uuid4
from flask import Blueprint, request, current_app, jsonify, g
from flask.ext.login import current_user
from .. import tasks, signals
from ..models import User, Pod
from ..core import db, ssh_connect
from ..rbac import check_permission
from ..utils import update_dict, login_required_or_basic
from ..kubedata.kuberesolver import KubeResolver
from ..validation import check_new_pod_data, check_change_pod_data
from ..billing import kubes_to_limits
from ..api import APIError
from ..pods.models import PodIP
from ..settings import KUBE_API_VERSION
from .stream import send_event


ALLOWED_ACTIONS = ('start', 'stop', 'inspect',)

pods = Blueprint('pods', __name__, url_prefix='/pods')


@pods.route('/checkName', methods=['GET', 'POST'])
@login_required_or_basic
@check_permission('get', 'pods')
def check_pod_name():
    data = request.args
    pod = Pod.query.filter_by(name=data['name']).first()
    if pod:
        raise APIError("Conflict. Pod with name = '{0}' already exists. "
                       "Try another name.".format(data['name']),
                       status_code=409)
    return jsonify({'status': 'OK'})


@check_permission('get', 'pods')
def get_pods_collection():
    units = KubeResolver().resolve_all()
    try:
        user = current_user
        admin = user.is_administrator()
    except AttributeError:
        user = g.user
        admin = user.is_administrator()
    if admin:
        return units
    return filter((lambda x: x['owner'] == user.username), units)


@pods.route('/', methods=['GET'])
@login_required_or_basic
@check_permission('get', 'pods')
def get_pods():
    coll = get_pods_collection()
    return jsonify({'status': 'OK', 'data': coll})


@pods.route('/', methods=['POST'])
@login_required_or_basic
@check_permission('create', 'pods')
def create_item():
    data = request.json
    set_public_ip = data.pop('set_public_ip', None) == '1'
    public_ip = data.pop('freeHost', None)
    check_new_pod_data(data)
    pod = Pod.query.filter_by(name=data['name']).first()
    if pod:
        raise APIError("Conflict. Pod with name = '{0}' already exists. "
                       "Try another name.".format(data['name']),
                       status_code=409)

    item_id = make_item_id(data['name'])
    save_only = data.pop('save_only', True)
    temp_uuid = str(uuid4())
    data.update({'id': temp_uuid, 'status': 'stopped'})
    for container in data.get('containers', []):
        if container.get('command'):
            container['command'] = parse_cmd_string(container['command'][0])

    json_data = json.dumps(data)

    pod = Pod(name=data['name'], config=json_data, id=temp_uuid, status='stopped')
    try:
        pod.owner = current_user
    except AttributeError:
        pod.owner = g.user
    try:
        db.session.add(pod)
        db.session.commit()
    except Exception, e:
        db.session.rollback()
        raise APIError("Could not create database record for "
                       "'{0}'.".format(data['name']), status_code=409)
    if set_public_ip and public_ip:
        data['public_ip'] = public_ip
        try:
            signals.allocate_ip_address.send([temp_uuid, public_ip])
        except Exception, e:
            db.session.rollback()
            raise APIError(str(e), status_code=409)
    
    if not save_only:    # trying to run service and pods right away
        try:
            service_rv = json.loads(run_service(data))
        except TypeError:
            service_rv = None
        config = make_config(data, item_id)
        try:
            # TODO rename to "create pod" when refactor
            pod_rv = json.loads(tasks.create_containers_nodelay(config))
        except TypeError:
            pod_rv = None
        if 'status' in pod_rv and pod_rv['status'] == 'Working':
            current_app.logger.debug('WORKING')
            output = copy.deepcopy(data)
            output.update(prepare_for_output(None, service_rv))
        else:
            output = prepare_for_output(pod_rv, service_rv)

        try:
            pod = db.session.query(Pod).get(temp_uuid)
            pod.config = json.dumps(add_to_output(json.loads(pod.config),
                                                  output))
            output['id'] = temp_uuid
            db.session.commit()
        except Exception, e:
            current_app.logger.debug('DB_EXCEPTION:'+str(e))
            db.session.rollback()
            if data['service'] and service_rv is not None:
                srv = json.loads(service_rv)
                if 'id' in srv:
                    tasks.delete_service_nodelay(srv['id'])
        return jsonify({'status': 'OK', 'data': output})
    return jsonify({'status': 'OK', 'data': data})


@pods.route('/<string:uuid>', methods=['DELETE'])
@login_required_or_basic
@check_permission('delete', 'pods')
def delete_item(uuid):
    item = db.session.query(Pod).get(uuid)
    if item is None:
        raise APIError('No pod with id: {0}'.format(uuid), status_code=404)
    name = item.name
    
    try:
        parsed_config = json.loads(item.config)
    except (TypeError, ValueError):
        parsed_config = {}
        
    try:
        public_ip = parsed_config['labels']['kuberdock-public-ip']
        podip = PodIP.filter_by(
            ip_address=int(ipaddress.ip_address(public_ip)))
        podip.delete()
    except KeyError:
        pass
    if parsed_config.get('cluster'):
        replicas = tasks.get_replicas_nodelay()

        if 'items' not in replicas:
            return jsonify({'status': 'ERROR', 'reason': 'no items entry'})

        try:
            filtered_replicas = filter(
                (lambda x: x['desiredState']['replicaSelector']['name'] == name),
                replicas['items'])
            for replica in filtered_replicas:
                replica_rv = tasks.delete_replica_nodelay(replica['id'])
                if 'status' in replica_rv and replica_rv['status'].lower() not in ['success', 'working']:
                    return jsonify({'status': 'ERROR', 'reason': replica_rv['message']})
        except KeyError, e:
            return jsonify({'status': 'ERROR', 'reason': 'Key not found (%s)' % (e.message,)})

    pods = tasks.get_pods_nodelay()

    if 'items' not in pods:
        return jsonify({'status': 'ERROR', 'reason': 'no items entry'})

    try:
        filtered_pods = filter(
            (lambda x: 'labels' in x and x['labels']['name'] == name),
            pods['items'])
        for pod in filtered_pods:
            pod_rv = tasks.delete_pod_nodelay(pod['id'])
            if 'status' in pod_rv and pod_rv['status'].lower() not in ['success', 'working']:
                return jsonify({'status': 'ERROR', 'reason': pod_rv['message']})
    except KeyError, e:
        return jsonify({'status': 'ERROR', 'reason': 'Key not found (%s)' % (e.message,)})

    if parsed_config.get('service'):
        services = tasks.get_services_nodelay()

        if 'items' not in services:
            return jsonify({'status': 'ERROR', 'reason': 'no items entry'})

        try:
            filtered_services = filter(
                (lambda x: is_related(x['selector'], {'name': name})),
                services['items'])
            for service in filtered_services:
                service_rv = tasks.delete_service_nodelay(service['id'])
                if 'status' in service_rv and service_rv['status'].lower() not in ['success', 'working']:
                    return jsonify({'status': 'ERROR', 'reason': service_rv['message']})
        except KeyError, e:
            return jsonify({'status': 'ERROR', 'reason': 'Key not found (%s)' % (e.message,)})

    item.name += ('__' + ''.join(random.sample(string.lowercase + string.digits, 8)))
    item.status = 'deleted'
    db.session.commit()
    return jsonify({'status': 'OK'})


@pods.route('/<string:uuid>', methods=['PUT', 'POST'])
@login_required_or_basic
@check_permission('edit', 'pods')
def update_item(uuid):
    response = {}
    item = db.session.query(Pod).get(uuid)
    try:
        username = current_user.username
    except AttributeError:
        username = g.user.username
    u = db.session.query(User).filter_by(username=username).first()
    if item is None:
        raise APIError('Pod not found', 404)
    data = request.json
    # Dirty workaround. This field even must not be here!
    data.pop('freeHost', None)
    check_change_pod_data(data)

    if 'dbdiff' in data:
        update_dict(item.__dict__, data['dbdiff'])
        try:
            db.session.add(item)
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({'status': 'ERROR', 'reason': 'Error updating database entry'})
    
    try:
        parsed_config = json.loads(item.config)
    except (TypeError, ValueError):
        parsed_config = {}

    if 'command' in data:
        if data['command'] == 'start':

            if parsed_config.get('cluster'):
                if is_alive(item.name):
                    # TODO check replica numbers and compare to ones set in config
                    resize_replica(item.name, parsed_config['replicas'])
                else:
                    return jsonify({'status': 'OK', 'data': start_cluster(data)})


            else:
                item_id = make_item_id(item.name)
                service_rv = run_service(data)
                config = make_config(parsed_config, item_id)
                pod_rv = tasks.create_containers_nodelay(config)
                output = prepare_for_output(pod_rv, service_rv)

                try:
                    pod = Pod(name=output['name'],
                              config=json.dumps(add_to_output(parsed_config, output)),
                              id=output['id'], owner=u)
                    db.session.add(pod)
                    db.session.delete(item)
                    db.session.commit()
                    response = {'id': output['id']}
                except Exception, e:
                    db.session.rollback()
                    if type(service_rv) is str or type(service_rv) is unicode:
                        srv = json.loads(service_rv)
                        if 'id' in srv:
                            tasks.delete_service_nodelay(srv['id'])
        elif data['command'] == 'stop':
            if parsed_config.get('cluster'):
                resize_replica(item.name, 0)
                response['data'] = {'status': 'Stopped'}
            else:
                pods = tasks.get_pods_nodelay()

                if 'items' not in pods:
                    return jsonify({'status': 'ERROR', 'reason': 'no items entry'})

                try:
                    filtered_pods = filter(
                        (lambda x: 'labels' in x and x['labels']['name'] == item.name),
                        pods['items'])
                    for pod in filtered_pods:
                        pod_rv = tasks.delete_pod_nodelay(pod['id'])
                        if 'status' in pod_rv and pod_rv['status'].lower() not in ['success', 'working']:
                            return jsonify({'status': 'ERROR', 'reason': pod_rv['message']})
                except KeyError, e:
                    return jsonify({'status': 'ERROR', 'reason': 'Key not found (%s)' % (e.message,)})
        elif data['command'] == 'resize':
            replicas = int(data['replicas'])
            resize_replica(item.name, replicas)
        else:
            return jsonify({'status': 'ERROR', 'reason': 'Unknown command'})
    response.update({'status': 'OK'})
    return jsonify(response)


def do_action(host, action, container_id):
    ssh, error_message = ssh_connect(host)
    if error_message:
        raise APIError(error_message)
    i, o, e = ssh.exec_command(
        'docker {0} {1}'.format(action, container_id.lstrip('docker://')))
    exit_status = o.channel.recv_exit_status()
    if exit_status != 0:
        raise APIError('Docker error. Exit status: {0}. Error: {1}'
               .format(exit_status, e.read()))
    else:
        message = o.read()
        if action in ('start', 'stop'):
            send_event('pull_pod_state', message)
        ssh.close()
        return message or 'OK'


@pods.route('/containers', methods=['PUT'])
@login_required_or_basic
@check_permission('edit', 'pods')
def docker_action():
    data = request.json or request.args or request.form
    try:
        user = current_user
    except AttributeError:
        user = g.user
    action = data.get('action')
    host = data.get('host')
    containers = data.get('containers', '').split(',')

    if action not in ALLOWED_ACTIONS:
        raise APIError('This action is not allowed.', status_code=403)
    if not host:
        raise APIError('Node host is not provided')
    pod = db.session.query(Pod).get(data.get('pod_uuid'))
    if pod is None:
        raise APIError('Pod not found', status_code=404)
    
    try:
        parsed_config = json.loads(pod.config)
    except (TypeError, ValueError):
        parsed_config = {}
    
    if pod.owner != user:
        raise APIError("You may do actions only on your own Pods",
                       status_code=403)
    if parsed_config.get('cluster'):
        if action != 'inspect':     # special cases here
            raise APIError('This action is not allowed for replicated PODs',
                           status_code=403)
    if parsed_config.get('restartPolicy') == 'always' \
            and action in ('start', 'stop'):
        raise APIError("POD with restart policy 'Always' can't "
                       "start or stop containers")
    # TODO validate containerId (escape) and his presents for different commands
    if containers:
        result = {cid: do_action(host, action, cid) for cid in containers}
    else:
        result = do_action(data['host'], data['action'], data['containerId'])
    return jsonify({'status': 'OK', 'data': result})


def run_service(data):
    if not data.get('service'):
        return
    dash_name = '-'.join(re.split(r'[\s\\/\[\|\]{}\(\)\._]+', data['name']))
    s = string.lowercase
    item_id = s[random.randrange(len(s))] +\
        ''.join(random.sample(s + string.digits, 19))
    conf = {
        'kind': 'Service',
        'apiVersion': KUBE_API_VERSION,
        'id': item_id,
        'selector': {'name': data['name']},
        'port': int(data['port']),
        'labels': {'name': dash_name + '-service'}
    }
    return tasks.create_service_nodelay(conf)


def parse_cmd_string(s):
    lex = shlex.shlex(s, posix=True)
    lex.whitespace_split = True
    lex.commenters = ''
    lex.wordchars += '.'
    return list(lex)


def prepare_container(data, key='ports', kube_type=0):
    a = []
    # if container name is missing generate from image
    if 'name' not in data or not data['name']:
        image = '-'.join(map((lambda x: x.lower()), data['image'].split('/')))
        data['name'] = "%s-%s" % (
            image, ''.join(random.sample(string.lowercase + string.digits, 10)))

    try:
        kubes = int(data.pop('kubes'))
    except (KeyError, ValueError):
        pass
    else:   # if we create pod, not start stopped
        data.update(kubes_to_limits(kubes, kube_type))

    # convert to int ports values
    data.setdefault(key, [])
    for t in data[key]:
        try:
            a.append(dict([
                (i[0], int( i[1])) for i in t.items()
            ]))
        except ValueError:
            a.append(dict([
                i for i in t.items()
            ]))

    wd = data.get('workingDir', '.')
    if type(wd) is list:
        data['workingDir'] = ','.join(data['workingDir'])

    data[key] = a
    return data


def prepare_for_output(rv=None, s_rv=None):
    out = {}
    if rv is not None:
        try:
            # Ugly workaround. Wants thorough consideration
            if type(rv) is unicode or type(rv) is str:
                rv = json.loads(rv)
            if rv['kind'] == 'ReplicationController':
                out['cluster'] = True
                out['name'] = rv['desiredState']['replicaSelector']['name']
                out['status'] = 'unknown'
            elif rv['kind'] == 'Pod':
                out['cluster'] = False
                out['name'] = rv['labels']['name']
                out['labels'] = rv['labels']
                out['status'] = rv['currentState']['status'].lower()
            else:
                return out

            out['id'] = rv['uid']

            try:
                root = rv['desiredState']['podTemplate']['desiredState']['manifest']
            except KeyError:
                root = rv['desiredState']['manifest']

            for k in 'containers', 'restartPolicy', 'volumes':
                out[k] = root[k]

            out['replicas'] = 1
            if 'replicas' in rv['desiredState']:
                out['replicas'] = rv['desiredState']['replicas']

        except (ValueError, TypeError, KeyError): # Failed to process JSON
            pass

    if s_rv is None:
        return out

    try:
        if s_rv['kind'] == 'Service':
            out['service'] = True
        else:
            out['service'] = False

        for k in 'port', 'containerPort', 'portalIP':
            try:
                out[k] = s_rv[k]
            except KeyError:
                continue

    except (ValueError, TypeError, KeyError):
        pass
    return out


def make_pod_config(data, sid, separate=True):
    # separate=True means that this is just a pod, not replica
    # to insert config into replicas config set separate to False
    inner = {'version': KUBE_API_VERSION}
    if separate:
        inner['id'] = sid
        inner['restartPolicy'] = data['restartPolicy']
    inner['volumes'] = data['volumes']
    kube_type = data.get('kube_type', 0)
    inner['containers'] =\
        [prepare_container(cont, kube_type=kube_type) for cont in data['containers']]
    outer = {}
    if separate:
        outer['kind'] = 'Pod'
        outer['apiVersion'] = KUBE_API_VERSION
        outer['id'] = sid
        outer['nodeSelector'] = {
            'kuberdock-kube-type': 'type_' + str(kube_type)
        }
        if 'node' in data and data['node'] is not None:
            outer['nodeSelector']['kuberdock-node-hostname'] = data['node']
    outer['desiredState'] = {'manifest': inner}
    if 'labels' not in data:
        outer['labels'] = {'name': data['name']}
        if 'public_ip' in data:
            outer['labels']['kuberdock-public-ip'] = data.pop('public_ip')
    else:
        outer['labels'] = data['labels']
    return outer


def make_config(data, sid=None):
    if sid is None:
        sid = data['sid']
    dash_name = '-'.join(re.split(r'[\s\\/\[\|\]{}\(\)\._]+', data['name']))
    cluster = data['cluster']

    # generate replicationController config
    if not cluster:
        return make_pod_config(data, sid)
    return {
        'kind': 'ReplicationController',
        'apiVersion': KUBE_API_VERSION,
        'id': sid,
        'desiredState': {
            'replicas': data['replicas'],
            'replicaSelector': {'name': data['name']},
            'podTemplate': make_pod_config(data, sid, False),
        },
        'labels': {'name': dash_name + '-cluster'}
    }


def make_item_id(item_name):
    item_id = ''.join(map((lambda x: x.lower()), re.split(r'[\s\\/\[\|\]{}\(\)\._]+', item_name)))
    item_id += ''.join(random.sample(string.lowercase + string.digits, 20))
    return item_id


def resize_replica(name, num):
    diff = {'desiredState': {'replicas': num}}
    replicas = tasks.get_replicas_nodelay()
    filtered_replicas = filter(
        (lambda x: x['desiredState']['replicaSelector']['name'] == name),
        replicas['items'])
    for replica in filtered_replicas:
        tasks.update_replica_nodelay(replica['id'], diff)


def is_related(one, two):
    if one is None or two is None:
        return False
    for k in two.keys():
        if k not in one:
            return False
        if one[k] != two[k]:
            return False
        return True


def is_alive(name):
    if KubeResolver().resolve_by_replica_name(name):
        return True
    return False


def start_cluster(data):
    item_id = make_item_id(data['name'])
    rv = {}
    try:
        service_rv = json.loads(run_service(data))
        if 'kind' in service_rv and service_rv['kind'] == 'Service':
            rv['service_ok'] = True
            rv['portalIP'] = service_rv['portalIP']
    except TypeError:
        rv['service_ok'] = False
    except KeyError:
        rv['portalIP'] = None

    config = make_config(data, item_id)

    try:
        pod_rv = json.loads(tasks.create_containers_nodelay(config))
        if 'kind' in pod_rv and pod_rv['kind'] == 'ReplicationController':
            rv['replica_ok'] = True
            rv['replicas'] = pod_rv['desiredState']['replicas']
    except TypeError:
        rv['replica_ok'] = False
    except KeyError:
        rv['replicas'] = 0
    if rv['service_ok'] and rv['replica_ok']:
        rv['status'] = 'Running'
        rv.pop('service_ok')
        rv.pop('replica_ok')
    return rv


def add_to_output(old_config, old_output):
    old_output['kube_type'] = old_config['kube_type']
    conf_containers = old_config.get('containers')
    kub_containers = old_output.get('containers')
    if conf_containers and kub_containers:
        for c_container, k_container in zip(conf_containers, kub_containers):
            k_container['kubes'] = c_container['kubes']
    return old_output
