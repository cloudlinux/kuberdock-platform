import math

from flask import current_app
from sqlalchemy.exc import IntegrityError

from .network_policies import get_dns_policy_config, get_logs_policy_config
from .podcollection import PodCollection
from ..billing import kubes_to_limits
from ..billing.models import Kube
from ..core import db
from ..exceptions import APIError
from ..pods.models import Pod
from ..settings import (
    DNS_CLIENT_CRT,
    DNS_CLIENT_KEY,
    DNS_SERVICE_IP,
    ELASTICSEARCH_PUBLISH_PORT,
    ELASTICSEARCH_REST_PORT,
    ETCD_CACERT,
    ETCD_NETWORK_POLICY_SERVICE,
    MASTER_IP,
)
from ..users.models import User
from ..utils import Etcd, retry
from ..validation import check_internal_pod_data


KUBERDOCK_DNS_POD_NAME = 'kuberdock-dns'
KUBERDOCK_POLICY_POD_NAME = 'kuberdock-policy-agent'
KUBERDOCK_LOGS_MEMORY_LIMIT = 256 * 1024 * 1024


def get_kuberdock_logs_pod_name(node):
    return 'kuberdock-logs-{0}'.format(node)


def create_logs_pod(hostname, owner):
    def _create_pod():
        pod_name = get_kuberdock_logs_pod_name(hostname)
        dbpod = db.session.query(Pod).filter(Pod.name == pod_name,
                                             Pod.owner_id == owner.id).first()
        if dbpod:
            return PodCollection(owner).get(dbpod.id, as_json=False)

        try:
            logs_kubes = 1
            logcollector_kubes = logs_kubes
            logstorage_kubes = logs_kubes
            node_resources = kubes_to_limits(
                logs_kubes, Kube.get_internal_service_kube_type()
            )['resources']
            logs_memory_limit = node_resources['limits']['memory']
            if logs_memory_limit < KUBERDOCK_LOGS_MEMORY_LIMIT:
                logs_kubes = int(math.ceil(
                    float(KUBERDOCK_LOGS_MEMORY_LIMIT) / logs_memory_limit
                ))

            if logs_kubes > 1:
                # allocate total log cubes to log collector and to log
                # storage/search containers as 1 : 3
                total_kubes = logs_kubes * 2
                logcollector_kubes = int(math.ceil(float(total_kubes) / 4))
                logstorage_kubes = total_kubes - logcollector_kubes
            internal_ku_token = owner.get_token()

            logs_config = get_kuberdock_logs_config(
                hostname, pod_name,
                Kube.get_internal_service_kube_type(),
                logcollector_kubes,
                logstorage_kubes,
                MASTER_IP,
                internal_ku_token
            )
            check_internal_pod_data(logs_config, owner)
            logs_pod = PodCollection(owner).add(logs_config, skip_check=True)
            pod_id = logs_pod['id']
            PodCollection(owner).update(
                pod_id, {'command': 'synchronous_start'}
            )
            logs_policy = get_logs_policy_config(
                owner.id, pod_id, pod_name)
            Etcd(ETCD_NETWORK_POLICY_SERVICE).put(
                pod_name, value=logs_policy)
            return PodCollection(owner).get(pod_id, as_json=False)

        except (IntegrityError, APIError):
            # Either pod already exists or an error occurred during it's
            # creation - log and retry
            current_app.logger.exception(
                'During "{}" node creation tried to create a Logs service '
                'pod but got an error.'.format(hostname))

    return retry(_create_pod, 1, 5, exc=APIError('Could not create Log '
                                                 'service POD'))


def create_dns_pod(hostname, owner):
    def _create_pod():
        if db.session.query(Pod) \
                .filter_by(name=KUBERDOCK_DNS_POD_NAME, owner=owner).first():
            return True

        try:
            dns_config = get_dns_pod_config()
            check_internal_pod_data(dns_config, owner)
            dns_pod = PodCollection(owner).add(dns_config, skip_check=True)
            PodCollection(owner).update(dns_pod['id'],
                                        {'command': 'synchronous_start'})
            dns_policy = get_dns_policy_config(owner.id, dns_pod['id'])
            Etcd(ETCD_NETWORK_POLICY_SERVICE).put(
                KUBERDOCK_DNS_POD_NAME, value=dns_policy
            )
            return True
        except (IntegrityError, APIError):
            # Either pod already exists or an error occurred during it's
            # creation - log and retry
            current_app.logger.exception(
                'During "{}" node creation tried to create a DNS service '
                'pod but got an error.'.format(hostname))

    return retry(_create_pod, 1, 5, exc=APIError('Could not create DNS '
                                                 'service POD'))


def create_policy_pod(hostname, owner, token):
    def _create_pod():
        if db.session.query(Pod).filter_by(
                name=KUBERDOCK_POLICY_POD_NAME, owner=owner).first():
            return True

        try:
            policy_conf = get_policy_agent_config(MASTER_IP, token)
            check_internal_pod_data(policy_conf, owner)
            policy_pod = PodCollection(owner).add(policy_conf, skip_check=True)
            PodCollection(owner).update(policy_pod['id'],
                                        {'command': 'synchronous_start'})
            return True
        except (IntegrityError, APIError):
            # Either pod already exists or an error occurred during it's
            # creation - log and retry
            current_app.logger.exception(
                'During "{}" node creation tried to create a Network Policy '
                'service pod but got an error.'.format(hostname))

    return retry(_create_pod, 1, 5, exc=APIError('Could not create Network '
                                                 'Policy service POD'))


def delete_logs_pod(hostname):
    ku = User.get_internal()

    logs_pod_name = get_kuberdock_logs_pod_name(hostname)
    logs_pod = db.session.query(Pod).filter_by(name=logs_pod_name,
                                               owner=ku).first()
    if logs_pod:
        PodCollection(ku).delete(logs_pod.id, force=True)


def get_kuberdock_logs_config(node, name, kube_type,
                              collector_kubes, storage_kubes, master_ip,
                              internal_ku_token):
    # Give 2/3 of elastic kubes limits to elastic heap. It's recommended do not
    # give all memory to the heap, and leave some to Lucene.
    es_memory_limit = kubes_to_limits(
        storage_kubes, kube_type
    )['resources']['limits']['memory']
    es_heap_limit = (es_memory_limit * 2) / 3
    return {
        "name": name,
        "replicas": 1,
        "kube_type": kube_type,
        "node": node,
        "restartPolicy": "Always",
        "volumes": [
            {
                "name": "docker-containers",
                # path is allowed only for kuberdock-internal
                "localStorage": {"path": "/var/lib/docker/containers"}
            },
            {
                "name": "es-persistent-storage",
                # path is allowed only for kuberdock-internal
                "localStorage": {"path": "/var/lib/elasticsearch"},
            }
        ],
        "containers": [
            {
                "command": ["./run.sh"],
                "kubes": collector_kubes,
                "image": "kuberdock/fluentd:1.8",
                "name": "fluentd",
                "env": [
                    {
                        "name": "NODENAME",
                        "value": node
                    },
                    {
                        "name": "ES_HOST",
                        "value": "127.0.0.1"
                    }
                ],
                "ports": [
                    {
                        "isPublic": False,
                        "protocol": "UDP",
                        "containerPort": 5140,
                        "hostPort": 5140
                    }
                ],
                "volumeMounts": [
                    {
                        "name": "docker-containers",
                        "mountPath": "/var/lib/docker/containers"
                    }
                ],
                "workingDir": "/root",
                "terminationMessagePath": None
            },
            {
                "kubes": storage_kubes,
                "image": "kuberdock/elasticsearch:2.2",
                "name": "elasticsearch",
                "env": [
                    {
                        "name": "MASTER",
                        "value": master_ip
                    },
                    {
                        "name": "TOKEN",
                        "value": internal_ku_token
                    },
                    {
                        "name": "NODENAME",
                        "value": node
                    },
                    {
                        "name": "ES_HEAP_SIZE",
                        "value": "{}m".format(es_heap_limit / (1024 * 1024))
                    }
                ],
                "ports": [
                    {
                        "isPublic": False,
                        "protocol": "TCP",
                        "containerPort": ELASTICSEARCH_REST_PORT,
                        "hostPort": ELASTICSEARCH_REST_PORT
                    },
                    {
                        "isPublic": False,
                        "protocol": "TCP",
                        "containerPort": ELASTICSEARCH_PUBLISH_PORT,
                        "hostPort": ELASTICSEARCH_PUBLISH_PORT
                    }
                ],
                "volumeMounts": [
                    {
                        "name": "es-persistent-storage",
                        "mountPath": "/elasticsearch/data"
                    }
                ],
                "workingDir": "",
                "terminationMessagePath": None
            }
        ]
    }


def get_dns_pod_config(domain='kuberdock', ip=DNS_SERVICE_IP):
    """Returns config of k8s DNS service pod."""
    # Based on
    # https://github.com/kubernetes/kubernetes/blob/release-1.2/
    #   cluster/addons/dns/skydns-rc.yaml.in
    # TODO AC-3377: migrate on yaml-based templates
    # TODO AC-3378: integrate exechealthz container
    return {
        "name": KUBERDOCK_DNS_POD_NAME,
        "podIP": ip,
        "replicas": 1,
        "kube_type": Kube.get_internal_service_kube_type(),
        "node": None,
        "restartPolicy": "Always",
        "dnsPolicy": "Default",
        "volumes": [
            {
                "name": "kubernetes-config",
                # path is allowed only for kuberdock-internal
                "localStorage": {"path": "/etc/kubernetes"}
            },
            {
                "name": "etcd-pki",
                # path is allowed only for kuberdock-internal
                "localStorage": {"path": "/etc/pki/etcd"}
            }
        ],
        "containers": [
            {
                "name": "etcd",
                "command": [
                    "/usr/local/bin/etcd",
                    "-data-dir",
                    "/var/etcd/data",
                    "-listen-client-urls",
                    "https://0.0.0.0:2379,http://127.0.0.1:4001",
                    "-advertise-client-urls",
                    "https://0.0.0.0:2379,http://127.0.0.1:4001",
                    "-initial-cluster-token",
                    "skydns-etcd",
                    "--ca-file",
                    ETCD_CACERT,
                    "--cert-file",
                    "/etc/pki/etcd/etcd-dns.crt",
                    "--key-file",
                    "/etc/pki/etcd/etcd-dns.key"
                ],
                "kubes": 1,
                "image": "gcr.io/google_containers/etcd-amd64:2.2.1",
                "env": [],
                "ports": [
                    {
                        "isPublic": False,
                        "protocol": "TCP",
                        "containerPort": 2379
                    }
                ],
                "volumeMounts": [
                    {
                        "name": "etcd-pki",
                        "mountPath": "/etc/pki/etcd"
                    }
                ],
                "workingDir": "",
                "terminationMessagePath": None
            },
            {
                "name": "kube2sky",
                "args": [
                    "--domain={0}".format(domain),
                    "--kubecfg-file=/etc/kubernetes/configfile",
                    "--kube-master-url=https://10.254.0.1",
                ],
                "kubes": 1,
                "image": "kuberdock/kube2sky:1.2",
                "env": [],
                "ports": [],
                "volumeMounts": [
                    {
                        "name": "kubernetes-config",
                        "mountPath": "/etc/kubernetes"
                    }
                ],
                "workingDir": "",
                "terminationMessagePath": None,
                "readinessProbe": {
                    "httpGet": {
                        "path": "/readiness",
                        "port": 8081,
                        "scheme": "HTTP",
                    },
                    "initialDelaySeconds": 30,
                    "timeoutSeconds": 5
                },
                "livenessProbe": {
                    "httpGet": {
                        "path": "/healthz",
                        "port": 8080,
                        "scheme": "HTTP"
                    },
                    "initialDelaySeconds": 60,
                    "timeoutSeconds": 5,
                    "successThreshold": 1,
                    "failureThreshold": 5,
                }
            },
            {
                "name": "skydns",
                "args": [
                    "-machines=http://127.0.0.1:4001",
                    "-addr=0.0.0.0:53",
                    "-ns-rotate=false",
                    "-domain={0}.".format(domain)
                ],
                "kubes": 1,
                "image": "gcr.io/google_containers/skydns:2015-10-13-8c72f8c",
                "env": [],
                "ports": [
                    {
                        "isPublic": False,
                        "protocol": "UDP",
                        "containerPort": 53
                    },
                    {
                        "isPublic": False,
                        "protocol": "TCP",
                        "containerPort": 53
                    }
                ],
                "volumeMounts": [],
                "workingDir": "",
                "terminationMessagePath": None
            },
            {
                "name": "healthz",
                "image": "gcr.io/google_containers/exechealthz:1.0",
                "args": [
                    "-cmd=nslookup {0} 127.0.0.1 >/dev/null".format(domain),
                    "-port=8080"
                ],
                "ports": [{
                    "protocol": "TCP",
                    "containerPort": 8080
                }]
            }
        ]
    }


def get_policy_agent_config(master, token):
    return {
        "name": "kuberdock-policy-agent",
        "replicas": 1,
        "kube_type": Kube.get_internal_service_kube_type(),
        "node": None,
        "restartPolicy": "Always",
        "hostNetwork": True,
        "volumes": [
            {
                "name": "etcd-pki",
                # path is allowed only for kuberdock-internal
                "localStorage": {"path": "/etc/pki/etcd"}
            }
        ],
        "containers": [
            {
                "command": [],
                "kubes": 1,
                "image": "kuberdock/k8s-policy-agent:v0.1.4-kd2",
                "name": "policy-agent",
                "env": [
                    {
                        "name": "ETCD_AUTHORITY",
                        "value": "{0}:2379".format(master)
                    },
                    {
                        "name": "ETCD_SCHEME",
                        "value": "https"
                    },
                    {
                        "name": "ETCD_CA_CERT_FILE",
                        "value": ETCD_CACERT
                    },
                    {
                        "name": "ETCD_CERT_FILE",
                        "value": DNS_CLIENT_CRT
                    },
                    {
                        "name": "ETCD_KEY_FILE",
                        "value": DNS_CLIENT_KEY
                    },
                    {
                        "name": "K8S_API",
                        "value": "https://{0}:6443".format(master)
                    },
                    {
                        "name": "K8S_AUTH_TOKEN",
                        "value": token
                    }
                ],
                "ports": [],
                "volumeMounts": [
                    {
                        "name": "etcd-pki",
                        "mountPath": "/etc/pki/etcd"
                    }
                ],
                "workingDir": "",
                "terminationMessagePath": None
            },
        ]
    }
