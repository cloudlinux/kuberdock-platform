import base64
import copy
import json
import random
import string

import requests

from .. import settings
from .. import utils
from kubedock.kapi.podutils import raise_if_failure
from ..core import db
from ..exceptions import APIError
from ..pods.models import Pod
from ..users.models import User
from ..utils import POD_STATUSES


class KubeQuery(object):
    def __init__(self, return_json=True, base_url=settings.KUBE_BASE_URL,
                 api_version=settings.KUBE_API_VERSION):
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
            return utils.get_api_url(
                *res, namespace=ns, base_url=self.base_url,
                api_version=self.api_version, **kwargs)
        return utils.get_api_url(
            namespace=ns, base_url=self.base_url, api_version=self.api_version,
            **kwargs)

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
        :param ns: str -> namespace
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
KUBERDOCK_TYPE = 'kuberdock-type'
LABEL_SELECTOR_TYPE = KUBERDOCK_TYPE + '={}'
LABEL_SELECTOR_PODS = KUBERDOCK_POD_UID + ' in ({})'
SERVICES = 'services'


class Services(object):
    """Class provides methods to get services by some label selector
    conditions, or by user or pods.

    Args:
        svc_type (str): type of service, or None to get all services

    """

    template = {
        'kind': 'Service',
        'apiVersion': settings.KUBE_API_VERSION,
        'metadata': {
            'generateName': 'service-',
            'labels': {'kuberdock-pod-uid': None},
        },
        'spec': {
            'selector': {'kuberdock-pod-uid': None},
            'ports': None,
            'type': 'ClusterIP',
            'sessionAffinity': 'None'
        }
    }

    def __init__(self, svc_type=None):
        self.kq = KubeQuery()
        self.svc_type = svc_type

    def post(self, service, namespace):
        json_data = json.dumps(service)
        return self.kq.post([SERVICES], json_data, rest=True, ns=namespace)

    def patch(self, name, namespace, data, replace_lists=True):
        json_data = json.dumps(data)
        return self.kq.patch([SERVICES, name], json_data,
                             ns=namespace, replace_lists=replace_lists)

    def delete(self, name, namespace):
        return self.kq.delete([SERVICES, name], ns=namespace)

    def get_template(self, pod_id, ports):
        if not all((pod_id, ports)):
            raise ValueError('Pod id and ports must be specified')
        template = copy.deepcopy(self.template)
        template['metadata']['labels']['kuberdock-pod-uid'] = pod_id
        if self.svc_type:
            template['metadata']['labels'][KUBERDOCK_TYPE] = self.svc_type
        template['spec']['selector']['kuberdock-pod-uid'] = pod_id
        template['spec']['ports'] = ports
        return template

    @staticmethod
    def _get_label_selector(conditions):
        return ", ".join(conditions)

    def _get(self, conditions=None):
        if conditions is None:
            conditions = []
        label_selector = self._get_label_selector(conditions)
        svc = self.kq.get([SERVICES], {'labelSelector': label_selector})
        return svc['items']

    def update_ports(self, service, ports):
        """Update ports in service or remove service if ports emtpy
        :param service: service to update
        :param ports: new ports for service
        :return: updated service
        """
        name = service['metadata']['name']
        namespace = service['metadata']['namespace']
        if ports:
            data = {'spec': {'ports': ports}}
            rv = self.patch(name, namespace, data)
            raise_if_failure(rv, "Couldn't patch service ports")
            return rv
        else:
            rv = self.delete(name, namespace)
            raise_if_failure(rv, "Couldn't delete service")
            return None

    def update_ports_by_pod(self, pod_id, ports):
        svc = self.get_by_pods(pod_id)
        for s in svc:
            self.update_ports(s, ports)

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
            pods = (pods,)
        ls_pods = LABEL_SELECTOR_PODS.format(', '.join(pods))
        svc = self.get_by_type(ls_pods)
        # TODO: pod can have several services, we need list as value
        return {s['metadata']['labels'][KUBERDOCK_POD_UID]: s for s in svc}

    def get_by_user(self, user_id):
        """Return all service of selected type, owned by user
        Args:
            user_id (str): id of user
        """
        user = User.get(user_id)
        pods = [pod['id'] for pod in user.pods_to_dict()]
        return self.get_by_pods(pods)


LOCAL_SVC_TYPE = 'local'

class LocalService(Services):

    def __init__(self):
        super(LocalService, self).__init__(LOCAL_SVC_TYPE)

    def get_template(self, pod_id, ports):
        template = super(LocalService, self).get_template(pod_id, ports)
        template['metadata']['labels']['name'] = pod_id[:54] + '-service'
        return template

    def get_clusterIP(self, service):
        try:
            return service['spec']['clusterIP']
        except (KeyError, IndexError):
            return None

    def set_clusterIP(self, service, clusterIP):
        if clusterIP:
            service['spec']['clusterIP'] = clusterIP
        return service

    def get_pods_clusterIP(self, services):
        svc = {}
        for pod, s in services.iteritems():
            clusterIP = self.get_clusterIP(s)
            if clusterIP:
                svc[pod] = clusterIP
        return svc

    def get_clusterIP_all(self):
        svc = self.get_all()
        return [self.get_clusterIP(s) for s  in svc]

    def get_clusterIP_by_pods(self, pods):
        svc = self.get_by_pods(pods)
        return self.get_pods_clusterIP(svc)

    def get_clusterIP_by_user(self, user_id):
        svc = self.get_by_user(user_id)
        return self.get_pods_clusterIP(svc)


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
    if db_pod.status == status:
        return
    # Do not change 'deleted' status inside database. Pod could have been
    # deleted during pod-task execution.
    if db_pod.status == POD_STATUSES.deleted:
        raise APIError('Not allowed to change "deleted" status.',
                       type='NotAllowedToChangeDeletedStatus')
    db_pod.status = status
    db.session.commit()
    if send_update:
        utils.send_pod_status_update(status, db_pod, 'MODIFIED')


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
    :param pod: Pod -> instance of Pod
    :param data: dict -> config to be saved
    """
    db_pod = db.session.query(Pod).get(pod.id)
    try:
        db_pod.config = json.dumps(data)
        db.session.commit()
    except Exception:  # TODO: Fix too broad exception
        db.session.rollback()


class K8sSecretsClient(object):
    SECRET_TYPE = 'kubernetes.io/dockercfg'

    def __init__(self, k8s_query):
        self.k8s_query = k8s_query

    @classmethod
    def _build_secret(cls, name, data, namespace):
        return {'apiVersion': settings.KUBE_API_VERSION,
                'kind': 'Secret',
                'metadata': {'name': name, 'namespace': namespace},
                'data': data,
                'type': cls.SECRET_TYPE}

    @classmethod
    def _process_response(cls, resp):
        if resp['kind'] != 'Status':
            return resp
        elif resp['kind'] == 'Status' and resp['status'] == 'Failure':
            raise cls.K8sApiError(resp)
        else:
            raise cls.UnknownAnswer(resp)

    def _run(self, method, url_parts, body=None, namespace=None, **kwargs):
        m = getattr(self.k8s_query, method)
        resp = m(url_parts, json.dumps(body), ns=namespace, **kwargs)
        return self._process_response(resp)

    def create(self, name, data, namespace):
        secret = self._build_secret(name, data, namespace)
        return self._run('post', ['secrets'], secret, namespace=namespace,
                         rest=True)

    def get(self, name, namespace):
        return self._run('get', ['secrets', name], namespace=namespace)

    def list(self, namespace):
        return self._run('get', ['secrets'], namespace=namespace)

    def update(self, name, data, namespace):
        secret = self._build_secret(name, data, namespace)
        return self._run('put', ['secrets', name], secret, namespace=namespace,
                         rest=True)

    def delete(self, name, namespace):
        return self._run('delete', ['secrets', name], namespace=namespace)

    class ErrorBase(Exception):
        def __init__(self, data):
            self.data = data
            message = data.get('message')
            super(K8sSecretsClient.ErrorBase, self).__init__(message)

    class K8sApiError(ErrorBase):
        pass

    class UnknownAnswer(ErrorBase):
        def __init__(self, data):
            self.data = data
            message = data.get('message')
            if message is None:
                message = data
            super(K8sSecretsClient.UnknownAnswer, self).__init__(message)


class K8sSecretsBuilder(object):
    DOCKERHUB_INDEX = 'https://index.docker.io/v1/'

    @classmethod
    def build_secret_data(cls, username, password, registry):
        """Prepare secret for saving in k8s."""
        if registry.endswith('docker.io'):
            registry = cls.DOCKERHUB_INDEX
        auth = base64.urlsafe_b64encode('{0}:{1}'.format(username, password))
        secret = {registry: {'auth': auth, 'email': 'a@a.a'}}
        encoded_secret = base64.urlsafe_b64encode(json.dumps(secret))
        return {'.dockercfg': encoded_secret}

    @classmethod
    def parse_secret_data(cls, secret_data):
        """Parse secret got from k8s.

        Returns dict
        {registry:
          {'auth':
            {'username': username,
             'password': password
            }
          },
          ...
        }
        """
        rv = {}
        dockercfg = json.loads(base64.urlsafe_b64decode(
            str(secret_data.get('.dockercfg'))))
        for registry, data in dockercfg.iteritems():
            username, password = base64.urlsafe_b64decode(
                str(data['auth'])).split(':', 1)
            # only index.docker.io in .dockercfg allowes to use image url
            # without the registry, like wncm/mynginx.
            # Replace it back to default registry
            if registry == cls.DOCKERHUB_INDEX:
                registry = settings.DEFAULT_REGISTRY
            rv[registry] = {
                'auth': {'username': username, 'password': password}
            }
        return rv
