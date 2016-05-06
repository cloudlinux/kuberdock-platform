from flask import Blueprint, current_app, request
from ..core import ConnectionPool, EvtStream
from ..login import auth_required
from ..sessions import session_required

stream = Blueprint('stream', __name__, url_prefix='/stream')


@stream.route('')
@auth_required
@session_required
def send_stream():
    conn = ConnectionPool.get_connection()
    channel = request.args.get('id')
    if channel is None:
        channel = 'common'
    last_id = request.headers.get('Last-Event-Id')
    if last_id is None:
        last_id = request.args.get('lastid')
    return current_app.response_class(
        EvtStream(conn, channel, last_id),
        direct_passthrough=True,
        mimetype='text/event-stream')
