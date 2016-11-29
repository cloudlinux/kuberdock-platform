"""Functions to manage ingress resources."""
import base64
import json

from .helpers import KubeQuery


class IngressResource(object):
    def __init__(self, name):
        self.config = {
            "metadata": {
                "name": name,
            },
            "kind": "Ingress",
            "spec": {
                "tls": [],
                "rules": []
            }
        }

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

    def update(self, resource):
        response = self.kq.put(['ingresses', resource.name],
                               resource.json_config, ns=resource.namespace)
        self._process_response(response)

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

    resource = IngressResource('http')
    kq = KubeQuery(base_url='apis/extensions', api_version='v1beta1')
    data = kq.get(['ingresses', resource.name], ns=namespace)

    if data.get('code') != 404:
        return

    resource.add_http_rule(domain, service)
    if custom_domain is not None:
        resource.add_http_rule(custom_domain, service)

    kq.post(['ingresses'], resource.json_config, rest=True, ns=namespace)


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

    resource = IngressResource('https')
    kq = KubeQuery(base_url='apis/extensions', api_version='v1beta1')
    data = kq.get(['ingresses', resource.name], ns=namespace)

    if data.get('code') != 404:
        return

    resource.add_http_rule(domain, service)
    resource.add_tls('https', domain)

    if custom_domain is not None:
        resource.add_http_rule(custom_domain, service)
        resource.add_tls('https-{}'.format(custom_domain), custom_domain)

    if certificate is not None:
        save_certificate_to_secret(certificate, 'https', namespace)
    else:
        # Request delayed certificate autogeneration via kube-lego
        resource.config['metadata']['annotations'] = {
            "kubernetes.io/tls-acme": "true"
        }

    kq.post(['ingresses'], resource.json_config, rest=True, ns=namespace)


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
        "type": "Opaque"
    }
    KubeQuery().post(['secrets'], json.dumps(secret), ns=namespace, rest=True)


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


def add_custom_domain(namespace, service, containers, domain):
    """Adds a user provided domain to the existing ingress resources
    Containers param is used do determine if we should enable TLS or not
    """
    http, https = get_required_protocols(containers)
    # If there are not containers with http or https - do nothing
    if not https and not http:
        return

    client = IngressResourceClient()

    if https:
        resource = client.get(namespace, 'https')
        resource.add_tls('https-{}'.format(domain), domain)
    elif http:
        resource = client.get(namespace, 'http')

    resource.add_http_rule(domain, service)

    client.update(resource)


def remove_custom_domain(namespace, service, containers, domain):
    """Removes a user provided domain from existin ingress resource
    Containers param is used do determine if we should enable TLS or not
    """
    http, https = get_required_protocols(containers)

    client = IngressResourceClient()
    if https:
        resource = client.get(namespace, 'https')
        resource.delete_tls(domain)
    elif http:
        resource = client.get(namespace, 'http')

    resource.delete_http_rule(domain)
    client.update(resource)
