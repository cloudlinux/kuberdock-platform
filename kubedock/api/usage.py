from flask import Blueprint
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from ..rbac import check_permission
from ..utils import login_required_or_basic_or_token, KubeUtils
from ..users import User
from . import APIError
from collections import defaultdict
import time
from datetime import datetime

usage = Blueprint('usage', __name__, url_prefix='/usage')


@usage.route('/', methods=['GET'], strict_slashes=False)
@login_required_or_basic_or_token
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_total_usage():
    return {user.username: get_user_usage(user) for user in User.query}


@usage.route('/<login>', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_usage(login):
    user = User.query.filter_by(username=login).first()
    if user is None:
        raise APIError('User with username {0} does not exist'.format(login))
    return get_user_usage(user)


def get_pod_usage(pod):
    time_ = defaultdict(list)
    for state in pod.container_states:
        start = to_timestamp(state.start_time)
        end = (int(time.time()) if state.end_time is None else
               to_timestamp(state.end_time))
        time_[state.container_name].append({'kubes': state.kubes,
                                            'start': start, 'end': end})
    return {'id': pod.id,
            'name': pod.name,
            'kubes': pod.kubes,
            'kube_id': pod.kube_id,
            'time': time_}


def get_user_usage(user):
    return {'pods_usage': map(get_pod_usage, user.pods),
            'ip_usage': [ip_state.to_dict() for ip_state in user.ip_states],
            'pd_usage': [pd_state.to_dict(exclude=['user_id'])
                         for pd_state in user.pd_states]}


def to_timestamp(date):
    return int((date - datetime(1970, 1, 1)).total_seconds())


#def get_range(start, end):
#    now = datetime.datetime.now()
#    offset = int(time.time()-int(datetime.datetime(now.year, now.month, 1).strftime('%s')))
#    return offset
