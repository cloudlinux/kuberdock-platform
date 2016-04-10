from flask import Blueprint, request

from ..rbac import check_permission
from ..decorators import login_required_or_basic_or_token
from ..utils import KubeUtils
from ..users import User
from ..kapi.users import UserNotFound
from ..usage.models import ContainerState, IpState, PersistentDiskState
from ..core import db
from collections import defaultdict
from . import APIError
import time
import dateutil.parser
from datetime import datetime

usage = Blueprint('usage', __name__, url_prefix='/usage')

DATE_FROM = 'date_from'
DATE_TO = 'date_to'


@usage.route('/', methods=['GET'], strict_slashes=False)
@login_required_or_basic_or_token
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_total_usage():
    date_from, date_to = get_dates(request)
    rv = {}
    for user in User.query:
        user_usage = get_user_usage(user, date_from, date_to)
        if user_usage:
            rv[user.username] = user_usage
    return rv


@usage.route('/<uid>', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'users')
@KubeUtils.jsonwrap
def get_usage(uid):
    date_from, date_to = get_dates(request)
    user = User.get(uid)
    if user is None:
        raise UserNotFound('User "{0}" does not exist'.format(uid))
    return get_user_usage(user, date_from, date_to)


def get_dates(request):
    data = request.args
    date_from = datetime.fromtimestamp(0)
    date_to = datetime.utcnow()
    if DATE_FROM in data:
        try:
            date_from = dateutil.parser.parse(data[DATE_FROM])
        except Exception as e:
            raise APIError('{}: {}'.format(DATE_FROM, e.message))
    if DATE_TO in data:
        try:
            date_to = dateutil.parser.parse(data[DATE_TO])
        except Exception as e:
            raise APIError('{}: {}'.format(DATE_TO, e.message))
    return (date_from, date_to)


def filter_query_by_date(query, model, date_from, date_to):
    query = query.filter(
        db.or_(model.start_time.between(date_from, date_to),
               model.end_time.between(date_from, date_to),
               db.and_(model.end_time.is_(None), model.start_time < date_to)))
    return query


def get_pod_usage(user, date_from, date_to):
    rv = []
    for pod in user.pods:
        time_ = defaultdict(list)
        query = ContainerState.query.filter(ContainerState.pod == pod)
        query = filter_query_by_date(query, ContainerState, date_from, date_to)
        states = query.all()
        for state in states:
            start = to_timestamp(state.start_time)
            end = (int(time.time()) if state.end_time is None else
                   to_timestamp(state.end_time))
            time_[state.container_name].append({'kubes': state.kubes,
                                                'start': start, 'end': end})
        if time_:
            rv.append({'id': pod.id,
                       'name': pod.name,
                       'kubes': pod.kubes,
                       'kube_id': pod.kube_id,
                       'time': time_})
    return rv


def get_ip_states(user, date_from, date_to):
    query = IpState.query.filter(IpState.user == user)
    query = filter_query_by_date(query, IpState, date_from, date_to)
    ip_states = query.all()
    return [ip_state.to_dict() for ip_state in ip_states]


def get_pd_states(user, date_from, date_to):
    query = PersistentDiskState.query.filter(PersistentDiskState.user == user)
    query = filter_query_by_date(query, PersistentDiskState,
                                 date_from, date_to)
    pd_states = query.all()
    return [pd_state.to_dict(exclude=['user_id']) for pd_state in pd_states]


def get_user_usage(user, date_from, date_to):
    rv = {}
    pods_usage = get_pod_usage(user, date_from, date_to)
    if pods_usage:
        rv['pods_usage'] = pods_usage
    ip_usage = get_ip_states(user, date_from, date_to)
    if ip_usage:
        rv['ip_usage'] = ip_usage
    pd_usage = get_pd_states(user, date_from, date_to)
    if pd_usage:
        rv['pd_usage'] = pd_usage
    return rv


def to_timestamp(date):
    return int((date - datetime(1970, 1, 1)).total_seconds())
