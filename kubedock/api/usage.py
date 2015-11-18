from flask import Blueprint, request
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from ..rbac import check_permission
from ..utils import login_required_or_basic_or_token, KubeUtils
from ..users import User
from ..usage.models import ContainerState, IpState, PersistentDiskState
from ..core import db
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
    date_from, date_to = get_dates(request)
    return {user.username:
            get_user_usage(user, date_from, date_to) for user in User.query}


@usage.route('/<login>', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_usage(login):
    date_from, date_to = get_dates(request)
    user = User.query.filter_by(username=login).first()
    if user is None:
        raise APIError('User with username {0} does not exist'.format(login))
    return get_user_usage(user, date_from, date_to)


def get_dates(request):
    data = request.args
    date_from = data.get('date_from', datetime.utcfromtimestamp(0).isoformat())
    date_to = data.get('date_to', datetime.utcnow().isoformat())
    return (date_from, date_to)


def filter_query_by_date(model, query, date_from, date_to):
    query = query.filter(
        db.or_(model.start_time.between(date_from, date_to),
               model.end_time.between(date_from, date_to)))
    return query


def get_pod_usage(user, date_from, date_to):
    rv = []
    for pod in user.pods:
        time_ = defaultdict(list)
        query = db.session.query(ContainerState).filter(ContainerState.pod.contains(pod))
        query = filter_query_by_date(ContainerState, query, date_from, date_to)
        states = query.all()
        for state in states:
            start = to_timestamp(state.start_time)
            end = (int(time.time()) if state.end_time is None else
                   to_timestamp(state.end_time))
            time_[state.container_name].append({'kubes': state.kubes,
                                                'start': start, 'end': end})
        rv.append({'id': pod.id,
                   'name': pod.name,
                   'kubes': pod.kubes,
                   'kube_id': pod.kube_id,
                   'time': time_})
    return rv


def get_ip_states(user, date_from, date_to):
    query = db.session.query(IpState).filter(IpState.user.contains(user))
    query = filter_query_by_date(IpState, query, date_from, date_to)
    ip_states = query.all()
    return [ip_state.to_dict() for ip_state in ip_states]


def get_pd_states(user, date_from, date_to):
    query = db.session.query(PersistentDiskState).filter(
        PersistentDiskState.user == user)
    query = filter_query_by_date(PersistentDiskState, query, date_from, date_to)
    pd_states = query.all()
    return [pd_state.to_dict(exclude=['user_id']) for pd_state in pd_states]


def get_user_usage(user, date_from, date_to):
    return {'pods_usage': get_pod_usage(user, date_from, date_to),
            'ip_usage': get_ip_states(user, date_from, date_to),
            'pd_usage': get_pd_states(user, date_from, date_to)}


def to_timestamp(date):
    return int((date - datetime(1970, 1, 1)).total_seconds())


#def get_range(start, end):
#    now = datetime.datetime.now()
#    offset = int(time.time()-int(datetime.datetime(now.year, now.month, 1).strftime('%s')))
#    return offset
