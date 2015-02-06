from flask import Blueprint, request, jsonify
from flask.ext.login import current_user

from ..static_pages.models import Menu, Page, MenuItem


static_pages = Blueprint('static_pages', __name__, url_prefix='/static_pages')


@static_pages.route('/<region>/', methods=['GET'])
def get_tree(region):
    menu = Menu.filter_by(region=region).first()
    return jsonify({'data': {'html': menu.render()}})


@static_pages.route('/page/<oid>', methods=['GET', 'POST', 'PUT'])
def get_page(oid):
    page = Page.filter_by(id=oid).first()
    if request.method == 'GET':
        return jsonify({'data': page.to_dict()})
    elif request.method in ('POST', 'PUT'):
        data = request.data
        print data
    return jsonify({'result': 'OK'})


@static_pages.route('/menu/<oid>', methods=['GET', 'POST', 'PUT'])
def get_menu(oid):
    menu = Menu.filter_by(id=oid).first()
    if request.method == 'GET':
        return jsonify({'data': menu.to_dict()})
    elif request.method in ('POST', 'PUT'):
        data = request.data
        print data
    return jsonify({'result': 'OK'})


@static_pages.route('/menuItem/<oid>', methods=['GET', 'POST', 'PUT'])
def get_menu_item(oid):
    data = request.form
    user_id = current_user.id
    if request.method == 'GET':
        item = MenuItem.filter_by(id=oid).first()
        return jsonify({'data': item.to_dict()})
    elif request.method in ('POST', 'PUT'):
        error = None
        try:
            if int(oid) == 0:
                item = MenuItem.create_item(data, user_id)
            else:
                item = MenuItem.filter_by(id=oid).first()
                item.update(data, user_id)
        except ValueError, e:
            error = str(e)
        except Exception, e:
            error = str(e)
        if error is not None:
            return jsonify({'error': error})
    return jsonify({'result': 'OK', 'dynatree_data': item.to_dynatree()})


@static_pages.route('/menuItem/delete/<oid>', methods=['DELETE', 'PUT', 'POST'])
def delete_menu_item(oid):
    print oid
    item = MenuItem.filter_by(id=oid).first()
    item.page.delete()
    item.delete()
    return jsonify({'result': 'OK'})


@static_pages.route('/dynatreeList/', methods=['GET'])
def get_dynatree_list():
    menu_list = Menu.get_dynatree_list()
    return jsonify({'data': menu_list})
