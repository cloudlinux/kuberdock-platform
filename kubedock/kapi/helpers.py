import base64
import ipaddress
import json
import random
import re
import requests
import shlex
import string
from ..core import db
from ..users.models import User
from ..pods.models import Pod, PodIP, PersistentDrive
from ..nodes.models import Node
from ..api import APIError
from ..utils import get_api_url

from flask import current_app

class KubeQuery(object):
    _json=True

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
    def _make_url(res):
        """
        Composes a full URL
        :param res: list -> list of URL path items
        """
        if res is not None:
            return get_api_url(*res)
        return get_api_url()

    @staticmethod
    def _return_request(req):
        """
        Return a request and catch an exception if occurs
        :param req: requests object
        """
        try:
            return req.json()
        except (ValueError, TypeError):
            return req.text

    def _get(self, res=None, params=None):
        """
        GET request wrapper.
        :param res: list of URL path items
        :param params: dict -> request params
        """
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
            req = dispatcher.get(act, requests.get)(self._make_url(res), **args)
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

    def _make_persistent_drives(self, pod, data):
        """
        Get from data return from kubernetes volume-related info,
        find scriptableDisk and eigher add decoded data to database or update
        a db record.
        :param pod: Pod instance
        :param data: dict -> data returned from kubernetes after a pod creation
        """
        kub_id = data.get('uid') # UUID returned by kubernetes
        volumes = data.get('desiredState', {}).get('manifest', {}).get('volumes', [])
        for volume in volumes:
            disk = volume.get('source', {}).get('scriptableDisk')
            if disk:
                args = base64.b64decode(disk['params']).split(';')
                if len(args) > 2:  # name and size given means a new volume
                    pd = PersistentDrive(pod_id=pod.id, kub_id=kub_id, name=args[1],
                                    owner=pod.owner, size=int(args[2]),
                                    status='mounted')
                    db.session.add(pd)
                elif len(args) == 2:    # not given size means reusing an old volume
                    #check if an entry exists in DB
                    db_vol = db.session.query(
                        PersistentDrive).filter_by(name=args[1]).first()
                    if db_vol is None:  # found none and create
                        pd = PersistentDrive(pod_id=pod.id, kub_id=kub_id, name=args[1],
                                        owner=pod.owner, size=1024,
                                        status='mounted')
                        db.session.add(pd)
                    else:
                        db_vol.status = 'mounted'
                        db_vol.kub_id = kub_id
                        db_vol.pod_id = pod.id
                else:
                    raise APIError("Wrong number of persistent drive arguments")
        db.session.commit()

    @staticmethod
    def _get_persistent_drives(kub_id):
        """
        Returns persistent drives names according to received kubernetes pod ID
        :param kub_id: string -> UUID
        """
        drives = db.session.query(PersistentDrive).filter_by(kub_id=kub_id)
        return [d.name for d in drives]

    def _get_node_persistent_drives(self, ip_address, kub_ip):
        """
        Returns persistent drives names according to received kubernetes pod ID.
        But if the remote address is not amongst node addresses return
        empty list
        :param kub_id: string -> UUID
        """
        node = db.session.query(Node).filter_by(ip=ip_address).first()
        if node is None:
            return []
        return self._get_persistent_drives(kub_ip)


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
        if message is None:
            message = 'An error occurred'
        status = return_value.get('status')
        if status is not None and status.lower() not in ['success', 'working']:
            self._raise(message)

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

