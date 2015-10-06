import re
from datetime import datetime
from flask import Blueprint, request, jsonify
from functools import wraps

from .. import tasks
from ..core import db
from ..models import ImageCache
from ..validation import check_container_image_name, check_image_request
from ..settings import DEFAULT_IMAGES_URL, DOCKER_IMG_CACHE_TIMEOUT
from ..utils import login_required_or_basic_or_token, KubeUtils
from ..kapi.images import get_container_config


images = Blueprint('images', __name__, url_prefix='/images')


def headerize(func):
    """The decorator adds header links to response for paginator"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        data = func(*args, **kwargs)
        resp = jsonify(data)
        fmt = '<{base}?page={page}&per_page={per_page}>; rel="{rel}"'
        links = [{'page': data['page'] - 1, 'rel':'prev'},
                 {'page': data['page'] + 1, 'rel':'next'},
                 {'page': 1, 'rel': 'first'},
                 {'page': data['num_pages'], 'rel':'last'}]
        header = ', '.join(fmt.format(base=request.base_url,
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
    refresh_cache = request.args.get('refresh_cache', 'no').lower() in ('1', 'true')
    repo_url = repo_url if patt.match(repo_url) else 'https://' + repo_url

    check_container_image_name(search_key)
    query_key = '{0}?{1}:{2}'.format(repo_url, search_key, page)
    query = db.session.query(ImageCache).get(query_key)

    # if query is saved in DB and it's not older than 1 day return it
    if not refresh_cache and query is not None and \
            (datetime.now() - query.time_stamp) < DOCKER_IMG_CACHE_TIMEOUT:
        return {'status': 'OK', 'data': query.data['results'],
                'num_pages': query.data['num_pages'], 'page': page, 'per_page': per_page}

    data = tasks.search_image(search_key, url=repo_url, page=page)
    data = {
        'num_pages': data['count'] // per_page + bool(data['count'] % per_page),
        'results': [{
            'is_automated': image['is_automated'],
            'star_count': image['star_count'],
            'description': image['short_description'],
            'name': image['repo_name'],
            'is_official': image['is_offical'],
            'pull_count': image['pull_count'],
        } for image in data['results']]
    }
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
@KubeUtils.jsonwrap
@login_required_or_basic_or_token
def get_dockerfile_data():
    params = KubeUtils._get_params()
    check_image_request(params)
    return get_container_config(params.pop('image'), **params)
