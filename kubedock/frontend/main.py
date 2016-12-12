from flask import Blueprint, make_response, render_template, request, session

from kubedock.sessions import create_token
from kubedock.settings import ISV_MODE_ENABLED, TEST

main = Blueprint('main', __name__)


@main.route('/', methods=['GET'])
def index():
    token = request.args.get('token2')
    if token is not None:
        token = create_token(session)
        resp = make_response(render_template('index.html', token=token))
        if 'X-Auth-Token' not in resp.headers:
            resp.headers['X-Auth-Token'] = token
        return resp
    return render_template('index.html', token=None)


@main.route('/hosted/', methods=['GET'])
def hosted():
    if not ISV_MODE_ENABLED:
        return 'not found', 404
    token = request.args.get('token2')
    if token is not None:
        token = create_token(session)
        resp = make_response(render_template('isv/index.html', token=token))
        if 'X-Auth-Token' not in resp.headers:
            resp.headers['X-Auth-Token'] = token
        return resp
    return render_template('isv/index.html', token=None)


@main.route('/test', methods=['GET'])
def run_tests():
    if TEST:
        return render_template('tests/index.html')
    return "not found", 404
