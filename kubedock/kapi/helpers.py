import json
import random
import string

import requests

from ..core import db
from ..exceptions import APIError
from ..pods.models import Pod
from ..settings import KUBE_BASE_URL, KUBE_API_VERSION
from ..users.models import User
from ..utils import get_api_url, send_pod_status_update


class KubeQuery(object):

    def __init__(self, return_json=True, base_url=KUBE_BASE_URL,
                 api_version=KUBE_API_VERSION):
        self.return_json = return_json
        self.base_url = base_url
        self.api_version = api_version

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

    def _make_url(self, res, ns=None, **kwargs):
        """
        Composes a full URL
        :param res: list -> list of URL path items
        """
        if res is not None:
            return get_api_url(*res, namespace=ns, base_url=self.base_url,
                               api_version=self.api_version, **kwargs)
        return get_api_url(namespace=ns, base_url=self.base_url,
                           api_version=self.api_version, **kwargs)

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


KUBERDOCK_POD_UID = 'kuberdock-pod-uid'
LABEL_SELECTOR_TYPE = 'kuberdock-type={}'
LABEL_SELECTOR_PODS = KUBERDOCK_POD_UID + ' in ({})'


class Services(object):
    """Class provides methods to get services by some label selector
    conditions, or by user or pods.

    Args:
        svc_type (str): type of service, or None to get all services

    """

    def __init__(self, svc_type=None):
        self.kq = KubeQuery()
        self.svc_type = svc_type

    def _get_label_selector(self, conditions):
        return ", ".join(conditions)

    def _get(self, conditions=None):
        if conditions is None:
            conditions = []
        label_selector = self._get_label_selector(conditions)
        svc = self.kq.get(['services'], {'labelSelector': label_selector})
        return svc['items']

    def get_by_type(self, conditions=None):
        """Return all services filtered by LabelSelector
        Args:
            conditions (str, tuple, list): conditions that goes to
            LabelSelector(example: 'kuberdock-pod-uid=123')

        """
        if conditions is None:
            conditions = []
        if not isinstance(conditions, (tuple, list)):
            conditions = [conditions]
        else:
            conditions = list(conditions)
        if self.svc_type:
            conditions.append(LABEL_SELECTOR_TYPE.format(self.svc_type))
        return self._get(conditions)

    def get_all(self):
        """Return all service of selected type
        """
        return self.get_by_type()

    def get_by_pods(self, pods):
        """Return all services of selected type, owned by pods
        Args:
            pods (str, list, tuple): pods ids

        """
        if not isinstance(pods, (list, tuple)):
            pods = (pods, )
        ls_pods = LABEL_SELECTOR_PODS.format(', '.join(pods))
        svc = self.get_by_type(ls_pods)
        #TODO: pod can have several services, we need list as value
        return {s['metadata']['labels'][KUBERDOCK_POD_UID]: s for s in svc}

    def get_by_user(self, user_id):
        """Return all service of selected type, owned by user
        Args:
            user_id (str): id of user
        """
        user = User.get(user_id)
        pods = [pod['id'] for pod in user.pods_to_dict()]
        return self.get_by_pods(pods)


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


def set_pod_status(pod_id, status, send_update=False):
    # TODO refactor to dbPod level + separate event send
    db_pod = db.session.query(Pod).get(pod_id)
    if db_pod.status != status:
        db_pod.status = status
        db.session.commit()
        if send_update:
            send_pod_status_update(status, db_pod, 'MODIFIED')


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
