import re
from datetime import datetime
from flask import Blueprint, request, jsonify
from functools import wraps

from ..core import db
from ..models import ImageCache
from ..validation import check_image_search, check_image_request
from ..settings import DEFAULT_IMAGES_URL
from ..decorators import login_required_or_basic_or_token
from ..utils import KubeUtils
from ..kapi import images as kapi_images
from ..rbac import check_permission


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
@check_permission('get', 'images')
def search_image():
    search_key = request.args.get('searchkey', 'none')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    refresh_cache = request.args.get('refresh_cache', 'no').lower() in ('1', 'true')
    repo_url = _get_repo_url(request.args)

    check_image_search(search_key)
    query_key = '{0}?{1}:{2}'.format(repo_url, search_key, page)
    query = db.session.query(ImageCache).get(query_key)

    # if query is saved in DB and it's not older than 1 day return it
    if not (refresh_cache or query is None or query.outdated):
        return {'status': 'OK', 'data': query.data['results'],
                'num_pages': query.data['num_pages'], 'page': page, 'per_page': per_page}

    data = kapi_images.search_image(search_key, url=repo_url, page=page)
    data = {
        'num_pages': data.get('count', 1) // per_page + bool(data.get('count', 1) % per_page),
        'results': [{
            'source_url': kapi_images.Image(
                image.get('repo_name', '')).source_url,
            'is_automated': image.get('is_automated', False),
            'star_count': image.get('star_count', 0),
            'description': image.get('short_description', ''),
            'name': image.get('repo_name', 'none'),
            'is_official': image.get('is_official', False),
            'pull_count': image.get('pull_count', 0),
        } for image in data.get('results', [])]
    }
    if query is None:
        db.session.add(ImageCache(query=query_key, data=data,
                                  time_stamp=datetime.utcnow()))
    else:
        query.data = data
        query.time_stamp = datetime.utcnow()
    db.session.commit()
    return {'status': 'OK', 'data': data['results'],
            'num_pages': data['num_pages'], 'page': page, 'per_page': per_page}


@images.route('/new', methods=['POST'])
@KubeUtils.jsonwrap
@login_required_or_basic_or_token
@check_permission('get', 'images')
def get_dockerfile_data():
    params = KubeUtils._get_params()
    check_image_request(params)
    return kapi_images.Image(
        params.pop('image')
    ).get_container_config(**params)


@images.route('/isalive', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('isalive', 'images')
def ping_registry():
    repo_url = _get_repo_url(request.args)
    kapi_images.check_registry_status(repo_url)
    return {'status': 'OK', 'data': True}


def _get_repo_url(args):
    patt = re.compile(r'https?://')
    repo_url = args.get('url', DEFAULT_IMAGES_URL).rstrip('/')
    repo_url = repo_url if patt.match(repo_url) else 'https://' + repo_url
    return repo_url
