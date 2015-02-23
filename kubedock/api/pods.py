from flask import Blueprint, request, current_app, jsonify
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
from ..validation import check_pod_data
from ..api import APIError
import copy

ALLOWED_ACTIONS = ('start', 'stop', 'inspect',)

pods = Blueprint('pods', __name__, url_prefix='/pods')


@pods.route('/', methods=['POST'])
@login_required_or_basic
@check_permission('create', 'pods')
def create_item():
    data = request.json
    check_pod_data(data)
    pod = Pod.query.filter_by(name=data['name']).first()
    if pod:
        raise APIError("Conflict. Pod with name = '{0}' already exists. "
                       "Try another name.".format(data['name']),
                       status_code=409)

    item_id = make_item_id(data['name'])
    save_only = data.pop('save_only', True)
    kubes = data.pop('kubes', 1)
    temp_uuid = str(uuid4())
    data.update({'id': temp_uuid, 'status': 'stopped'})
    pod = Pod(name=data['name'], kubes=kubes, config=data, id=temp_uuid, status='stopped')
    pod.owner = current_user
    try:
        db.session.add(pod)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise APIError("Could not create database record for '{0}'.".format(data['name']),
                       status_code=409)
    
    if not save_only:    # trying to run service and pods right away
        try:
            service_rv = json.loads(run_service(data))
        except TypeError:
            service_rv = None
        config = make_config(data, item_id)
        result = tasks.create_containers.delay(config)
        try:
            pod_rv = json.loads(result.wait())
        except TypeError:
            pod_rv = None
        if 'status' in pod_rv and pod_rv['status'] == 'Working':
            current_app.logger.debug('WORKING')
            output = copy.deepcopy(data)
            output.update(prepare_for_output(None, service_rv))
        else:
            output = prepare_for_output(pod_rv, service_rv)
        output['kubes'] = kubes

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
                    result = tasks.delete_service.delay(srv['id'])
                    result.wait()
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
        result = tasks.get_replicas.delay()
        replicas = result.wait()

        if 'items' not in replicas:
            return jsonify({'status': 'ERROR', 'reason': 'no items entry'})

        try:
            filtered_replicas = filter(
                (lambda x: x['desiredState']['replicaSelector']['name'] == name),
                replicas['items'])
            for replica in filtered_replicas:
                result = tasks.delete_replica.delay(replica['id'])
                current_app.logger.debug(result)
                replica_rv = result.wait()
                current_app.logger.debug(replica_rv)
                if 'status' in replica_rv and replica_rv['status'].lower() not in ['success', 'working']:
                    return jsonify({'status': 'ERROR', 'reason': replica_rv['message']})
        except KeyError, e:
            return jsonify({'status': 'ERROR', 'reason': 'Key not found (%s)' % (e.message,)})

    result = tasks.get_pods.delay()
    pods = result.wait()

    if 'items' not in pods:
        return jsonify({'status': 'ERROR', 'reason': 'no items entry'})

    try:
        filtered_pods = filter(
            (lambda x: x['labels']['name'] == name),
            pods['items'])
        for pod in filtered_pods:
            result = tasks.delete_pod.delay(pod['id'])
            pod_rv = result.wait()
            current_app.logger.debug(pod_rv)
            if 'status' in pod_rv and pod_rv['status'].lower() not in ['success', 'working']:
                return jsonify({'status': 'ERROR', 'reason': pod_rv['message']})
    except KeyError, e:
        return jsonify({'status': 'ERROR', 'reason': 'Key not found (%s)' % (e.message,)})

    if item.config.get('service'):
        result = tasks.get_services.delay()
        services = result.wait()

        if 'items' not in services:
            return jsonify({'status': 'ERROR', 'reason': 'no items entry'})

        try:
            filtered_services = filter(
                (lambda x: is_related(x['selector'], {'name': name})),
                services['items'])
            for service in filtered_services:
                result = tasks.delete_service.delay(service['id'])
                service_rv = result.wait()
                current_app.logger.debug(service_rv)
                if 'status' in service_rv and service_rv['status'].lower() not in ['success', 'working']:
                    return jsonify({'status': 'ERROR', 'reason': service_rv['message']})
        except KeyError, e:
            return jsonify({'status': 'ERROR', 'reason': 'Key not found (%s)' % (e.message,)})

    item.name += ('__' + ''.join(random.sample(string.lowercase + string.digits, 8)))
    item.status = 'deleted'
    db.session.commit()
    return jsonify({'status': 'OK'})


@pods.route('/<string:uuid>', methods=['PUT'])
@login_required_or_basic
@check_permission('edit', 'pods')
def update_item(uuid):
    response = {}
    item = db.session.query(Pod).get(uuid)
    u = db.session.query(User).filter_by(username=current_user.username).first()
    if item is None:
        raise APIError('Pod not found', 404)
    data = request.json
    check_pod_data(data)
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
                result = tasks.create_containers.delay(config)
                pod_rv = result.wait()
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
                            result = tasks.delete_service.delay(srv['id'])
                            result.wait()
        elif data['command'] == 'stop':
            if item.config['cluster']:
                resize_replica(item.name, 0)
                response['data'] = {'status': 'Stopped'}
            else:
                result = tasks.get_pods.delay()
                pods = result.wait()

                if 'items' not in pods:
                    return jsonify({'status': 'ERROR', 'reason': 'no items entry'})

                try:
                    filtered_pods = filter(
                        (lambda x: x['labels']['name'] == item.name),
                        pods['items'])
                    for pod in filtered_pods:
                        result = tasks.delete_pod.delay(pod['id'])
                        pod_rv = result.wait()
                        current_app.logger.debug(pod_rv)
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
        raise APIError('Docker error. Exit status: {0}. Error: {1}'.format(exit_status, e.read()))
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
    task = tasks.create_service.delay(conf)
    return task.wait()


def prepare_container(data, key='ports'):
    a = []
    # if container name is missing generate from image
    if 'name' not in data or not data['name']:
        image = '-'.join(map((lambda x: x.lower()), data['image'].split('/')))
        data['name'] = "%s-%s" % (
            image, ''.join(random.sample(string.lowercase + string.digits, 10)))

    # convert to int cpu and memory data or delete'em entirely if invalid
    for i in 'cpu', 'memory':
        try:
            data[i] = int(data[i])
        except (TypeError, ValueError):
            data.pop(i)
        except KeyError:
            continue

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

    if type(data['workingDir']) is list:
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
    outer['desiredState'] = {'manifest': inner}
    outer['labels'] = {'name': data['name']}
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
    result = tasks.get_replicas.delay()
    replicas = result.wait()
    filtered_replicas = filter(
        (lambda x: x['desiredState']['replicaSelector']['name'] == name),
        replicas['items'])
    for replica in filtered_replicas:
        tasks.update_replica.delay(replica['id'], diff).wait()


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

    result = tasks.create_containers.delay(config)
    try:
        pod_rv = json.loads(result.wait())
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