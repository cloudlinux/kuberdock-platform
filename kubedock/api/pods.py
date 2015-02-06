from flask import Blueprint, request, current_app, jsonify
from flask.ext.login import current_user
from .. import tasks
import json
from collections import OrderedDict
from uuid import uuid4
import string
import random
import re
from ..models import User, Pod
from ..core import db, check_permission
from ..utils import update_dict, login_required_or_basic
from ..validation import check_pod_data
from ..api import APIError


pods = Blueprint('pods', __name__, url_prefix='/pods')


@pods.route('/', methods=['POST'])
@login_required_or_basic
@check_permission('create', 'pods')
def create_item():
    data = request.json
    check_pod_data(data)
    pod = Pod.query.filter_by(name=data['name']).first()
    if pod:
        raise APIError("Conflict. Pod with name = '{0}' already exists. Try another name.".format(data['name']),
                       status_code=409)
    item_id = make_item_id(data['name'])
    runnable = data.pop('runnable', False)
    kubes = data.pop('kubes', 1)
    temp_uuid = str(uuid4())
    
    u = db.session.query(User).filter_by(username=current_user.username).first()
    data.update({'id': temp_uuid, 'status': 'stopped'})
    pod = Pod(name=data['name'], kubes=kubes, config=data, id=temp_uuid, status='stopped')
    pod.owner = u
    try:
        db.session.add(pod)
        db.session.commit()
    except Exception:
        db.session.rollback()
    
    if runnable:    # trying to run service and pods right away
        service_rv = run_service(data)
        config = make_config(data, item_id)
        
        #current_app.logger.debug(config)
        result = tasks.create_containers.delay(config)
        pod_rv = result.wait()
        output = prepare_for_output(pod_rv, service_rv)
        output['kubes'] = kubes
    
        try:
            pod = Pod(name=output['name'], kubes=kubes, config=output, id=output['id'])
            pod.owner = u
            db.session.add(pod)
            pending_pod = db.session.query(Pod).get(temp_uuid)
            db.session.delete(pending_pod)
            db.session.commit()
        except Exception:
            #current_app.logger.debug(output)
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
        return jsonify({'status': 'ERROR'})
    name = item.name
    if item.config['cluster']:
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
                #current_app.logger.debug(result)
                replica_rv = result.wait()
                #current_app.logger.debug(replica_rv)
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
            #current_app.logger.debug(pod_rv)
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
                #current_app.logger.debug(service_rv)
                if 'status' in service_rv and service_rv['status'].lower() not in ['success', 'working']:
                    return jsonify({'status': 'ERROR', 'reason': service_rv['message']})
        except KeyError, e:
            return jsonify({'status': 'ERROR', 'reason': 'Key not found (%s)' % (e.message,)})
    
    db.session.delete(item)
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
                resize_replica(item.name, item.config['replicas'])
            else:
                item_id = make_item_id(item.name)
                service_rv = run_service(data)
                config = make_config(item.config, item_id)
                #current_app.logger.debug(config)
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
                    #current_app.logger.debug(output)
                    db.session.rollback()
                    if service_rv is not None:
                        srv = json.loads(service_rv)
                        if 'id' in srv:
                            result = tasks.delete_service.delay(srv['id'])
                            result.wait()
        elif data['command'] == 'stop':
            if item.config['cluster']:
                resize_replica(item.name, 0)
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
                        #current_app.logger.debug(pod_rv)
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

def run_service(data):
    if not data['service']:
        return
    dash_name = '-'.join(re.split(r'[\s\\/\[\|\]{}\(\)\._]+', data['name']))
    s = string.lowercase
    item_id = s[random.randrange(len(s))] + ''.join(random.sample(s + string.digits, 19))
    conf = OrderedDict([
        ('kind', 'Service'),
        ('apiVersion', 'v1beta2'),
        ('id', item_id),
        ('selector', dict([
            ('name', data['name'])
        ])),
        ('port', int(data['port'])),
        ('labels', dict([
            ('name', dash_name + '-service')
        ])),
    ])
    task = tasks.create_service.delay(conf)
    return task.wait()
            
def prepare_container(data, key='ports'):
    a=[]
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
    #current_app.logger.debug(data[key])
    return data

def prepare_for_output(rv, s_rv=None):
    #current_app.logger.debug(rv)
    #current_app.logger.debug(s_rv)
    out = {}
    try:
        rv = json.loads(rv)

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
        s_rv = json.loads(s_rv)
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
    # to insert config into peplicas config set separate to False
    inner = [('version', 'v1beta1')]
    if separate:
        inner.append(('id', sid))
    #current_app.logger.debug('about to convert')
    inner.extend([('volumes', data['volumes']),
                ('containers', map(prepare_container, data['containers']))])
    outer = []
    if separate:
        outer.extend([('kind', 'Pod'), ('apiVersion', 'v1beta1'), ('id', sid)])
    outer.extend([('desiredState', dict([('manifest', OrderedDict(inner))])),
        ('labels', dict([('name', data['name'])]))])
    return OrderedDict(outer)


def make_config(data, sid=None):
    if sid is None:
        sid = data['sid']
    dash_name = '-'.join(re.split(r'[\s\\/\[\|\]{}\(\)\._]+', data['name']))
    cluster = data['cluster']
    
    # generate replicationController config
    if not cluster:
        return make_pod_config(data, sid)
    return OrderedDict([
        ('kind', 'ReplicationController'),
        ('apiVersion', 'v1beta2'),
        ('id', sid),
        ('desiredState', OrderedDict([
            ('replicas', data['replicas']),
            ('replicaSelector', dict([
                ('name', data['name'])
            ])),
            ('podTemplate', make_pod_config(data, sid, False)),
        ])),
        ('labels', dict([
            ('name', dash_name + '-cluster')
        ])),
    ])
    
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