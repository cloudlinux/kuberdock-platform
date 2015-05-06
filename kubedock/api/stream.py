from flask import Blueprint, request, current_app
#from flask.ext.login import current_user
import json
from ..core import ConnectionPool, EvtStream

stream = Blueprint('stream', __name__, url_prefix='/stream')


#@route(bp, '/', methods=['GET'])
#def get_list():
#    pass

@stream.route('')
def send_stream():
    conn = ConnectionPool.get_connection()
    #current_app.logger.debug(conn)
    channel = request.args.get('channel', 'common')
    return current_app.response_class(
        EvtStream(conn, channel),
        direct_passthrough=True,
        mimetype='text/event-stream')


def send_event(event_name, data, to_file=None, channel='common'):
    conn = ConnectionPool.get_connection()
    conn.publish(channel, json.dumps([event_name, data]))
    if to_file is not None:
        try:
            to_file.write(data)
            to_file.write('\n')
            to_file.flush()
        except Exception as e:
            print 'Error writing to log file', e.__repr__()


def send_logs(node, data, to_file=None, channel='common'):
    conn = ConnectionPool.get_connection()
    conn.publish(channel, json.dumps(['install_logs',
                                      {'for_node': node, 'data': data}]))
    if to_file is not None:
        try:
            to_file.write(data)
            to_file.write('\n')
            to_file.flush()
        except Exception as e:
            print 'Error writing to log file', e.__repr__()
    

#def get_events():
#    while True:
#        result = tasks.wait_for_events.delay()
#        rv = result.wait()
#        current_app.logger.debug(rv)
#        send_event('kubevt', rv, 'bliss')