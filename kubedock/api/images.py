import json
import datetime
from flask import Blueprint, request, current_app, jsonify

from .. import tasks
from ..core import db
from ..models import ImageCache, DockerfileCache
from ..validation import check_container_image_name


images = Blueprint('images', __name__, url_prefix='/images')

DEFAULT_IMAGES_URL = 'https://registry.hub.docker.com'


def process(data):
    data = data.strip()
    pos = data.find(' ')
    if pos <= 0:
        return []
    return map((lambda x: x.strip('\'"[] ')), data[pos:].split(','))


def parse(data):
    ready = {'command': [], 'workingDir': '', 'ports': [], 'volumeMounts': []}
    for line in data.splitlines():
        if line.startswith('CMD'):
            ready['command'].extend(process(line))
        elif line.startswith('WORKDIR'):
            res = process(line)
            ready['workingDir'] = '' if not res else res[0]
        elif line.startswith('VOLUME'):
            ready['volumeMounts'].extend(process(line))
        elif line.startswith('EXPOSE'):
            ready['ports'].extend(process(line))
    return ready


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


@images.route('/<search_key>/<path:repo_url>', methods=['GET'])
def search_image(search_key=None, repo_url=None):
    page = int(request.args.get('page', 0)) + 1

    # parse search string
    if search_key.startswith('http://') or search_key.startswith('https://'):
        protocol = 'http://' if search_key.startswith('http://') else 'https://'
        host, urn = search_key.lstrip(protocol).split('/', 1)
        search_key = '/'.join(urn.split('/')[-2:])
        repo_url = protocol + host

    check_container_image_name(search_key)
    query_key = '{0}?{1}:{2}'.format(repo_url.rstrip('/'), search_key, page)
    query = db.session.query(ImageCache).get(query_key)
    if query is not None:
        if (datetime.datetime.now() - query.time_stamp).seconds < 86400:    # 1 day
            return jsonify({'status': 'OK', 'data': query.data['results'],
                            'num_pages': query.data['num_pages'],
                            'page': page})
    result = tasks.get_container_images.delay(
        search_key, url=repo_url, page=page)
    rv = result.wait()
    # if you want to search an image directly without celery:
    # rv = tasks.search_image(search_key, url=repo_url)
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
    query = db.session.query(DockerfileCache).get(image)
    current_app.logger.debug(query)
    if query is not None:
        if (datetime.datetime.now() - query.time_stamp).seconds < 86400:    # 1 day
            return jsonify({'status': 'OK', 'data': query.data})
    result = tasks.get_dockerfile.delay(image)
    rv = result.wait()

    out = parse(rv)
    out['image'] = image
    current_app.logger.debug(out)
    if query is None:
        db.session.add(DockerfileCache(image=image, data=out,
                                       time_stamp=datetime.datetime.now()))
    else:
        query.data = out
        query.time_stamp = datetime.datetime.now()
    db.session.commit()
    return jsonify({'status': 'OK', 'data': out})