
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

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
