import ipaddress
import json
import random
import re
import requests
import shlex
import string
from ..core import db
from ..pods.models import Pod, PodIP
from ..billing.models import Kube
from ..api import APIError
from ..utils import get_api_url

from flask import current_app

class KubeQuery(object):
    return_json=True

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
        if self._json:
            raise SystemExit(
                json.dumps(
                    {'status': 'ERROR',
                     'message': error_string}))
        else:
            raise SystemExit(error_string)

    @staticmethod
    def _make_url(res, use_v3=False):
        """
        Composes a full URL
        :param res: list -> list of URL path items
        """
        kw = {'use_v3': use_v3}
        if res is not None:
            return get_api_url(*res, **kw)
        return get_api_url(**kw)

    def _return_request(self, req):
        try:
            if self.return_json:
                return req.json()
            return req.text
        except (ValueError, TypeError), e:
            raise APIError("Cannot process request: {0}".format(str(e)))

    def _get(self, res=None, params=None, use_v3=False):
        """
        GET request wrapper.
        :param res: list of URL path items
        :param params: dict -> request params
        """
        args = self._compose_args()
        if params:
            args['params'] = params
        return self._run('get', res, args, use_v3)

    def _post(self, res, data, rest=False, use_v3=False):
        args = self._compose_args(rest)
        args['data'] = data
        return self._run('post', res, args, use_v3)

    def _put(self, res, data, rest=False, use_v3=False):
        args = self._compose_args(rest)
        args['data'] = data
        return self._run('put', res, args, use_v3)

    def _del(self, res, use_v3=False):
        args = self._compose_args()
        return self._run('del', res, args, use_v3)

    def _run(self, act, res, args, use_v3):
        dispatcher = {
            'get': requests.get,
            'post': requests.post,
            'put': requests.put,
            'del': requests.delete
        }
        try:
            req = dispatcher.get(act, requests.get)(self._make_url(res, use_v3), **args)
            return self._return_request(req)
        except requests.exceptions.ConnectionError, e:
            return self._raise_error(str(e))


class ModelQuery(object):

    def _fetch_pods(self, users=False, live_only=True):
        if users:
            if live_only:
                return db.session.query(Pod).join(Pod.owner).filter(Pod.status!='deleted')
            return db.session.query(Pod).join(Pod.owner)
        if live_only:
            return db.session.query(Pod).filter(Pod.status!='deleted')
        return db.session.query(Pod)



    def _check_pod_name(self):
        if not hasattr(self, 'name'):
            return
        pod = Pod.query.filter_by(name=self.name).first()
        if pod:
            raise APIError(
                "Conflict. Pod with name = '{0}' already exists. "
                       "Try another name.".format(self.name),
                       status_code=409)

    def _free_ip(self, ip=None):
        if hasattr(self, 'public_ip'):
            podip = PodIP.filter_by(
                ip_address=int(ipaddress.ip_address(self.public_ip)))
            podip.delete()

    def _save_pod(self, data, owner):
        kube_type = data.get('kube_type', 0)
        pod = Pod(name=self.name, config=json.dumps(data), id=self.id, status='stopped')
        kube = db.session.query(Kube).get(kube_type)
        if kube is None:
            kube = db.session.query(Kube).get(0)
        pod.kube = kube
        pod.owner = owner
        try:
            db.session.add(pod)
            db.session.commit()
            return pod
        except Exception, e:
            current_app.logger.debug(e)
            db.session.rollback()

    def _mark_pod_as_deleted(self, pod):
        p = db.session.query(Pod).get(pod.id)
        if p is not None:
            p.name += '__' + ''.join(random.sample(string.lowercase + string.digits, 8))
            p.status = 'deleted'
        db.session.commit()

    def get_config(self, param=None, default=None):
        db_pod = db.session.query(Pod).get(self.id)
        if param is None:
            return json.loads(db_pod.config)
        return json.loads(db_pod.config).get(param, default)

    @staticmethod
    def _update_pod_config(pod, **attrs):
        db_pod = db.session.query(Pod).get(pod.id)
        try:
            data = json.loads(db_pod.config)
            data.update(attrs)
            db_pod.config = json.dumps(data)
            db.session.commit()
        except Exception:
            db.session.rollback()


class Utilities(object):

    @staticmethod
    def _parse_cmd_string(cmd_string):
        lex = shlex.shlex(cmd_string, posix=True)
        lex.whitespace_split = True
        lex.commenters = ''
        lex.wordchars += '.'
        try:
            return list(lex)
        except ValueError:
            raise APIError('Incorrect cmd string')

    @staticmethod
    def _raise(message, code=409):
        raise APIError(message, status_code=code)

    def _raise_if_failure(self, return_value, message=None):
        """
        Raises error if return value has key 'status' and that status' value
        neither 'success' nor 'working' (which means failure)
        :param return_value: dict
        :param message: string
        """
        pass
        #if message is None:
        #    message = 'An error occurred'
        #status = return_value.get('status')
        #if status is not None and status.lower() not in ['success', 'working']:
        #    self._raise(message)

    def _make_dash(self):
        """
        Substitutes certain symbols for dashes to make DNS-compatible string
        """
        return '-'.join(re.split(r'[\s\\/\[\|\]{}\(\)\._]+', self.name))

    def _make_sid(self):
        sid = ''.join(
            map((lambda x: x.lower()), re.split(r'[\s\\/\[\|\]{}\(\)\._]+',
                self.name)))
        sid += ''.join(random.sample(string.lowercase + string.digits, 20))
        return sid

    @staticmethod
    def _make_name_from_image(image):
        """
        Appends random part to image
        :param image: string -> image name
        """
        n = '-'.join(map((lambda x: x.lower()), image.split('/')))
        return "%s-%s" % (n, ''.join(
            random.sample(string.lowercase + string.digits, 10)))

    def _forge_dockers(self, obj=None):
        if obj is None:
            obj = self
        obj.dockers = []
        for container in obj.containers:
            container['imageID'] = 'docker://'
            obj.dockers.append({
                'host': '',
                'info': {
                    'containerID': 'docker://',
                    'image': container['image'],
                    'imageID': container['imageID'],
                    'lastState': {},
                    'ready': False,
                    'restartCount': 0,
                    'state': {'stopped': {}}}})

