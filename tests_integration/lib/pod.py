import itertools
import json
import logging
import pipes
import sys
import time
import urllib2

from collections import namedtuple

from tests_integration.lib.exceptions import StatusWaitException, \
    UnexpectedKubectlResponse, PodIsNotRunning, \
    IncorrectPodDescription, CannotRestorePodWithMoreThanOneContainer
from tests_integration.lib.utils import \
    assert_eq, assert_in, kube_type_to_int, wait_net_port, \
    retry, kube_type_to_str, get_rnd_low_string, all_subclasses

DEFAULT_WAIT_PORTS_TIMEOUT = 5 * 60


logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger("paramiko").setLevel(logging.WARNING)
LOG = logging.getLogger(__name__)


class RESTMixin(object):
    # Expectations:
    # self.public_ip

    def do_GET(self, scheme="http", path='/', port=None, timeout=5):
        if port:
            url = '{0}://{1}:{2}{3}'.format(scheme, self.public_ip, port, path)
        else:
            url = '{0}://{1}{2}'.format(scheme, self.public_ip, path)
        LOG.debug("Issuing GET to {0}".format(url))
        req = urllib2.urlopen(url, timeout=timeout)
        res = unicode(req.read(), 'utf-8')
        LOG.debug(u"Response:\n{0}".format(res))
        return res

    def do_POST(self, path='/', headers=None, body=""):
        pass

    def wait_http_resp(self, scheme="http", path='/', port=None, code=200,
                       timeout=3, tries=60, internal=3):
        if port:
            url = '{0}://{1}:{2}{3}'.format(scheme, self.public_ip, port, path)
        else:
            url = '{0}://{1}{2}'.format(scheme, self.public_ip, path)
        LOG.debug('Expecting for response code {code} on url {url}, '
                  'total retries: {tries}'.format(
                      code=code, url=url, tries=tries))

        def check(*args, **kwargs):
            req = urllib2.urlopen(url, timeout=timeout)
            assert req.code == code

        retry(check, tries=tries, internal=internal)


class KDPod(RESTMixin):
    # Image or PA name
    SRC = None
    WAIT_PORTS_TIMEOUT = DEFAULT_WAIT_PORTS_TIMEOUT
    Port = namedtuple('Port', 'port proto')

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
               restart_policy, pvs, owner, password, ports_to_open):
        """
        Create new pod in kuberdock
        :param open_all_ports: if true, open all ports of image (does not mean
        these are Public IP ports, depends on a cluster setup)
        :param ports_to_open: if open_all_ports is False, open only the ports
        from this list
        :return: object via which Kuberdock pod can be managed
        """

        def _get_image_ports(img):
            _, out, _ = cluster.kcli(
                'image_info {}'.format(img), out_as_dict=True, user=owner)

            return [
                cls.Port(int(port['number']), port['protocol'])
                for port in out['ports']]

        def _ports_to_dict(ports):
            """
            :return: list of dictionaries with ports, necessary for
            creation of general pod via kcli2
            """
            ports_list = []
            for port in ports:
                ports_list.append(dict(containerPort=port.port,
                                       hostPort=port.port,
                                       isPublic=(open_all_ports or
                                                 port.port in ports_to_open),
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
                         name=get_rnd_low_string(length=11))
        ports = retry(_get_image_ports, img=image)
        container.update(ports=_ports_to_dict(ports))
        if pvs is not None:
            container.update(volumeMounts=[pv.volume_mount_dict for pv in pvs])
            pod_spec.update(volumes=[pv.volume_dict for pv in pvs])
        pod_spec.update(containers=[container])
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
                raise CannotRestorePodWithMoreThanOneContainer(
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
            raise IncorrectPodDescription(
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
            raise IncorrectPodDescription(
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
        kube_type = kube_type_to_str(data['kube_type'])
        restart_policy = data['restartPolicy']
        this_pod_class = cls._get_pod_class(image)
        return this_pod_class(cluster, "", name, kube_type, "", True,
                              restart_policy, "", owner)

    @classmethod
    def _get_pod_class(cls, image):
        pod_classes = {c.SRC: c for c in all_subclasses(cls)}
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
        # Currently all ports can be open by setting open_all_ports, or some
        # ports can be open by setting ports_to_open while creating a pod
        timeout = timeout or self.WAIT_PORTS_TIMEOUT
        if not (self.open_all_ports or self.ports):
            raise Exception("Cannot wait for ports on a pod with no"
                            " ports open")
        ports = ports or self.ports
        self._wait_for_ports(ports, timeout)

    def _wait_for_ports(self, ports, timeout):
        for p in ports:
            wait_net_port(self.public_ip, p, timeout)

    def wait_for_status(self, status, tries=50, interval=5, delay=0):
        """
        Wait till POD's status changes to the given one

        :param status: the desired status to wait for
        :param tries: number of tries to check the status for
        :param interval: delay between the tries in seconds
        :param delay: the initial delay before a first check
        :return:
        """
        time.sleep(delay)
        for _ in range(tries):
            if self.status == status:
                return
            time.sleep(interval)
        raise StatusWaitException()

    @property
    def info(self):
        try:
            _, out, _ = self.cluster.kubectl(
                u'get pod {}'.format(self.escaped_name), out_as_dict=True,
                user=self.owner)
            return out[0]
        except KeyError:
            raise UnexpectedKubectlResponse()

    @property
    def status(self):
        return self.info['status']

    @property
    def escaped_name(self):
        return pipes.quote(self.name)

    @property
    def ssh_credentials(self):
        return retry(self._get_creds, tries=10, interval=1)

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

        return container['containerID']

    def get_spec(self):
        _, out, _ = self.cluster.kubectl(
            u"describe pods {}".format(self.escaped_name), out_as_dict=True,
            user=self.owner)
        return out

    def get_dump(self):
        cmd = u"pods dump {pod_id}".format(pod_id=self.pod_id)
        _, out, _ = self.cluster.kdctl(cmd, out_as_dict=True)
        rv = out['data']
        return rv

    @property
    def pod_id(self):
        return self.get_spec()['id']

    def docker_exec(self, container_id, command, detached=False):
        if self.status != 'running':
            raise PodIsNotRunning()

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
        assert_eq(spec['kube_type'], kube_type_to_int(self.kube_type))
        for container in spec['containers']:
            assert_eq(container['kubes'], self.kubes)
        assert_eq(spec['restartPolicy'], self.restart_policy)
        assert_eq(spec['status'], "running")
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
                     container_name=None, container_image=None):
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

        try:
            container = next(c for c in
                             edit_data['edited_config']['containers']
                             if predicate(c))
            container['kubes'] = kubes
        except StopIteration:
            LOG.error("Pod {} does not have {} container".format(
                self.name, container_name))

        _, out, _ = self.cluster.kcli2(
            "pods update --name '{}' '{}'".format(self.name,
                                                  json.dumps(edit_data)),
            out_as_dict=True, user=self.owner)
        LOG.debug("Pod {} updated".format(out))
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
        self.kube_type = kube_type_to_str(kube_type)


class _NginxPod(KDPod):
    SRC = "nginx"

    def wait_for_ports(self, ports=None, timeout=DEFAULT_WAIT_PORTS_TIMEOUT):
        # Though nginx also has 443, it is not turned on in a clean image.
        ports = ports or [80]
        self._wait_for_ports(ports, timeout)

    def healthcheck(self):
        if not (self.open_all_ports or self.ports):
            raise Exception(
                "Cannot perform nginx healthcheck without public IP")
        self._generic_healthcheck()
        assert_in("Welcome to nginx!", self.do_GET())
