"""Functions to manage ingress resources."""
import base64
import json

from ..domains.models import PodDomain
from .helpers import KubeQuery


class IngressResource(object):
    def __init__(self, name, namespace=None):
        self.config = {
            'metadata': {
                'name': name,
                'annotations': {}
            },
            'kind': 'Ingress',
            'spec': {
                'tls': [],
                'rules': []
            }
        }

        if namespace is not None:
            self.config['metadata']['namespace'] = namespace

    def add_tls(self, secret_name, *domains):
        self.tls.append({
            'hosts': domains,
            'secretName': secret_name
        })

    def add_http_rule(self, domain, service):
        self.rules.append({
            "host": domain,
            "http": {
                "paths": [
                    {
                        "path": "/",
                        "backend": {"serviceName": service, "servicePort": 80}
                    }
                ]
            }
        })

    def delete_http_rule(self, domain):
        for i, rule in enumerate(self.rules):
            if rule['host'] == domain:
                self.rules.pop(i)
                return

    def delete_tls(self, domain):
        matching_tls = ((i, l) for i, l in enumerate(self.tls)
                        if domain in l['hosts'])

        for index, t in matching_tls:
            # If it is the last domain - drop the whole TLS element
            if len(t['hosts']) == 1:
                self.tls.pop(index)
            else:
                t['hosts'].remove(domain)

    def disable_ssl_autogeneration(self):
        self.config['metadata']['annotations'].pop(
            'kubernetes.io/tls-acme', None)

    def enable_ssl_autogeneration(self):
        self.config['metadata']['annotations']['kubernetes.io/tls-acme'] = 'true'

    @classmethod
    def from_config(cls, config):
        obj = cls(config['metadata']['name'])
        obj.config = config
        return obj

    @property
    def rules(self):
        return self.config['spec']['rules']

    @property
    def namespace(self):
        return self.config['metadata'].get('namespace', None)

    @property
    def tls(self):
        return self.config['spec']['tls']

    @property
    def ssl_secret_name(self):
        return 'https-{}'.format(self.name)

    @property
    def name(self):
        return self.config['metadata'].get('name', None)

    @property
    def json_config(self):
        return json.dumps(self.config)


class UnexpectedResponse(Exception):
    pass


class IngressResourceNotFound(KeyError):
    pass


class IngressResourceAlreadyExists(Exception):
    pass


class K8sApiError(Exception):
    pass


class IngressResourceClient(object):
    def __init__(self):
        self.kq = KubeQuery(base_url='apis/extensions', api_version='v1beta1')

    def remove(self, resource):
        response = self.kq.delete(['ingresses', resource.name], ns=resource.namespace)
        self._process_response(response)

    def remove_by_name(self, namespace, name=None):
        res = ['ingresses'] if name is None else ['ingresses', name]
        response = self.kq.delete(res, ns=namespace)
        self._process_response(response)

    def get(self, namespace, name=None):
        if name is None:
            response = self.kq.get(['ingresses'], ns=namespace)
            self._process_response(response)
            return [IngressResource.from_config(i) for i in response['items']]

        response = self.kq.get(['ingresses', name], ns=namespace)
        self._process_response(response)
        return IngressResource.from_config(response)

    def create(self, resource):
        r = self.kq.post(['ingresses'], resource.json_config, rest=True,
                         ns=resource.namespace)
        self._process_response(r)

    def update(self, resource):
        response = self.kq.put(['ingresses', resource.name],
                               resource.json_config, ns=resource.namespace)
        self._process_response(response)

    def update_or_create(self, resource):
        try:
            r = self.kq.post(['ingresses'], resource.json_config, rest=True,
                             ns=resource.namespace)
            self._process_response(r)
        except IngressResourceAlreadyExists:
            self.update(resource)

    @classmethod
    def _process_response(cls, resp):
        if resp['kind'] != 'Status':
            return resp

        if resp['kind'] == 'Status' and resp['status'] == 'Failure':
            if resp['code'] == 404:
                raise IngressResourceNotFound()
            elif resp['code'] == 409:
                raise IngressResourceAlreadyExists()
            raise K8sApiError(resp)


def create_ingress_http(namespace, service, domain, custom_domain=None):
    """
    Create Ingress resource for HTTP only

    :param namespace: Pod Namespace
    :type namespace: str
    :param domain: Pod Domain Name
    :type domain: str
    :param service: Pod Service Name
    :type service: str
    """

    resource = IngressResource('http', namespace)
    client = IngressResourceClient()

    try:
        client.get(resource.namespace, resource.name)
        return
    except IngressResourceNotFound:
        pass

    resource.add_http_rule(domain, service)
    if custom_domain is not None:
        c_resource = IngressResource('http-{}'.format(domain), namespace)
        c_resource.add_http_rule(custom_domain, service)
        client.create(c_resource)

    client.create(resource)


def create_ingress_https(namespace, service, domain, custom_domain=None,
                         certificate=None):
    """
    Create Ingress resource for HTTPS and HTTP

    :param namespace: Pod Namespace
    :type namespace: str
    :param domain: Pod Domain Name
    :type domain: str
    :param service: Pod Service Name
    :type service: str
    """

    client = IngressResourceClient()
    resource = IngressResource('https', namespace)

    try:
        client.get(resource.namespace, resource.name)
        return
    except IngressResourceNotFound:
        pass

    pod_domain = PodDomain.find_by_full_domain(domain)
    if pod_domain is None:
        raise Exception('{} domain is not present in a db'.format(domain))

    wildcard_cert = pod_domain.base_domain.certificate

    if custom_domain is not None:
        custom_r = IngressResource('https-{}'.format(custom_domain), namespace)
        custom_r.add_http_rule(custom_domain, service)
        custom_r.add_tls(custom_r.name, custom_domain)

        if certificate is not None:
            save_certificate_to_secret(certificate, custom_r.name, namespace)
        else:
            custom_r.enable_ssl_autogeneration()

        client.create(custom_r)

    resource.add_http_rule(domain, service)
    resource.add_tls('https', domain)
    resource.enable_ssl_autogeneration()
    # Wildcard certificate is used in all cases except there is user provided
    # certificate and there is no custom_domain specified
    if certificate is not None and custom_domain is None:
        save_certificate_to_secret(certificate, resource.name, namespace)
        resource.disable_ssl_autogeneration()
    elif wildcard_cert:
        save_certificate_to_secret(wildcard_cert, resource.name, namespace)
        resource.disable_ssl_autogeneration()

    client.create(resource)


def save_certificate_to_secret(certificate, secret_name, namespace):
    secret = {
        "kind": "Secret",
        "apiVersion": "v1",
        "metadata": {
            "name": secret_name,
        },
        "data": {
            "tls.crt": base64.encodestring(certificate['cert']),
            "tls.key": base64.encodestring(certificate['key']),
        },
        "type": "kubernetes.io/tls"
    }

    kq = KubeQuery()
    r = kq.post(['secrets'], json.dumps(secret), ns=namespace, rest=True)

    if r.get('code') == 409:
        kq.put(['secrets', secret_name], json.dumps(secret), ns=namespace, rest=True)


def create_ingress(containers, namespace, service, domain, custom_domain=None,
                   certificate=None):
    """
    Create Ingress resource based on containers ports

    :param containers: Pod Containers
    :type containers: list
    :param namespace: Pod Namespace
    :type namespace: str
    :param domain: Pod Domain Name
    :type domain: str
    :param service: Pod Service Name
    :type service: str
    """

    http, https = get_required_protocols(containers)

    if https:
        create_ingress_https(namespace, service, domain, custom_domain,
                             certificate)
    elif http:
        create_ingress_http(namespace, service, domain, custom_domain)
    else:
        return False, '80/tcp or 443/tcp Pod port needed to use IP Sharing'

    return True, None


def get_required_protocols(containers):
    http = https = False
    for container in containers:
        for port in container['ports']:
            port_number = port.get('hostPort') or port['containerPort']
            port_proto = port.get('protocol', 'tcp').lower()
            port_is_public = port.get('isPublic', False)
            if port_proto == 'tcp' and port_is_public:
                http = port_number == 80 or http
                https = port_number == 443 or https
    return http, https


def add_custom_domain(namespace, service, containers, domain, certificate=None):
    """Adds a user provided domain to the existing ingress resources
    Containers param is used do determine if we should enable TLS or not
    """
    http, https = get_required_protocols(containers)
    # If there are not containers with http or https - do nothing
    if not https and not http:
        return

    client = IngressResourceClient()

    if https:
        resource = IngressResource('https-{}'.format(domain), namespace)
        resource.add_tls(resource.name, domain)

        if certificate is not None:
            resource.disable_ssl_autogeneration()
            save_certificate_to_secret(certificate, resource.name, resource.namespace)
        else:
            resource.enable_ssl_autogeneration()
    else:
        resource = IngressResource('http-{}'.format(domain), namespace)

    resource.add_http_rule(domain, service)
    client.update_or_create(resource)

def remove_custom_domain(namespace, service, containers, domain):
    """Removes a user provided domain from existin ingress resource
    Containers param is used do determine if we should enable TLS or not
    """
    http, https = get_required_protocols(containers)

    if https:
        name = 'https-{}'.format(domain)
    elif http:
        name = 'http-{}'.format(domain)

    client = IngressResourceClient()
    client.remove_by_name(namespace, name)
