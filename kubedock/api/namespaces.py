import json
import requests
from flask import Blueprint, request, jsonify, current_app
from flask.ext.login import current_user

from ..rbac import check_permission
from ..utils import login_required_or_basic, get_api_url
from ..settings import KUBE_API_VERSION, DEBUG
from ..api import APIError
from ..api.entities.pod import PodEntity
from ..users.models import User
from ..users.signals import user_get_setting, user_set_setting


pods = Blueprint('namespaces', __name__, url_prefix='/namespaces')


@pods.route('/', methods=['GET'])
@login_required_or_basic
@check_permission('get', 'namespaces')
def get_namespaces():
    namespaces = Namespaces.get()
    return jsonify({'status': 'OK', 'data': namespaces})


@pods.route('/', methods=['POST'])
@login_required_or_basic
@check_permission('create', 'namespaces')
def create_namespaces():
    """
    Create a namespace
    """
    podname = request.form.get('pod_name')
    config = Namespaces.make_config(current_user.username, podname)
    result = Namespaces.create(config)
    return jsonify({'status': 'OK'})


@pods.route('/', methods=['POST'])
@login_required_or_basic
@check_permission('create', 'namespaces')
def get_user_namespaces():
    """
    Return user's namespaces
    :return: list
    """
    username = request.form.get('pod_name')
    user = User.query.filter_by(username=username).first()
    if user is None:
        raise APIError('User not found: {0}'.format(username))
    namespaces_names_list = [Namespaces._make_namespace_name(username, p.name)
                             for p in user.pods]
    namespaces_list = [Namespaces.get(ns) for ns in namespaces_names_list]
    return jsonify({'status': 'OK', 'data': namespaces_list})


###################
### namespaces ####
class Namespaces(object):
    """
    A Namespace is a mechanism to partition resources created by users into a
    logically named group.
    https://github.com/GoogleCloudPlatform/kubernetes/blob/master/docs/design/namespaces.md
    API: http://kubernetes.io/third_party/swagger-ui/
    """

    API_HEADERS = {'Content-type': 'application/json'}

    @classmethod
    def _user_namespaces_from_db(cls, user_id=None):
        user_id = user_id or current_user.id
        if user_id <= 0:
            return []
        user_namespaces = user_get_setting.send((user_id, 'namespaces'))[0][1] or []
        return user_namespaces

    @classmethod
    def _append_user_namespace(cls, namespace, user_id=None):
        user_id = user_id or current_user.id
        if user_id <= 0:
            return
        user_namespaces = user_get_setting.send((user_id, 'namespaces'))[0][1]
        if user_namespaces is None:
            user_namespaces = []
        if namespace not in user_namespaces:
            user_namespaces.append(namespace)
            user_set_setting.send((user_id, 'namespaces', user_namespaces))

    @classmethod
    def _delete_user_namespace(cls, namespace, user_id=None):
        user_id = user_id or current_user.id
        if user_id <= 0:
            return
        user_namespaces = user_get_setting.send(
            (user_id, 'namespaces'))[0][1] or []
        if namespace in user_namespaces:
            user_namespaces = [ns for ns in user_namespaces if ns != namespace]
            user_set_setting.send((user_id, 'namespaces', user_namespaces))

    @classmethod
    def _make_namespace_name(cls, username, podname):
        """
        Returns the namespace name that consist from to parts: username and pod name
        :param username: string
        :param podname: string
        :return: string: 'user-mysql'
        """
        return '{0}-{1}'.format(username, podname)

    @staticmethod
    def all():
        """
        Returns all namespaces from kubernetes
        URL: GET /api/v1beta3/namespaces
        :return: dict: {
            "apiVersion": "",
            "items": [
                {
                    "annotations": "any",
                    "apiVersion": "",
                    "creationTimestamp": "",
                    "deletionTimestamp": "",
                    "generateName": "",
                    "kind": "",
                    "labels": "any",
                    "name": "",
                    "namespace": "",
                    "resourceVersion": "",
                    "selfLink": "",
                    "spec": {
                        "finalizers": [
                            {}
                        ]
                    },
                    "status": {
                        "phase": ""
                    },
                    "uid": ""
                },
                ...
            ],
            "kind": "",
            "resourceVersion": "",
            "selfLink": ""
        }
        """
        url = get_api_url('namespaces', use_v3=True, namespace=False)
        res = requests.get(url=url)
        return res.json()

    @classmethod
    def get(cls, ns_name):
        """
        Returns the namespace object by namespace name
        URL: GET /api/v1beta3/namespaces/{name}
        :param ns_name: string
        :return: dict: {
            "annotations": "any",
            "apiVersion": "",
            "creationTimestamp": "",
            "deletionTimestamp": "",
            "generateName": "",
            "kind": "",
            "labels": "any",
            "name": "",
            "namespace": "",
            "resourceVersion": "",
            "selfLink": "",
            "spec": {
                "finalizers": [
                    {}
                ]
            },
            "status": {
                "phase": ""
            },
            "uid": ""
        }
        """
        url = get_api_url(namespace=ns_name, use_v3=True)
        r = requests.get(url=url)
        try:
            res = r.json()
            if 'code' in res and res['code'] == 404:
                current_app.logger.warning(
                    'Namespaces.get({0}) failed: {1}'.format(
                        ns_name, res['message']))
                return None
            return res
        except Exception, e:
            current_app.logger.warning('Namespaces.get({0}) failed: {1}'.format(
                ns_name, e))
            return None

    @classmethod
    def create(cls, namespace, user_id=None):
        """
        Create a namespace
        URL: POST /api/v1beta3/namespaces
        :param namespace: string: namespace name
        :param user_id: if not passed, use current user's Id
        :return: dict: {
            "annotations": "any",
            "apiVersion": "",
            "creationTimestamp": "",
            "deletionTimestamp": "",
            "generateName": "",
            "kind": "",
            "labels": "any",
            "name": "",
            "namespace": "",
            "resourceVersion": "",
            "selfLink": "",
            "spec": {
                "finalizers": [
                    {}
                ]
            },
            "status": {
                "phase": ""
            },
            "uid": ""
        }
        """
        namespace = namespace.lower()
        url = get_api_url('namespaces', use_v3=True, namespace=False)
        ns = cls.get(namespace)
        if ns:
            return ns
        config = cls.make_config(namespace)
        r = requests.post(url=url, json=config, headers=cls.API_HEADERS)
        res = r.json()
        if res['metadata']['name'] == namespace:
            cls._append_user_namespace(namespace, user_id=user_id)
        return res

    @classmethod
    def update(cls, namespace, config):
        """
        Update namespace
        URL: PUT /api/v1beta3/namespaces/{name}
        :param namespace: string
        :param config: json (or dict) see docstring of method create(...)
        :return: dict: {...} see docstring of method create(...)
        """
        namespace = namespace.lower()
        url = get_api_url('namespaces', namespace=namespace, use_v3=True)
        r = requests.put(url=url, json=config, headers=cls.API_HEADERS)
        return r.json()

    @classmethod
    def delete(cls, namespace, user_id=None):
        """
        Delete namespace
        URL: DELETE /api/v1beta3/namespaces/{name}
        :param namespace: string
        :param user_id: if not passed, use current user's Id
        :return: dict: {
            "kind": "Namespace",
            "id": "user-mysql",
            "uid": "c1063a3c-edb8-11e4-81b6-001c42768cd7",
            "creationTimestamp": "2015-04-28T15:10:49Z",
            "selfLink": "/api/v1beta2/namespaces/user-mysql",
            "resourceVersion": 162835,
            "apiVersion": "v1beta3",
            "deletionTimestamp": "2015-04-28T15:10:49Z",
            "labels": {
                "name": "user-mysql"
            },
            "spec": {
                "finalizers": [
                    "kubernetes"
                ]
            },
            "status": {
                "phase": "Terminating"
            }
        }
        """
        namespace = namespace.lower()
        ns = cls.get(namespace)
        if ns is None:
            current_app.logger.warning(
                'Namespaces.delete({0}) does not exist'.format(namespace))
            return
        url = get_api_url(namespace=namespace, use_v3=True)
        current_app.logger.debug(url)
        r = requests.delete(url=url)
        res = r.json()
        current_app.logger.debug(res)
        if res['metadata']['name'] == namespace:
            cls._delete_user_namespace(namespace, user_id=user_id)
        return res

    @classmethod
    def finalize(cls, namespace):
        """
        Finalize namespace
        URL: PUT /api/v1beta3/namespaces/{name}/finalize
        :param name: string
        :return:
        """
        namespace = namespace.lower()
        url = get_api_url('finalize', namespace=namespace, use_v3=True)
        r = requests.put(url=url)
        return r.json()

    @classmethod
    def watch(cls, callback):
        """
        Watch all namespaces
        URL: GET /api/v1beta3/watch/namespaces
        :param callback: response wrapper
        :return: stream
        """
        url = get_api_url('watch', 'namespaces', namespace=False, use_v3=True)
        r = requests.get(url=url, stream=True)
        lines = r.iter_lines()
        callback(json.loads(next(lines)))
        for line in lines:
            # filter out keep-alive new lines
            if line:
                callback(json.loads(line))

    @classmethod
    def make_config(cls, namespace):
        """
        Generate config object to create a new namespace
        :param namespace: string
        :return: dict: {
            "kind": "Namespace",
            "apiVersion": 'v1beta3,
            "id": "my-namespace,
            "metadata": {
                "name": "my-namespace"
            },
            "spec": {},
            "status": {},
            "labels": {
                "name": "my-namespace"
            }
        }
        """
        namespace = namespace.lower()
        config = {
            "kind": "Namespace",
            "apiVersion": KUBE_API_VERSION,
            "id": namespace,
            "metadata": {
                "name": namespace
            },
            "spec": {},
            "status": {},
            "labels": {
                "name": namespace
            }
        }
        return config


class NamespacesPods(Namespaces):
    """
    Namespaces Pods
    """
    def __init__(self, namespace):
        self.namespace = namespace

    @staticmethod
    def _default_pods():
        """
        Returns default Pods list
        :return:
        """
        url = get_api_url('pods', use_v3=True)
        r = requests.get(url=url)
        pods = r.json()
        return pods['items']

    @staticmethod
    def _default_services():
        """
        Returns default Services list
        :return: [
            {
                "kind": "Service",
                "apiVersion": "v1beta3",
                "metadata": {
                    "name": "redis-service-x9r8f",
                    "generateName": "redis-service-",
                    "namespace": "user-redis-pods",
                    "selfLink": "/api/v1beta1/services/redis-service-x9r8f?namespace=user-redis-pods",
                    "uid": "435484cd-f968-11e4-93a8-001c42768cd7",
                    "resourceVersion": "86679",
                    "creationTimestamp": "2015-05-13T12:04:52Z",
                    "labels": {
                        "name": "redis-service"
                    },
                    "annotations": {
                        "public-ip-state": "{\"assigned-public-ip\": null}"
                    }
                },
                "spec": {
                    "ports": [
                        {
                            "name": "c0-p0",
                            "protocol": "tcp",
                            "port": 6379,
                            "targetPort": 6379
                        }
                    ],
                    "selector": {
                        "name": "redis"
                    },
                    "portalIP": "10.254.143.210",
                    "sessionAffinity": "None"
                },
                "status": {}
            },
            ...
        ]
        """
        url = get_api_url('services', use_v3=True)
        r = requests.get(url=url)
        pods = r.json()
        return pods['items']

    @property
    def pods(self):
        """
        Returns the list of pods assigned in namespace
        :return:
        """
        url = get_api_url('pods', namespace=self.namespace, use_v3=True)
        r = requests.get(url=url)
        res = r.json()
        pods = res['items']
        return pods

    @property
    def pods_entities(self):
        """
        Returns a list of pods (PodEntity)
        :return:
        """
        return [PodEntity(data) for data in self.pods]

    @property
    def services(self):
        """
        Returns the list of services assigned in namespace
        :return:
        """
        url = get_api_url('services', namespace=self.namespace, use_v3=True)
        r = requests.get(url=url)
        res = r.json()
        services = res['items']
        return services

    def get(self, name):
        """
        Returns Pod by name
        :param name: pod's name
        :return:
        """
        url = get_api_url('pods', name, namespace=self.namespace, use_v3=True)
        r = requests.get(url=url)
        return r.json()

    def delete(self, name):
        """
        Returns Pod by name
        :param name: pod's name
        :return:
        """
        url = get_api_url('pods', name, namespace=self.namespace, use_v3=True)
        r = requests.delete(url=url)
        return r.json()


    def stop(self, name):
        """
        Delete Pod from namespace
        :param name:
        :return:
        """
        url = get_api_url('pods', name, namespace=self.namespace, use_v3=True)
        r = requests.delete(url=url)
        res = r.text
        return json.loads(res)

    @classmethod
    def user_pods(cls, username=None, from_server=None):
        """
        Returns user's pods by username
        :param username: user name
        :param from_server: Get user's namespaces from kubernetes if not None
        :return: list
        """
        if DEBUG: # always get user's namespaces form kubernetes in debug mode
            from_server = True
        user_namespaces = []
        if username is None or current_user.username == username:
            user_namespaces = cls._user_namespaces_from_db(current_user.id)
        else:
            from_server = True
        if from_server:
            ns_prefix = '{0}-'.format(username)
            ns_sufix = '-pods'
            namespaces_list = super(NamespacesPods, cls).all()['items']
            user_namespaces.extend([
                ns['metadata']['name'] for ns in namespaces_list
                if ns['metadata']['name'].startswith(ns_prefix)
                and ns['metadata']['name'].endswith(ns_sufix)
            ])
        user_namespaces = set(user_namespaces)
        pods_list = cls._default_pods()
        for namespace in user_namespaces:
            pods_list.extend(cls(namespace).pods)
        return pods_list

    @classmethod
    def user_services(cls, username=None, from_server=None):
        """
        Returns user's services by username
        :param username: user name
        :param from_server: Get user's namespaces from kubernetes if not None
        :return: list of services
        """
        if DEBUG: # always get user's namespaces form kubernetes in debug mode
            from_server = True
        user_namespaces = []
        if username is None or current_user.username == username:
            user_namespaces = cls._user_namespaces_from_db(current_user.id)
        else:
            from_server = True
        if from_server:
            ns_prefix = '{0}-'.format(username)
            ns_sufix = '-pods'
            namespaces_list = super(NamespacesPods, cls).all()['items']
            user_namespaces.extend([
                ns['metadata']['name'] for ns in namespaces_list
                if ns['metadata']['name'].startswith(ns_prefix)
                and ns['metadata']['name'].endswith(ns_sufix)
            ])
        user_namespaces = set(user_namespaces)
        services_list = cls._default_services()
        for namespace in user_namespaces:
            services_list.extend(cls(namespace).services)
        return services_list

    @classmethod
    def all_pods(cls):
        """
        Returns all namespaces
        :return: list
        """
        all_namespaces = cls.all()
        pods_namespaces = [ns.endswith('-pods') for ns in all_namespaces]
        pods_list = []
        for namespace in pods_namespaces:
            pods_list.extend(cls(namespace).pods)
        return pods_list
