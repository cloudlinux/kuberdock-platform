from flask import Blueprint, request, jsonify, current_app
from flask.ext.login import current_user

from . import APIError
from ..core import check_permission
from ..static_pages.models import Menu, Page, MenuItem


static_pages = Blueprint('static_pages', __name__, url_prefix='/static_pages')


@static_pages.route('/<region>', methods=['GET'])
@check_permission('get', 'static_pages')
def get_tree(region):
    menu = Menu.filter_by(region=region).first()
    return jsonify({'status': 'OK', 'data': {'html': menu.render()}})


@static_pages.route('/page/<oid>', methods=['GET'])
@check_permission('get', 'static_pages')
def get_page(oid):
    page = Page.filter_by(id=oid).first()
    return jsonify({'status': 'OK', 'data': page.to_dict()})


@static_pages.route('/menu/<oid>', methods=['GET'])
@check_permission('get', 'static_pages')
def get_menu(oid):
    menu = Menu.filter_by(id=oid).first()
    return jsonify({'status': 'OK', 'data': menu.to_dict()})


@static_pages.route('/menuItem/<oid>', methods=['GET'])
@check_permission('get', 'static_pages')
def get_menu_item(oid):
    item = MenuItem.filter_by(id=oid).first()
    if item is None:
        raise APIError('Menu item "{0}" does not exist'.format(oid))
    return jsonify({'status': 'OK', 'data': item.to_dynatree()})


@static_pages.route('/menuItem/<oid>', methods=['PUT', 'POST'])
@check_permission('edit', 'static_pages')
def put_menu_item(oid):
    data = request.form
    user_id = current_user.id
    if not oid.isdigit():
        raise APIError('Wrong menu item Id {0}'.format(oid))
    if int(oid) == 0:
        try:
            item = MenuItem.create_item(data, user_id)
        except Exception, e:
            raise APIError(str(e))
    else:
        item = MenuItem.filter_by(id=oid).first()
        if item is None:
            raise APIError('Menu item {0} does not exist'.format(oid))
        try:
            item.update(data, user_id)
        except Exception, e:
            current_app.logger.warning(
                'put_menu_item({0}) failed: {1}'.format(oid, e))
            raise APIError(str(e))
    return jsonify({'status': 'OK', 'dynatree_data': item.to_dynatree()})


@static_pages.route('/menuItem/ord/<oid1>/<oid2>', methods=['PUT', 'POST'])
@check_permission('edit', 'static_pages')
def order_item(oid1, oid2):
    item1 = MenuItem.filter_by(id=oid1).first()
    item2 = MenuItem.filter_by(id=oid2).first()
    if item1 is None or item2 is None:
        raise APIError(
            'Menu item1 {0} or item2 {1} does not exist'.format(oid1, oid2))
    new_ordering = item2.ordering
    item2.ordering = item1.ordering
    item1.ordering = new_ordering
    item1.save()
    item2.save()
    return jsonify({'status': 'OK'})


@static_pages.route('/menuItem/delete/<oid>', methods=['DELETE', 'PUT', 'POST'])
@check_permission('delete', 'static_pages')
def delete_menu_item(oid):
    item = MenuItem.filter_by(id=oid).first()
    if item is None:
        raise APIError('Menu item {0} does not exist'.format(oid))
    if item.page_id:
        item.page.delete()
    item.delete()
    return jsonify({'status': 'OK'})


@static_pages.route('/dynatreeList', methods=['GET'])
@check_permission('get', 'static_pages')
def get_dynatree_list():
    menu_list = Menu.get_dynatree_list()
    return jsonify({'status': 'OK', 'data': menu_list})
