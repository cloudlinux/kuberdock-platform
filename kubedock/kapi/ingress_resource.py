"""Functions to manage ingress resources."""
import json

from .helpers import KubeQuery


def create_ingress_http(namespace, domain, service):
    """
    Create Ingress resource for HTTP only

    :param namespace: Pod Namespace
    :type namespace: str
    :param domain: Pod Domain Name
    :type domain: str
    :param service: Pod Service Name
    :type service: str
    """

    name = 'http'
    kq = KubeQuery(base_url='apis/extensions', api_version='v1beta1')
    data = kq.get(['ingresses', name], ns=namespace)

    if data.get('code') != 404:
        return

    config = {
        "metadata": {
            "name": name
        },
        "kind": "Ingress",
        "spec": {
            "rules": [
                {
                    "host": domain,
                    "http": {
                        "paths": [
                            {
                                "path": "/",
                                "backend": {
                                    "serviceName": service,
                                    "servicePort": 80
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }

    kq.post(['ingresses'], json.dumps(config), rest=True, ns=namespace)


def create_ingress_https(namespace, domain, service):
    """
    Create Ingress resource for HTTPS and HTTP

    :param namespace: Pod Namespace
    :type namespace: str
    :param domain: Pod Domain Name
    :type domain: str
    :param service: Pod Service Name
    :type service: str
    """

    name = 'https'
    kq = KubeQuery(base_url='apis/extensions', api_version='v1beta1')
    data = kq.get(['ingresses', name], ns=namespace)

    if data.get('code') != 404:
        return

    config = {
        "metadata": {
            "name": name,
            "annotations": {
                "kubernetes.io/tls-acme": "true"
            }
        },
        "kind": "Ingress",
        "spec": {
            "tls": [
                {
                    "hosts": [
                        domain
                    ],
                    "secretName": name
                }
            ],
            "rules": [
                {
                    "host": domain,
                    "http": {
                        "paths": [
                            {
                                "path": "/",
                                "backend": {
                                    "serviceName": service,
                                    "servicePort": 80
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }

    kq.post(['ingresses'], json.dumps(config), rest=True, ns=namespace)


def create_ingress(containers, namespace, domain, service):
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

    http = https = False
    for container in containers:
        for port in container['ports']:
            port_number = port.get('hostPort') or port['containerPort']
            port_proto = port.get('protocol', 'tcp').lower()
            port_is_public = port.get('isPublic', False)
            if port_proto == 'tcp' and port_is_public:
                http = port_number == 80 or http
                https = port_number == 443 or https
    if https:
        create_ingress_https(namespace, domain, service)
    elif http:
        create_ingress_http(namespace, domain, service)
    else:
        return False, '80/tcp or 443/tcp Pod port needed to use IP Sharing'
    return True, None
