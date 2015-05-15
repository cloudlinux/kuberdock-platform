import ipaddress
import random
import re
import requests
import shlex
import string
from ..core import db
from ..users.models import User
from ..pods.models import Pod, PodIP
from ..api import APIError
from ..utils import get_api_url

from flask import current_app

class KubeQuery(object):
    
    def _compose_args(self, json=False):
        args = {}
        if json:
            args['headers'] = {'Content-Type': 'application/json'}
        return args
    
    def _raise_error(self, error_string):
        if self.json:
            raise SystemExit(json.dumps({'status': 'ERROR', 'message': error_string}))
        else:
            raise SystemExit(error_string)
    
    def _make_url(self, res):
        if res is not None:
            return get_api_url(*res)
        return get_api_url()
    
    def _return_request(self, req):
        try:
            return req.json()
        except (ValueError, TypeError):
            return req.text
    
    def _get(self, res=None, params=None):
        args = self._compose_args()
        if params:
            args['params'] = params
        return self._run('get', res, args)

    def _post(self, res, data, rest=False):
        args = self._compose_args(rest)
        args['data'] = data
        return self._run('post', res, args)
    
    def _put(self, res, data, rest=False):
        args = self._compose_args(rest)
        args['data'] = data
        return self._run('put', res, args)
    
    def _del(self, res):
        args = self._compose_args()
        return self._run('del', res, args)
        
    def _run(self, act, res, args):
        dispatcher = {
            'get': requests.get,
            'post': requests.post,
            'put': requests.put,
            'del': requests.delete
        }
        try:
            req = dispatcher.get(act, 'get')(self._make_url(res), **args)
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
        pod = Pod(name=self.name, config=data, id=self.id, status='stopped')
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

class Utilities(object):
    
    @staticmethod
    def _parse_cmd_string(s):
        lex = shlex.shlex(s, posix=True)
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
    
    def _raise_if_failure(self, rv, message=None):
        if message is None:
            message = 'An error occurred'
        status = rv.get('status')
        if status is not None and status.lower() not in ['success', 'working']:
            self._raise(message)
            
    def _make_dash(self):
        return '-'.join(re.split(r'[\s\\/\[\|\]{}\(\)\._]+', self.name))
    
    def _make_sid(self):
        sid = ''.join(
            map((lambda x: x.lower()), re.split(r'[\s\\/\[\|\]{}\(\)\._]+',
                self.name)))
        sid += ''.join(random.sample(string.lowercase + string.digits, 20))
        return sid
    
    def _make_name_from_image(self, image):
        n = '-'.join(map((lambda x: x.lower()), image.split('/')))
        return "%s-%s" % (n, ''.join(random.sample(string.lowercase + string.digits, 10)))
