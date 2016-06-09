import json
import random
import requests
import string
from ..core import db
from ..exceptions import APIError
from ..pods.models import Pod
from ..utils import get_api_url


class KubeQuery(object):

    def __init__(self, return_json=True):
        self.return_json = return_json

    @staticmethod
    def _compose_args(rest=False):
        """
        Adds request args
        :param rest: bool
        :return: dict -> args dict to be included to request
        """
        args = {}
        if rest:
            args['headers'] = {'Content-Type': 'application/json'}
        return args

    def _raise_error(self, error_string):
        """
        Raises an error
        :param error_string: string
        """
        if self.return_json:
            raise SystemExit(
                json.dumps(
                    {'status': 'ERROR',
                     'message': error_string}))
        else:
            raise SystemExit(error_string)

    @staticmethod
    def _make_url(res, ns=None, **kwargs):
        """
        Composes a full URL
        :param res: list -> list of URL path items
        """
        if res is not None:
            return get_api_url(*res, namespace=ns, **kwargs)
        return get_api_url(namespace=ns, **kwargs)

    def _return_request(self, req):
        try:
            if self.return_json:
                return req.json()
            return req.text
        except (ValueError, TypeError), e:
            raise APIError("Cannot process request: {0}".format(str(e)))

    def get(self, res=None, params=None, ns=None):
        """
        GET request wrapper.
        :param res: list of URL path items
        :param params: dict -> request params
        """
        args = self._compose_args()
        if params:
            args['params'] = params
        return self._run('get', res, args, ns)

    def post(self, res, data, rest=False, ns=None):
        args = self._compose_args(rest)
        args['data'] = data
        return self._run('post', res, args, ns)

    def put(self, res, data, rest=False, ns=None):
        args = self._compose_args(rest)
        args['data'] = data
        return self._run('put', res, args, ns)

    def delete(self, res, ns=None):
        args = self._compose_args()
        return self._run('del', res, args, ns)

    def patch(self, res, data, ns=None, replace_lists=True):
        args = self._compose_args(True)
        if replace_lists:
            ct = 'application/merge-patch+json'
        else:
            ct = 'application/strategic-merge-patch+json'
        args['headers']['Content-Type'] = ct
        args['data'] = data
        return self._run('patch', res, args, ns)

    def _run(self, act, res, args, ns):
        dispatcher = {
            'get': requests.get,
            'post': requests.post,
            'put': requests.put,
            'del': requests.delete,
            'patch': requests.patch,
        }
        try:
            req = dispatcher.get(act, requests.get)(self._make_url(res, ns),
                                                    **args)
            return self._return_request(req)
        except requests.exceptions.ConnectionError, e:
            return self._raise_error(str(e))


def get_pod_config(pod_id, param=None, default=None):
    db_pod = db.session.query(Pod).get(pod_id)
    return db_pod.get_dbconfig(param, default)


def check_pod_name(name, owner=None):
    if name is None:
        return
    if owner is None:
        pod = Pod.query.filter_by(name=name).first()
    else:
        pod = Pod.query.filter_by(name=name, owner=owner).first()
    if pod:
        raise APIError("Conflict. Pod with name = '{0}' already exists. "
                       "Try another name.".format(name),
                       status_code=409)


def set_pod_status(pod_id, status):
    p = db.session.query(Pod).get(pod_id)
    if p.status != status:
        p.status = status
        db.session.commit()


def mark_pod_as_deleted(pod_id):
    p = db.session.query(Pod).get(pod_id)
    if p is not None:
        p.name += \
            '__' + ''.join(random.sample(string.lowercase + string.digits, 8))
        p.status = 'deleted'
    db.session.commit()


def fetch_pods(users=False, live_only=True):
    if users:
        if live_only:
            return db.session.query(Pod).join(Pod.owner).filter(
                Pod.status != 'deleted'
            )
        return db.session.query(Pod).join(Pod.owner)
    if live_only:
        return db.session.query(Pod).filter(Pod.status != 'deleted')
    return db.session.query(Pod)


def replace_pod_config(pod, data):
    """
    Replaces config in DB entirely with provided one
    :param data: dict -> config to be saved
    """
    db_pod = db.session.query(Pod).get(pod.id)
    try:
        db_pod.config = json.dumps(data)
        db.session.commit()
    except Exception:
        db.session.rollback()
