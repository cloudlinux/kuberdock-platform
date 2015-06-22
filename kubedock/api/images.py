import json
import datetime
import re
from flask import Blueprint, request, current_app, jsonify

from .. import tasks
from ..core import db
from ..dockerfile import DockerfileParser
from ..models import ImageCache, DockerfileCache
from ..validation import check_container_image_name


images = Blueprint('images', __name__, url_prefix='/images')

DEFAULT_IMAGES_URL = 'https://registry.hub.docker.com'


def _get_docker_file(image, tag=None):
    data = {}
    query = db.session.query(DockerfileCache).get(image)
    #current_app.logger.debug(query)
    if query is not None:
        if (datetime.datetime.now() - query.time_stamp).seconds < 86400:    # 1 day
            data = query.data
    if not data:
        result = tasks.get_dockerfile.delay(image, tag)
        rv = result.wait()
        data = DockerfileParser(rv).get()
        data['image'] = image
        # current_app.logger.debug(out)
        if query is None:
            db.session.add(DockerfileCache(image=image, data=data,
                                           time_stamp=datetime.datetime.now()))
        else:
            query.data = data
            query.time_stamp = datetime.datetime.now()
        db.session.commit()
    parent = data.pop('parent', {})
    if parent:
        parent_data = _get_docker_file(parent['name'], parent['tag'])
        data = _merge_parent(data, parent_data)
    return data


def _update_set_attr(current, attr, parent):
    s = set()
    for i in current[attr] + parent[attr]:
        if isinstance(i, list):
            i = tuple(i)
        s.add(i)
    current[attr] = list(s)


def _merge_parent(current, parent):
    for attr in 'ports', 'env', 'volumeMounts':
        _update_set_attr(current, attr, parent)
        if 'onbuild' in parent:
            _update_set_attr(current, attr, parent['onbuild'])
    for p_attr in 'command', 'workingDir':
        if not current[p_attr] and parent[p_attr]:
            current[p_attr] = parent[p_attr]
        if 'onbuild' in parent:
            if not current[p_attr] and parent['onbuild'][p_attr]:
                current[p_attr] = parent['onbuild'][p_attr]
    return current


@images.route('/', methods=['GET'])
def get_list_by_keyword():
    repo_url = request.args.get('url', DEFAULT_IMAGES_URL).rstrip('/')
    search_key = request.args.get('searchkey', 'none')

    # parse search string
    if search_key.startswith('http://') or search_key.startswith('https://'):
        protocol = 'http://' if search_key.startswith('http://') else 'https://'
        host, urn = search_key.lstrip(protocol).split('/', 1)
        search_key = '/'.join(urn.split('/')[-2:])
        repo_url = protocol + host

    check_container_image_name(search_key)
    query_key = '{0}?{1}'.format(repo_url.rstrip('/'), search_key)
    query = db.session.query(ImageCache).get(query_key)
    if query is not None:
        if (datetime.datetime.now() - query.time_stamp).seconds < 86400:    # 1 day
            return jsonify({'status': 'OK', 'data': query.data})
    result = tasks.get_container_images.delay(search_key, url=repo_url)
    rv = result.wait()
    # if you want to search an image directly without celery:
    # rv = tasks.search_image(search_key, url=repo_url)
    data = json.loads(rv)['results']
    if query is None:
        db.session.add(ImageCache(query=query_key, data=data,
                                  time_stamp=datetime.datetime.now()))
    else:
        query.data = data
        query.time_stamp = datetime.datetime.now()
    db.session.commit()
    return jsonify({'status': 'OK', 'data': data})


@images.route('/search', methods=['GET'])
def search_image():
    repo_url = request.args.get('url', DEFAULT_IMAGES_URL).rstrip('/')
    repo_url = 'https://{0}'.format(
        repo_url.lstrip('http://').lstrip('https://'))
    search_key = request.args.get('searchkey', 'none')
    page = int(request.args.get('page', 0)) + 1

    # current_app.logger.debug((search_key, repo_url))
    check_container_image_name(search_key)
    query_key = '{0}?{1}:{2}'.format(repo_url.rstrip('/'), search_key, page)
    query = db.session.query(ImageCache).get(query_key)
    if query is not None:
        if (datetime.datetime.now() - query.time_stamp).seconds < 86400:    # 1 day
            return jsonify({'status': 'OK', 'data': query.data['results'],
                            'num_pages': query.data['num_pages'],
                            'page': page})
    #result = tasks.get_container_images.delay(
    #    search_key, url=repo_url, page=page)
    #rv = result.wait()
    # if you want to search an image directly without celery:
    rv = tasks.search_image(search_key, url=repo_url, page=page)
    data = json.loads(rv)#['results']
    if query is None:
        db.session.add(ImageCache(query=query_key, data=data,
                                  time_stamp=datetime.datetime.now()))
    else:
        query.data = data
        query.time_stamp = datetime.datetime.now()
    db.session.commit()
    return jsonify({'status': 'OK', 'data': data['results'],
                    'num_pages': data['num_pages'], 'page': page})


@images.route('/new', methods=['POST'])
def get_dockerfile_data():
    image = request.form.get('image', 'none')
    out = _get_docker_file(image)
    out.pop('onbuild', None)
    out['env'] = [{'name': k, 'value': v} for k, v in out['env']]
    out['ports'] = [{'number': k, 'protocol': v} for k, v in out['ports']]
    out['volumeMounts'] = list(out['volumeMounts'])
    return jsonify({'status': 'OK', 'data': out})