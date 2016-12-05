import cookielib
import itertools
import json
import logging
import pipes
import re
import sys
import urllib
import urllib2
from contextlib import closing
from urlparse import urlparse

import requests
from requests.exceptions import ConnectionError, Timeout

from tests_integration.lib import exceptions
from tests_integration.lib import utils
from tests_integration.lib.exceptions import \
    PodResizeError
from tests_integration.lib.utils import assert_eq, assert_in

DEFAULT_WAIT_PORTS_TIMEOUT = 6 * 60


logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger("paramiko").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
LOG = logging.getLogger(__name__)


class RESTMixin(object):
    # Expectations:
    # self.host
    HTTP_PORT = None

    def _build_url(self, scheme, port, path):
        if port:
            url = '{0}://{1}:{2}{3}'.format(scheme, self.host, port, path)
        else:
            url = '{0}://{1}{2}'.format(scheme, self.host, path)
        return url

    def do_GET(self, scheme="http", path='/', port=None, timeout=10,
               exp_retcodes=None, fetch_subres=False, verbose=True):
        url = self._build_url(scheme, port, path)

        LOG.debug("Issuing GET to {0}".format(url))
        with closing(urllib2.urlopen(url, timeout=timeout)) as req:
            body = unicode(req.read(), 'utf-8')
            code = req.code
        LOG.debug("GET {} status: {}".format(url, code))
        if verbose:
            LOG.debug(u"Response:\n{0}".format(body))

        if exp_retcodes:
            assert_in(code, exp_retcodes)

        if fetch_subres:
            self._fetch_subresources(body, urlparse(url).netloc)

        return body

    def _fetch_subresources(self, html, netloc):

        def parse(_html, _sess, _netloc):
            tag_patt = re.compile(r"""<(?:link|img|script)[^>]*>""")
            resource_patt = re.compile(r"""(?:href|src)=["']([^"']+)""")
            tags = tag_patt.findall(_html)
            for tag in tags:
                if tag.startswith('<link') and 'stylesheet' not in tag:
                    continue
                m = resource_patt.search(tag)
                if not m:
                    continue
                href = m.group(1)
                if _netloc not in href:
                    continue
                fetch(href, _sess)

        def fetch(_href, _sess):
            try:
                resp = _sess.get(_href)
                parse(resp.text, _sess, urlparse(_href).netloc)
            except (ConnectionError, Timeout):
                pass

        parse(html, requests.Session(), netloc)

    def do_POST(self, scheme="http", path='/', port=None, timeout=10,
                body=None, opener=None, exp_retcodes=None, verbose=True):
        url = self._build_url(scheme, port, path)
        data = urllib.urlencode(body or {})

        LOG.debug("Issuing POST to {0}".format(url))
        if opener:
            req = opener.open(url, data=data, timeout=timeout)
        else:
            req = urllib2.urlopen(url, data=data, timeout=timeout)
        resp = unicode(req.read(), 'utf-8')
        code = req.code

        LOG.debug("POST {} status: {}".format(url, code))
        if verbose:
            LOG.debug(u"Response:\n{0}".format(resp))

        if exp_retcodes:
            assert_in(code, exp_retcodes)

        return resp

    def wait_http_resp(self, scheme="http", path='/', port=None, code=200,
                       timeout=10, tries=30, interval=3):
        port = port or self.HTTP_PORT
        url = self._build_url(scheme, port, path)
        LOG.debug('Expecting for response code {code} on url {url}, '
                  'total retries: {tries}'.format(
                      code=code, url=url, tries=tries, port=port))

        def check(*args, **kwargs):
            with closing(urllib2.urlopen(url, timeout=timeout)) as req:
                assert_eq(req.code, code)

        utils.retry(check, tries=tries, interval=interval)

    def get_opener(self, scheme="http", path='/', port=None, timeout=5,
                   body=None):
        url = self._build_url(scheme, port, path)
        cj = cookielib.CookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
        login_data = urllib.urlencode(body)
        opener.open(url, login_data)
        return opener


class Port(object):
    def __init__(self, port, proto='tcp', container_port=None, public=False):
        self.port = port
        self.proto = proto
        self.container_port = container_port if container_port else port
        self.is_public = public

    def __str__(self):
        return "<port={0} proto='{1}' container_port={2}>".format(
            self.port, self.proto, self.container_port)


class KDPod(RESTMixin):
    # Image or PA name
    SRC = None
    WAIT_PORTS_TIMEOUT = DEFAULT_WAIT_PORTS_TIMEOUT

    def __init__(self, cluster, image, name, kube_type, kubes,
                 open_all_ports, restart_policy, pvs, owner):
        self.cluster = cluster
        self.name = name
        self.image = image
        self.kube_type = kube_type
        self.kubes = kubes
        self.restart_policy = restart_policy
        self.owner = owner
        self.pvs = pvs
        self.open_all_ports = open_all_ports

    @property
    def containers(self):
        return self.get_spec().get('containers', [])

    @property
    def public_ip(self):
        spec = self.get_spec()
        return spec.get('public_ip')

    @property
    def domain(self):
        spec = self.get_spec()
        return spec.get('domain') or spec.get('public_aws')

    @property
    def host(self):
        # TODO add generic caching mechanism, define cacheable fields
        if getattr(self, "_cached_host", None) is None:
            self._cached_host = self.public_ip or self.domain
        return self._cached_host

    @property
    def pod_id(self):
        if getattr(self, "_cached_pod_id", None) is None:
            self._cached_pod_id = self.get_spec()['id']
        return self._cached_pod_id

    @property
    def ports(self):
        def _get_ports(containers):
            all_ports = itertools.chain.from_iterable(
                c['ports'] for c in containers if c.get('ports'))
            return [port.get('hostPort') or port.get('containerPort')
                    for port in all_ports if port.get('isPublic') is True]

        spec = self.get_spec()
        return _get_ports(spec['containers'])

    @classmethod
    def create(cls, cluster, image, name, kube_type, kubes, open_all_ports,
               restart_policy, pvs, owner, password, domain, ports=None):
        """
        Create new pod in kuberdock
        :param open_all_ports: if true, open all ports of image (does not mean
            these are Public IP ports, depends on a cluster setup)
        :param ports: List of Port objects or None. Port objects contain
            information about pod-to-container port mapping as well as whether
            port is public or not (a way to make some ports public).
            In case of 'None' - container image ports will be used and
            pod ports will default to container ports.
        :return: object via which Kuberdock pod can be managed
        """

        def _get_image_ports(img):
            _, out, _ = cluster.kcli(
                'image_info {}'.format(img), out_as_dict=True, user=owner)

            return [
                Port(int(port['number']), port['protocol'])
                for port in out['ports']]

        def _update_image_ports(image_ports, ports):
            for p in ports:
                try:
                    image_port = next(i for i in image_ports
                                      if i.container_port == p.container_port)
                    image_port.is_public = p.is_public
                    image_port.port = p.port
                except StopIteration:
                    raise Exception(
                        "Port '{port}:{proto}' was not found in container "
                        "image ports".format(port=p.container_port,
                                             proto=p.proto))
            return image_ports

        def _ports_to_dict(ports):
            """
            :return: list of dictionaries with ports, necessary for
            creation of general pod via kcli2
            """
            ports_list = []
            for port in ports:
                ports_list.append(dict(containerPort=port.container_port,
                                       hostPort=port.port,
                                       isPublic=(open_all_ports or
                                                 port.is_public),
                                       protocol=port.proto))
            return ports_list

        escaped_name = pipes.quote(name)
        kube_types = {
            "Tiny": 0,
            "Standard": 1,
            "High memory": 2
        }
        pod_spec = dict(kube_type=kube_types[kube_type],
                        restartPolicy=restart_policy,
                        name=escaped_name)
        container = dict(kubes=kubes, image=image,
                         name=utils.get_rnd_low_string(length=11))
        image_ports = utils.retry(_get_image_ports, img=image)
        if ports is None:
            pod_ports = image_ports
        else:
            pod_ports = _update_image_ports(image_ports, ports)
        container.update(ports=_ports_to_dict(pod_ports))
        if pvs is not None:
            container.update(volumeMounts=[pv.volume_mount_dict for pv in pvs])
            pod_spec.update(volumes=[pv.volume_dict for pv in pvs])
        pod_spec.update(containers=[container], replicas=1)
        if domain:
            pod_spec["domain"] = domain
        pod_spec = json.dumps(pod_spec, ensure_ascii=False)

        _, out, _ = cluster.kcli2(u"pods create '{}'".format(pod_spec),
                                  out_as_dict=True,
                                  user=owner,
                                  password=(password or owner))
        this_pod_class = cls._get_pod_class(image)
        return this_pod_class(cluster, image, name, kube_type, kubes,
                              open_all_ports, restart_policy, pvs, owner)

    @classmethod
    def restore(cls, cluster, user, file_path=None, pod_dump=None,
                pv_backups_location=None, pv_backups_path_template=None,
                flags=None, return_as_json=False):
        """
        Restore pod using "kdctl pods restore" command
        :return: instance of KDPod object.
        """

        def get_image(file_path=None, pod_dump=None):
            if pod_dump is None:
                _, pod_dump, _ = cluster.ssh_exec("master",
                                                  "cat {}".format(file_path))
            pod_dump = json.loads(pod_dump)
            container = pod_dump['pod_data']["containers"]
            if len(container) > 1:
                # In current implementation of KDPod class we cannot
                # manage consisting of more than on container, therefore
                # creation of such container is prohibited
                raise exceptions.CannotRestorePodWithMoreThanOneContainer(
                    "Unfortunately currently we cannot restore pod with more "
                    "than one container. KDPod class should be overwritten to "
                    "allow correct managing such containers to nake this "
                    "operation possible."
                )
            return pipes.quote(container[0]["image"])

        owner = pipes.quote(user)
        if return_as_json:
            cmd = "-j "
        else:
            cmd = ""
        if file_path and pod_dump:
            raise exceptions.IncorrectPodDescription(
                "Only file_path OR only pod_description should be "
                "privoded. Hoverwer provided both parameters."
            )
        elif file_path:
            image = get_image(file_path=file_path)
            cmd += u"pods restore -f {}" \
                .format(file_path)
        elif pod_dump:
            image = get_image(pod_dump=pod_dump)
            cmd += u"pods restore \'{}\'" \
                .format(pod_dump)
        else:
            raise exceptions.IncorrectPodDescription(
                "Either file_path or pod_description should not be empty")

        if pv_backups_location is not None:
            cmd += " --pv-backups-location={}".format(pv_backups_location)

        if pv_backups_path_template is not None:
            cmd += " --pv-backups-path-template={}".format(
                pv_backups_path_template)

        if flags is not None:
            cmd += " {}".format(flags)
        cmd += " --owner {}".format(owner)
        _, pod_description, _ = cluster.kdctl(cmd, out_as_dict=True)
        data = pod_description['data']
        name = data['name']
        kube_type = utils.kube_type_to_str(data['kube_type'])
        restart_policy = data['restartPolicy']
        this_pod_class = cls._get_pod_class(image)
        return this_pod_class(cluster, "", name, kube_type, "", True,
                              restart_policy, "", owner)

    @classmethod
    def get_internal_pod(cls, cluster, pod_name):
        """Get pod from kuberdock
        Create KDPod object modeling pod, which is already created in the
        Kuberdock. Will be used for finding and tracking pods of
        kuberdock-internal user
        :return: KDPod object modeling already existing pod
        """
        escaped_pod_name = pipes.quote(pod_name)
        cmd = u"pods get --name {} --owner kuberdock-internal".\
              format(escaped_pod_name)
        _, out, _ = cluster.kdctl(cmd, out_as_dict=True)
        spec = out["data"]
        return KDPod(cluster, None, pod_name, None, None, False,
                     spec["restartPolicy"], [], "kuberdock-internal")

    @classmethod
    def _get_pod_class(cls, image):
        pod_classes = {c.SRC: c for c in utils.all_subclasses(cls)}
        return pod_classes.get(image, cls)

    def command(self, command):
        data = dict(command=command)
        return self.cluster.kcli2(
            u"pods update --name {} '{}'".format(self.name, json.dumps(data)),
            user=self.owner,
            out_as_dict=True)

    def start(self):
        self.command("start")

    def stop(self):
        self.command("stop")

    def delete(self):
        self.cluster.kcli2(
            u"pods delete --name {}".format(self.escaped_name),
            user=self.owner)

    def redeploy(self, wipeOut=False, applyEdit=False):
        commands = {}
        if wipeOut is True:
            commands['wipeOut'] = wipeOut
        if applyEdit is True:
            commands['applyEdit'] = applyEdit

        data = {
            'command': 'redeploy', 'commandOptions': commands
        }
        self.cluster.kcli2(
            u"pods update --name {} '{}'".format(
                self.escaped_name, json.dumps(data), user=self.owner))

    def wait_for_ports(self, ports=None, timeout=None):
        # NOTE: we still don't know if this is in a routable network, so
        # open_all_ports does not exactly mean wait_for_ports pass.
        # But for sure it does not make sense to wait if no ports open.
        timeout = timeout or self.WAIT_PORTS_TIMEOUT
        if not (self.open_all_ports or self.ports):
            raise Exception("Cannot wait for ports on a pod with no"
                            " ports open")
        ports = ports or self.ports
        self._wait_for_ports(ports, timeout)

    def _wait_for_ports(self, ports, timeout):
        for p in ports:
            utils.wait_net_port(self.host, p, timeout)

    def wait_for_status(self, status, tries=50, interval=5, delay=0):
        utils.wait_for_status(self, status, tries, interval, delay)

    @property
    def node(self):
        return self.info.get('host')

    @property
    def info(self):
        try:
            _, out, _ = self.cluster.kubectl(
                u'get pod {}'.format(self.escaped_name), out_as_dict=True,
                user=self.owner)
            return out[0]
        except KeyError:
            raise exceptions.UnexpectedKubectlResponse()

    def events(self, event_type=None, event_source=None, event_reason=None):
        """Fetch events from pod namespace

        Possible filters:
            event_type: "type",
            event_source: "from:name"

        Example:
            pod.events(event_type='warning',
                       event_source='component:default-scheduler'
                       event_reason='FailedScheduling')
        """
        try:
            _, out, _ = self.cluster.true_kubectl(
                u'get events --namespace {}'.format(self.pod_id),
                out_as_dict=True)
            events = out['items']
        except KeyError:
            raise exceptions.UnexpectedKubectlResponse()

        def _filter(e):
            if event_reason and e['reason'].lower() != event_reason.lower():
                return

            if event_type and e['type'].lower() != event_type.lower():
                return

            if event_source and e['source'][
                    event_source.split(':')[0]] != event_source.split(':')[1]:
                return

            return True

        return filter(_filter, events)

    @property
    def status(self):
        """Calculate web-UI status of the pod
        Calculate the same status of the pod which would be displayed in the
        web-ui for user (see kubedock/frontend/static/js/app_data/model.js
        data.Pod.getPrettyStatus), this status distinguishes from what is
        returned in "status" field by podapi

        :return: pod's status calculated by front-end rules
        """
        spec = self.get_spec()
        status = spec['status']
        if status == "running" and not spec['ready']:
            return "pending"
        return status

    @property
    def escaped_name(self):
        return pipes.quote(self.name)

    @property
    def ssh_credentials(self):
        return utils.retry(self._get_creds, tries=10, interval=1)

    def _get_creds(self):
        direct_access = self.get_spec()['direct_access']
        links = [v.split('@') for v in direct_access['links'].values()]
        return {
            'password': direct_access['auth'],
            'users': [v[0] for v in links],
            'hosts': [v[1] for v in links]
        }

    def get_container_ip(self, container_id):
        """
        Returns internal IP of a given container within the current POD
        """
        _, out, _ = self.docker_exec(container_id, 'hostname --ip-address')
        return out

    def get_container_id(self, container_name=None, container_image=None):
        if not (container_name is None) ^ (container_image is None):
            raise ValueError('You need to specify either the container_name'
                             ' or container image')

        spec = self.get_spec()
        if container_name is not None:
            def predicate(c):
                return c['name'] == container_name
        elif container_image is not None:
            def predicate(c):
                return c['image'] == container_image

        try:
            container = next(c for c in
                             spec['containers']
                             if predicate(c))
        except StopIteration:
            LOG.error("Pod {} does not have {} container".format(
                self.name, container_name))
            raise

        utils.wait_for(lambda: container['containerID'] is not None)
        return container['containerID']

    def get_spec(self):
        cmd = u"pods get --name {} --owner {}".\
              format(self.escaped_name, self.owner)
        _, out, _ = self.cluster.kdctl(cmd, out_as_dict=True)
        return out["data"]

    def get_dump(self):
        cmd = u"pods dump {pod_id}".format(pod_id=self.pod_id)
        _, out, _ = self.cluster.kdctl(cmd, out_as_dict=True)
        rv = out['data']
        return rv

    def docker_exec(self, container_id, command, detached=False):
        if self.status != 'running':
            raise exceptions.PodIsNotRunning()

        node_name = self.info['host']
        args = '-d' if detached else ''
        docker_cmd = u'exec {} {} bash -c {}'.format(
            args, container_id, pipes.quote(command))
        return self.cluster.docker(docker_cmd, node_name)

    def healthcheck(self):
        LOG.warning(
            "This is a generic KDPod class health check. Inherit KDPod and "
            "implement health check for {0} image.".format(self.image))
        self._generic_healthcheck()

    def _generic_healthcheck(self):
        spec = self.get_spec()
        utils.assert_eq(spec['kube_type'],
                        utils.kube_type_to_int(self.kube_type))
        for container in spec['containers']:
            utils.assert_eq(container['kubes'], self.kubes)
        utils.assert_eq(spec['restartPolicy'], self.restart_policy)
        utils.assert_eq(spec['status'], "running")
        return spec

    def __get_edit_data(self):
        pod_spec = self.get_spec()
        edit_data = {
            "command": "edit",
            "commandOptions": {},
            "edited_config": {
                "name": "Nameless",
                "volumes": pod_spec['volumes'],
                "replicas": pod_spec["replicas"],
                "restartPolicy": pod_spec['restartPolicy'],
                "kube_type": pod_spec["kube_type"],
                "node": None,
                "status": 'stopped',
                "containers": pod_spec['containers'],
            }
        }
        return edit_data

    def change_kubes(self, kubes=None, kube_type=None,
                     container_name=None, container_image=None,
                     redeploy=True):
        edit_data = self.__get_edit_data()

        if not (kubes is None) ^ (kube_type is None):
            raise ValueError('You need to specify either the kube'
                             ' or kube type')

        if not (container_name is None) ^ (container_image is None):
            raise ValueError('You need to specify either the container_name'
                             ' or container image')

        if container_name is not None:
            def predicate(c):
                return c['name'] == container_name
        elif container_image is not None:
            def predicate(c):
                return c['image'] == container_image
        else:
            raise Exception('Neither container_name nor container_image '
                            'was specified')

        try:
            container = next(c for c in
                             edit_data['edited_config']['containers']
                             if predicate(c))
            container['kubes'] = kubes
        except StopIteration:
            raise PodResizeError(
                "Pod '{}' does not have container with {}".format(
                    self.name,
                    "name '{}'".format(container_name) if container_name else
                    "image '{}'".format(container_image)
                ))

        _, out, _ = self.cluster.kcli2(
            "pods update --name '{}' '{}'".format(self.name,
                                                  json.dumps(edit_data)),
            out_as_dict=True, user=self.owner)
        LOG.debug("Pod {} updated".format(out))
        if redeploy:
            self.redeploy(applyEdit=True)
        self.kubes = kubes

    def change_kubetype(self, kube_type):
        edit_data = self.__get_edit_data()
        edit_data['edited_config']['kube_type'] = kube_type
        _, out, _ = self.cluster.kcli2(
            "pods update --name '{}' '{}'".format(self.name,
                                                  json.dumps(edit_data)),
            out_as_dict=True, user=self.owner)
        LOG.debug("Pod {} updated".format(out))
        self.redeploy(applyEdit=True)
        self.kube_type = utils.kube_type_to_str(kube_type)

    def get_stat(self):
        self.cluster.kcli2(u"stats pod {}".format(self.pod_id))

    def get_container_stat(self, container):
        self.cluster.kcli2(u"stats container {} {}".format(self.pod_id,
                                                           container))

    def gen_workload(self, load_time):
        pass


class _NginxPod(KDPod):
    SRC = "nginx"

    def wait_for_ports(self, ports=None, timeout=DEFAULT_WAIT_PORTS_TIMEOUT):
        # Though nginx also has 443, it is not turned on in a clean image.
        ports = ports or self.ports
        if 443 in ports:
            ports.remove(443)
        self._wait_for_ports(ports, timeout)

    def healthcheck(self):
        if not (self.open_all_ports or self.ports):
            raise Exception(
                "Cannot perform nginx healthcheck without public IP")
        self._generic_healthcheck()
        # if shared IP is used, 404 is returned in a response to GET on
        # pod's domain name for up to 40 seconds after pod is started
        utils.retry(self.do_GET, tries=5, interval=10)
        utils.assert_in("Welcome to nginx!", self.do_GET())
