
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

from flask import Blueprint, current_app, request, session
from ..core import ConnectionPool, EvtStream
from ..login import auth_required


stream = Blueprint('stream', __name__, url_prefix='/stream')


@stream.route('')
@auth_required
def send_stream():
    conn = ConnectionPool.get_connection()
    channel = getattr(session, 'sid', None)
    if channel is None:
        channel = 'common'
    last_id = request.headers.get('Last-Event-Id')
    if last_id is None:
        last_id = request.args.get('lastid')
    return current_app.response_class(
        EvtStream(conn, channel, last_id),
        direct_passthrough=True,
        mimetype='text/event-stream')
