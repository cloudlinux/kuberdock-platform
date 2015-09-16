import json
import re

from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from functools import wraps

from .. import tasks
from ..core import db
from ..dockerfile import DockerfileParser
from ..models import ImageCache, DockerfileCache
from ..validation import check_container_image_name
from ..settings import DEFAULT_IMAGES_URL
from ..utils import login_required_or_basic_or_token


images = Blueprint('images', __name__, url_prefix='/images')


def _get_docker_file(image, tag=None):
    data = {}
    query = db.session.query(DockerfileCache).get(image)
    #current_app.logger.debug(query)
    if query is not None:
        if (datetime.now() - query.time_stamp) < timedelta(days=1):
            data = query.data
    if not data:
        result = tasks.get_dockerfile.delay(image, tag)
        rv = result.wait()
        data = DockerfileParser(rv).get()
        data['image'] = image
        # current_app.logger.debug(out)
        if query is None:
            db.session.add(DockerfileCache(image=image, data=data,
                                           time_stamp=datetime.now()))
        else:
            query.data = data
            query.time_stamp = datetime.now()
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


def headerize(func):
    """
    The decorator adds header links to response for paginator
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        data = func(*args, **kwargs)
        resp = jsonify(data)
        fmt='<{base}?page={page}&per_page={per_page}>; rel="{rel}"'
        links=[
            {'page':data['page']-1, 'rel':'prev'},
            {'page':data['page']+1,'rel':'next'},
            {'page':1,'rel':'first'},
            {'page':data['num_pages'], 'rel':'last'}]
        header = ', '.join(fmt.format(
                base=request.base_url,
                page=i['page'],
                per_page=data['per_page'],
                rel=i['rel'])
                    for i in links)
        resp.headers.extend({'Link': header})
        return resp
    return wrapper


@images.route('/', methods=['GET'])
@headerize
@login_required_or_basic_or_token
def search_image(patt=re.compile(r'https?://')):
    search_key = request.args.get('searchkey', 'none')
    repo_url = request.args.get('url', DEFAULT_IMAGES_URL).rstrip('/')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    repo_url = repo_url if patt.match(repo_url) else 'https://' + repo_url

    check_container_image_name(search_key)
    query_key = '{0}?{1}:{2}'.format(repo_url, search_key, page)
    query = db.session.query(ImageCache).get(query_key)

    # if query is saved in DB and it's not older than 1 day return it
    if query is not None and (datetime.now() - query.time_stamp) < timedelta(days=1):
        return {'status': 'OK', 'data': query.data['results'],
                'num_pages': query.data['num_pages'], 'page': page, 'per_page': per_page}

    rv = tasks.search_image(search_key, url=repo_url, page=page)
    data = json.loads(rv)
    if query is None:
        db.session.add(ImageCache(query=query_key, data=data,
                                  time_stamp=datetime.now()))
    else:
        query.data = data
        query.time_stamp = datetime.now()
    db.session.commit()
    return {'status': 'OK', 'data': data['results'],
            'num_pages': data['num_pages'], 'page': page, 'per_page': per_page}


@images.route('/new', methods=['POST'])
@login_required_or_basic_or_token
def get_dockerfile_data():
    image = request.form.get('image')
    if image is None and request.json is not None:
        image = request.json.get('image')
    out = _get_docker_file(image)
    out.pop('onbuild', None)
    out['env'] = [{'name': k, 'value': v} for k, v in out['env']]
    out['ports'] = [{'number': k, 'protocol': v} for k, v in out['ports']]
    out['volumeMounts'] = list(out['volumeMounts'])
    return jsonify({'status': 'OK', 'data': out})
