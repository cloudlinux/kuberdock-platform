from flask import Blueprint, request, current_app, jsonify, g
from flask.ext.login import current_user
from .. import tasks
import json
from uuid import uuid4
import string
import random
import re
from ..models import User, Pod
from ..core import db, check_permission, ssh_connect
from .stream import send_event
from ..utils import update_dict, login_required_or_basic
from ..kubedata.kuberesolver import KubeResolver
from ..validation import check_new_pod_data, check_change_pod_data
from ..billing import kubes_to_limits
from ..api import APIError
from .. import signals
import copy

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
def get_pods_collection(user):
    units = KubeResolver().resolve_all()
    if user.is_administrator():
        return units
    return filter((lambda x: x['owner'] == user.username), units)


@pods.route('/', methods=['GET'])
@login_required_or_basic
@check_permission('get', 'pods')
def get_pods():
    try:
        coll = get_pods_collection(current_user)
    except AttributeError:
        coll = get_pods_collection(g.user)
    return jsonify({'status': 'OK', 'data': coll})


@pods.route('/', methods=['POST'])
@login_required_or_basic
@check_permission('create', 'pods')
def create_item():
    data = request.json
    set_public_ip = data.pop('set_public_ip', None) == '1'
    public_ip = data.pop('free_host', None)
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
    pod = Pod(name=data['name'], config=data, id=temp_uuid, status='stopped')
    pod.owner = current_user
    try:
        db.session.add(pod)
        db.session.commit()
    except Exception:
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
            pod.config = output
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
    if item.config.get('cluster'):
        replicas = tasks.get_replicas_nodelay()

        if 'items' not in replicas:
            return jsonify({'status': 'ERROR', 'reason': 'no items entry'})

        try:
            filtered_replicas = filter(
                (lambda x: x['desiredState']['replicaSelector']['name'] == name),
                replicas['items'])
            for replica in filtered_replicas:
                replica_rv = tasks.delete_replica_nodelay(replica['id'])
                current_app.logger.debug(replica_rv)
                if 'status' in replica_rv and replica_rv['status'].lower() not in ['success', 'working']:
                    return jsonify({'status': 'ERROR', 'reason': replica_rv['message']})
        except KeyError, e:
            return jsonify({'status': 'ERROR', 'reason': 'Key not found (%s)' % (e.message,)})

    pods = tasks.get_pods_nodelay()

    if 'items' not in pods:
        return jsonify({'status': 'ERROR', 'reason': 'no items entry'})

    try:
        filtered_pods = filter(
            (lambda x: x['labels']['name'] == name),
            pods['items'])
        for pod in filtered_pods:
            pod_rv = tasks.delete_pod_nodelay(pod['id'])
            current_app.logger.debug(pod_rv)
            if 'status' in pod_rv and pod_rv['status'].lower() not in ['success', 'working']:
                return jsonify({'status': 'ERROR', 'reason': pod_rv['message']})
    except KeyError, e:
        return jsonify({'status': 'ERROR', 'reason': 'Key not found (%s)' % (e.message,)})

    if item.config.get('service'):
        services = tasks.get_services_nodelay()

        if 'items' not in services:
            return jsonify({'status': 'ERROR', 'reason': 'no items entry'})

        try:
            filtered_services = filter(
                (lambda x: is_related(x['selector'], {'name': name})),
                services['items'])
            for service in filtered_services:
                service_rv = tasks.delete_service_nodelay(service['id'])
                current_app.logger.debug(service_rv)
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
    u = db.session.query(User).filter_by(username=current_user.username).first()
    if item is None:
        raise APIError('Pod not found', 404)
    data = request.json
    # TODO: sart|stop|terminate actions for containers
    containers = data.get('containers')
    check_change_pod_data(data)
    if 'dbdiff' in data:
        update_dict(item.__dict__, data['dbdiff'])
        try:
            db.session.add(item)
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({'status': 'ERROR', 'reason': 'Error updating database entry'})

    if 'command' in data:
        if data['command'] == 'start':

            if item.config['cluster']:
                if is_alive(item.name):
                    # TODO check replica numbers and compare to ones set in config
                    resize_replica(item.name, item.config['replicas'])
                else:
                    return jsonify({'status': 'OK', 'data': start_cluster(data)})


            else:
                item_id = make_item_id(item.name)
                service_rv = run_service(data)
                config = make_config(item.config, item_id)
                current_app.logger.debug(config)
                pod_rv = tasks.create_containers_nodelay(config)
                output = prepare_for_output(pod_rv, service_rv)

                try:
                    pod = Pod(name=output['name'], config=output, id=output['id'], owner=u)
                    db.session.add(pod)
                    db.session.delete(item)
                    db.session.commit()
                    response = {'id': output['id']}
                except Exception:
                    current_app.logger.debug(output)
                    db.session.rollback()
                    if service_rv is not None:
                        srv = json.loads(service_rv)
                        if 'id' in srv:
                            tasks.delete_service_nodelay(srv['id'])
        elif data['command'] == 'stop':
            if item.config['cluster']:
                resize_replica(item.name, 0)
                response['data'] = {'status': 'Stopped'}
            else:
                pods = tasks.get_pods_nodelay()

                if 'items' not in pods:
                    return jsonify({'status': 'ERROR', 'reason': 'no items entry'})

                try:
                    filtered_pods = filter(
                        (lambda x: x['labels']['name'] == item.name),
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
    i, o, e = ssh.exec_command('docker {0} {1}'.format(action, container_id))
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
    data = request.json
    action = data.get('action')
    if action not in ALLOWED_ACTIONS:
        raise APIError('This action is not allowed.', status_code=403)
    if not data.get('host'):
        raise APIError('Node host is not provided')
    pod = db.session.query(Pod).get(data.get('pod_uuid'))
    if pod is None:
        raise APIError('Pod not found', status_code=404)
    if pod.owner != current_user:
        raise APIError("You may do actions only on your own Pods",
                       status_code=403)
    if pod.config.get('cluster'):
        if action != 'inspect':     # special cases here
            raise APIError('This action is not allowed for replicated PODs',
                           status_code=403)
    if pod.config.get('restartPolicy') == 'always' \
            and action in ('start', 'stop'):
        raise APIError("POD with restart policy 'Always' can't "
                       "start or stop containers")
    # TODO validate containerId (escape) and his presents for different commands
    return jsonify({
        'status': 'OK',
        'data': do_action(data['host'], data['action'], data['containerId'])})


def run_service(data):
    if not data['service']:
        return
    dash_name = '-'.join(re.split(r'[\s\\/\[\|\]{}\(\)\._]+', data['name']))
    s = string.lowercase
    item_id = s[random.randrange(len(s))] +\
        ''.join(random.sample(s + string.digits, 19))
    conf = {
        'kind': 'Service',
        'apiVersion': 'v1beta2',
        'id': item_id,
        'selector': {'name': data['name']},
        'port': int(data['port']),
        'labels': {'name': dash_name + '-service'}
    }
    return tasks.create_service_nodelay(conf)


def prepare_container(data, key='ports'):
    a = []
    # if container name is missing generate from image
    if 'name' not in data or not data['name']:
        image = '-'.join(map((lambda x: x.lower()), data['image'].split('/')))
        data['name'] = "%s-%s" % (
            image, ''.join(random.sample(string.lowercase + string.digits, 10)))

    try:
        kubes = int(data.pop('kubes'))
    except (KeyError, ValueError):
        kubes = 1
    kube_type = 0   # mock
    data.update(kubes_to_limits(kubes, kube_type, version='v1beta1'))

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
            if rv['kind'] == 'ReplicationController':
                out['cluster'] = True
                out['name'] = rv['desiredState']['replicaSelector']['name']
                out['status'] = 'unknown'
            elif rv['kind'] == 'Pod':
                out['cluster'] = False
                out['name'] = rv['labels']['name']
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

        except (ValueError, TypeError), e: # Failed to process JSON
            current_app.logger.debug(str(e))
            return out

        except KeyError, e:
            current_app.logger.debug(str(e))
            current_app.logger.debug(rv)
            return out

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

    except (ValueError, TypeError), e: # Failed to process JSON
        return out
    except KeyError:
        return out
    return out


def make_pod_config(data, sid, separate=True):
    # separate=True means that this is just a pod, not replica
    # to insert config into replicas config set separate to False
    inner = {'version': 'v1beta1'}
    if separate:
        inner['id'] = sid
        inner['restartPolicy'] = data['restartPolicy']
    inner['volumes'] = data['volumes']
    inner['containers'] = map(prepare_container, data['containers'])
    outer = {}
    if separate:
        outer['kind'] = 'Pod'
        outer['apiVersion'] = 'v1beta1'
        outer['id'] = sid
        if 'node' in data and data['node'] is not None:
            outer['nodeSelector'] = {'kuberdock-node-hostname': data['node']}
    outer['desiredState'] = {'manifest': inner}
    outer['labels'] = {'name': data['name']}
    if 'public_ip' in data:
        outer['labels']['kuberdock-public-ip'] = data.pop('public_ip')
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
        'apiVersion': 'v1beta2',
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