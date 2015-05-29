import ipaddress
from flask import Blueprint, request, jsonify, current_app

from . import APIError
from ..core import db
from ..rbac import check_permission
from ..utils import login_required_or_basic
from ..pods.models import IPPool, PodIP


ippool = Blueprint('ippool', __name__, url_prefix='/ippool')


@check_permission('get', 'ippool')
def get_networks_collection():
    return [u.to_dict() for u in IPPool.all()]


@ippool.route('/', methods=['GET'])
@login_required_or_basic
def get_list():
    return jsonify({'status': 'OK', 'data': get_networks_collection()})


@ippool.route('/getFreeHost', methods=['GET'])
@login_required_or_basic
def get_free_host():
    free_host = IPPool.get_free_host()
    return jsonify({'status': 'OK', 'data': free_host})


@ippool.route('/<network>', methods=['GET'])
@login_required_or_basic
@check_permission('get', 'ippool')
def get_one_network(network):
    if network == 'all':
        return jsonify({'status': 'OK', 'data': get_networks_collection()})
    # Suppose our IDs are integers only
    net = IPPool.filter_by(network=network).first()
    if net is None:
        raise APIError("Network {0} doesn't exists".format(network))
    return jsonify({'status': 'OK', 'data': net.to_dict()})


@ippool.route('/', methods=['POST'])
@login_required_or_basic
@check_permission('create', 'ippool')
def create_item():
    data = request.json
    if data is None:
        data = request.form
    for key in data.keys():
        if type(data[key]) is list and len(data[key]) == 1:
            data[key] = data[key][0]
    try:
        network = str(ipaddress.ip_network(unicode(data['network'])))
        autoblock_list = []
        for v in data.get('autoblock', '').split(','):
            v = v.strip()
            if v.isdigit():
                autoblock_list.append(int(v))
            elif v.find('-') > 0:
                _start, _end = v.split('-')
                if _start.isdigit() and _end.isdigit():
                    r = xrange(int(_start), int(_end) + 1)
                    autoblock_list.extend(
                        [vv for vv in r if vv not in autoblock_list])
        blocked_list = []
        autoblock_list = list(set(autoblock_list))
        autoblock_list.sort()
        # current_app.logger.debug(autoblock_list)
        ip_prefix = '.'.join(network.split('/')[0].split('.')[:-1])
        for i in autoblock_list:
            _ip = int(ipaddress.ip_address(u'{0}.{1}'.format(ip_prefix, i)))
            if _ip not in blocked_list:
                blocked_list.append(_ip)
        # current_app.logger.debug(blocked_list)
        if IPPool.filter_by(network=network).first():
            raise Exception("Network '{0}' already exist".format(network))
        pool = IPPool.create(network=network)
        pool.save()
        if autoblock_list:
            pool.block_ip(blocked_list)
        return jsonify({'status': 'OK', 'data': pool.to_dict()})
    except KeyError:
        raise APIError('Network is not defined')
    except Exception, e:
        db.session.rollback()
        raise APIError("An error was occured: '{0}'".format(e))


@ippool.route('/<path:network>', methods=['PUT'])
@login_required_or_basic
@check_permission('edit', 'ippool')
def change_item(network):
    data = request.json
    if data is None:
        data = request.form
    block_ip = data.get('block_ip')
    unblock_ip = data.get('unblock_ip')
    unbind_ip = data.get('unbind_ip')
    net = IPPool.filter_by(network=network).first()
    if net is None:
        raise APIError("Network '{0}' doesn't exist".format(network))
    if block_ip is not None:
        net.block_ip(block_ip)
    if unblock_ip is not None:
        net.unblock_ip(unblock_ip)
    if unbind_ip:
        podip = PodIP.filter_by(ip_address=int(ipaddress.ip_address(unbind_ip)))
        podip.delete()
    return jsonify({'status': 'OK', 'data': net.to_dict()})


@ippool.route('/<path:network>', methods=['DELETE'])
@login_required_or_basic
@check_permission('delete', 'ippool')
def delete_item(network):
    try:
        network = str(ipaddress.ip_network(network))
        if not IPPool.filter_by(network=network).first():
            raise Exception("Network '{0}' does not exist".format(network))
        pods_count = PodIP.filter_by(network=network).count()
        if pods_count > 0:
            raise Exception("You cannot delete this network '{0}' while "
                            "some of IP-addresses of this network were "
                            "assigned to Pods".format(network))
        for obj in PodIP.filter_by(network=network):
            obj.delete()
        for obj in IPPool.filter_by(network=network):
            obj.delete()
        return jsonify({'status': 'OK'})
    except KeyError:
        raise APIError('Network is not defined')
    except Exception, e:
        raise APIError("An error was occured: '{0}'".format(e))