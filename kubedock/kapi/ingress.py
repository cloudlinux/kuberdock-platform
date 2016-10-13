from flask import current_app
from sqlalchemy.exc import IntegrityError

from .podcollection import PodCollection
from ..billing.models import Kube
from ..constants import (
    KUBERDOCK_BACKEND_POD_NAME,
    KUBERDOCK_INGRESS_POD_NAME,
)
from ..exceptions import APIError
from ..pods.models import Pod, IPPool
from ..settings import IS_PRODUCTION_PKG
from ..system_settings import keys
from ..system_settings.models import SystemSettings
from ..validation import check_internal_pod_data
from ..users.models import User
from ..utils import retry


def create_default_backend_pod():
    """
    Create Default Backend pod that serving 404 response for Ingress Controller
    """
    owner = User.get_internal()

    def _create_pod():
        if Pod.query.filter_by(name=KUBERDOCK_BACKEND_POD_NAME,
                               owner=owner).first():
            return True
        try:
            backend_config = get_default_backend_config()
            check_internal_pod_data(backend_config, owner)
            backend_pod = PodCollection(owner).add(backend_config,
                                                   skip_check=True)
            PodCollection(owner).update(
                backend_pod['id'], {'command': 'start'})
            return True
        except (IntegrityError, APIError):
            # Either pod already exists or an error occurred during it's
            # creation - log and retry
            current_app.logger.exception(
                'Tried to create a Default HTTP Backend service '
                'pod but got an error.'
            )

    return retry(_create_pod, 1, 5, exc=APIError('Could not create Default '
                                                 'HTTP Backend service POD'))


def create_ingress_controller_pod():
    """Create Ingress Controller pod"""
    owner = User.get_internal()

    # Check if pod is already exists and if not - check free public ip for it
    if Pod.query.filter_by(name=KUBERDOCK_INGRESS_POD_NAME,
                           owner=owner).first():
        return

    if not current_app.config['AWS']:
        # Raises exception if there are no free IPs. Not needed in AWS case
        IPPool.get_free_host()

    def _create_pod():
        try:
            default_backend_pod = Pod.query.filter_by(
                name=KUBERDOCK_BACKEND_POD_NAME,
                owner=owner).first()

            if not default_backend_pod:
                raise APIError('No Default HTTP Backend Pod can be found')

            default_backend_pod_config = default_backend_pod.get_dbconfig()

            backend_ns = default_backend_pod_config['namespace']
            backend_svc = default_backend_pod_config.get('service', None)

            if backend_svc is None:
                return False

            email = SystemSettings.get_by_name(
                keys.EXTERNAL_SYSTEMS_AUTH_EMAIL)
            ingress_config = get_ingress_pod_config(backend_ns, backend_svc,
                                                    email)
            check_internal_pod_data(ingress_config, owner)
            ingress_pod = PodCollection(owner).add(ingress_config,
                                                   skip_check=True)
            PodCollection(owner).update(
                ingress_pod['id'], {'command': 'start'})
            return True
        except (IntegrityError, APIError):
            # Either pod already exists or an error occurred during it's
            # creation - log and retry
            current_app.logger.exception(
                'Tried to create an Ingress Controller service '
                'pod but got an error.'
            )

    return retry(_create_pod, 10, 5, exc=APIError('Could not create Ingress '
                                                  'Controller service POD'))


def get_default_backend_config():
    """Return config of k8s default http backend pod."""
    # Based on
    # https://github.com/jetstack/kube-lego/blob/0.0.4/examples/
    #   default-http-backend-deployment.yaml
    return {
        "name": KUBERDOCK_BACKEND_POD_NAME,
        "replicas": 1,
        "kube_type": Kube.get_internal_service_kube_type(),
        "node": None,
        "restartPolicy": "Always",
        "volumes": [],
        "containers": [
            {
                "name": "default-http-backend",
                "command": [],
                "kubes": 2,
                "image": "gcr.io/google_containers/defaultbackend:1.0",
                "env": [],
                "ports": [
                    {
                        "protocol": "TCP",
                        "containerPort": 8080
                    }
                ],
                "volumeMounts": [],
                "workingDir": "",
                "terminationMessagePath": None
            }
        ]
    }


def get_ingress_pod_config(backend_ns, backend_svc, email, ip='10.254.0.100'):
    """Return config of k8s ingress controller pod."""
    # Based on
    # https://github.com/jetstack/kube-lego/blob/0.0.4/examples/
    #   nginx-deployment.yaml
    # and
    # https://github.com/jetstack/kube-lego/blob/0.0.4/examples/
    #   kube-lego-deployment.yaml
    config = {
        "name": KUBERDOCK_INGRESS_POD_NAME,
        "podIP": ip,
        "replicas": 1,
        "kube_type": Kube.get_internal_service_kube_type(),
        "node": None,
        "restartPolicy": "Always",
        "volumes": [],
        "containers": [
            {
                "name": "nginx-ingress",
                "command": [
                    "/nginx-ingress-controller",
                    "--default-backend-service={0}/{1}".format(
                        backend_ns, backend_svc
                    )
                ],
                "kubes": 5,
                "image": "gcr.io/google_containers/"
                         "nginx-ingress-controller:0.8.1",
                "env": [
                    {
                        "name": "POD_NAME",
                        "valueFrom": {
                            "fieldRef": {
                                "fieldPath": "metadata.name"
                            }
                        }
                    },
                    {
                        "name": "POD_NAMESPACE",
                        "valueFrom": {
                            "fieldRef": {
                                "fieldPath": "metadata.namespace"
                            }
                        }
                    }
                ],
                "ports": [
                    {
                        "isPublic": True,
                        "protocol": "TCP",
                        "containerPort": 80
                    },
                    {
                        "isPublic": True,
                        "protocol": "TCP",
                        "containerPort": 443
                    }
                ],
                "volumeMounts": [],
                "workingDir": "",
                "terminationMessagePath": None
            },
            {
                "name": "kube-lego",
                "command": [],
                "kubes": 3,
                "image": "jetstack/kube-lego:0.0.4",
                "env": [
                    {
                        "name": "LEGO_EMAIL",
                        "value": email
                    },
                    {
                        "name": "LEGO_NAMESPACE",
                        "valueFrom": {
                            "fieldRef": {
                                "fieldPath": "metadata.namespace"
                            }
                        }
                    },
                    {
                        "name": "LEGO_SERVICE_NAME",
                        "value": "$(KUBERDOCK_SERVICE)"
                    },
                    {
                        "name": "LEGO_PORT",
                        "value": "8081"
                    }
                ],
                "ports": [
                    {
                        "protocol": "TCP",
                        "containerPort": 8081
                    }
                ],
                "volumeMounts": [],
                "workingDir": "",
                "terminationMessagePath": None
            }
        ],
        "serviceAccount": True,
    }

    if IS_PRODUCTION_PKG:
        config['containers'][1]['env'].append(
            {
                "name": "LEGO_URL",
                "value": "https://acme-v01.api.letsencrypt.org/directory"
            }
        )

    return config


def check_cluster_email():
    """Check if cluster email is not empty"""
    if SystemSettings.get_by_name(keys.EXTERNAL_SYSTEMS_AUTH_EMAIL):
        return
    raise APIError('Email for external services is empty')


def prepare_ip_sharing():
    """Create all pods for IP Sharing"""
    check_cluster_email()
    create_default_backend_pod()
    create_ingress_controller_pod()
