from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from ..billing import Package
from ..core import db
from ..rbac import check_permission
from ..utils import login_required_or_basic_or_token
from ..users import User
from ..pods import Pod
from ..stats import StatWrap5Min
from collections import defaultdict
import time
from datetime import datetime

usage = Blueprint('usage', __name__, url_prefix='/usage')


@usage.route('/', methods=['GET'], strict_slashes=False)
@login_required_or_basic_or_token
@check_permission('get', 'users')
def get_total_usage():
    data = {}
    users = db.session.query(User).all()
    for user in users:
        if user.username not in data:
            data[user.username] = []
        kube_id = user.package.kube_id
        for pod in user.pods:
            entry = unfold_entry(pod)
            entry.update({"kube_id": kube_id})
            data[user.username].append(entry)
    return jsonify({'status': 'OK', 'data': data})

@usage.route('/<login>', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'users')
def get_usage(login):
    #start = request.args.get('start', None)
    #end = request.args.get('end', None)
    #period = db.session.query(User).filter(User.username==login).first().package.period
    user = db.session.query(User).filter(User.username==login).first()
    data = []
    for pod in user.pods:
        entry = unfold_entry(pod)
        data.append(entry)
    return jsonify({'status': 'OK', 'data': data})


def unfold_entry(row):
    time_ = defaultdict(list)
    for state in row.states:
        start = to_timestamp(state.start_time)
        end = (int(time.time()) if state.end_time is None else
               to_timestamp(state.end_time))
        time_[state.container_name].append({
            'kubes': state.kubes,
            'start': start,
            'end': end,
            })
    return {
        'id': row.id,
        'name': row.name,
        'kubes': row.kubes,
        'kube_id': [k.id for k in row.owner.package.kubes],
        'time': time_,
        }


def to_timestamp(date):
    return int((date - datetime(1970, 1, 1)).total_seconds())


#def get_range(start, end):
#    now = datetime.datetime.now()
#    offset = int(time.time()-int(datetime.datetime(now.year, now.month, 1).strftime('%s')))
#    return offset
