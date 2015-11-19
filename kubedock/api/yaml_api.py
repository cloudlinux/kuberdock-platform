import yaml
from flask import Blueprint
from flask.views import MethodView
from kubedock.decorators import (login_required_or_basic_or_token,
                                 maintenance_protected)
from kubedock.utils import KubeUtils, register_api, APIError, send_event
from kubedock.kapi.podcollection import PodCollection
from kubedock.validation import check_new_pod_data
from kubedock.settings import KUBE_API_VERSION
from kubedock.billing.models import Kube

yamlapi = Blueprint('yaml_api', __name__, url_prefix='/yamlapi')


class YamlAPI(KubeUtils, MethodView):
    decorators = (
        KubeUtils.jsonwrap,
        KubeUtils.pod_permissions,
        KubeUtils.pod_start_permissions,
        login_required_or_basic_or_token
    )

    @maintenance_protected
    def post(self):
        user = self._get_current_user()
        data = self._get_params().get('data')
        if data is None:
            raise APIError('No "data" provided')
        try:
            parsed_data = list(yaml.safe_load_all(data))
        except yaml.YAMLError as e:
            raise APIError('Incorrect yaml, parsing failed: "{0}"'.format(e))
        new_pod = dispatch_kind(parsed_data)
        check_new_pod_data(new_pod, user)

        try:
            res = PodCollection(user).add(new_pod)
        except APIError as e:
            raise e
        except Exception as e:
            raise APIError('Unknown error during creating pod: {0}'.format(e))
        send_event('pull_pods_state', 'ping', channel='user_%s' % user.id)
        return res

register_api(yamlapi, YamlAPI, 'yamlapi', '/', 'pod_id', strict_slashes=False)


def dispatch_kind(docs):
    if not docs or not docs[0]:     # at least one needed
        raise APIError("No objects found in data")
    pod, rc, service = None, None, None
    for doc in docs:
        if not isinstance(doc, dict):
            raise APIError('Document must describe an object, '
                           'not just string or number')
        kind = doc.get('kind')
        if not kind:
            raise APIError('No object kind information')
        api_version = doc.get('apiVersion')
        if api_version != KUBE_API_VERSION:
            raise APIError(
                'Not supported apiVersion. Must be {0}'.format(KUBE_API_VERSION))
        if kind == 'Pod':
            if pod is not None:
                raise APIError('Only one Pod per yaml is allowed')
            pod = doc
        elif kind == 'ReplicationController':
            if rc is not None:
                raise APIError('Only one ReplicationController per yaml is allowed')
            rc = doc
        elif kind == 'Service':
            if service is not None:
                raise APIError('Only one Service per yaml is allowed')
            service = doc
        else:
            raise APIError('Unsupported object kind')
    if not pod and not rc:
        raise APIError('At least Pod or ReplicationController is needed')
    if pod and rc:
        raise APIError('Only one Pod or ReplicationController is allowed '
                       'but not both')
    return process_pod(pod, rc, service)


def process_pod(pod, rc, service):
    # TODO for now Services are useless and ignored
    if rc:
        doc = rc
        rc_spec = rc.get('spec', {})
        spec_body = rc_spec.get('template', {}).get('spec', {})
        replicas = rc_spec.get('replicas', 1)
    else:
        doc = pod
        spec_body = pod.get('spec', {})
        replicas = spec_body.get('replicas', 1)

    kdSection = doc.get('kuberdock', {})

    new_pod = {
        'name': doc.get('metadata', {}).get('name', ''),
        'restartPolicy': spec_body.get('restartPolicy', "Always"),
        'replicas': replicas,
        'kube_type': kdSection.get('kube_type', Kube.get_default_kube_type()),
        'kuberdock_template_id': kdSection.get('kuberdock_template_id'),
    }

    if 'containers' in spec_body:
        containers = spec_body['containers'] or []
        for c in containers:
            for p in c.get('ports', []):
                p.pop('name', '')
        new_pod['containers'] = containers

    if 'volumes' in spec_body:
        new_pod['volumes'] = spec_body['volumes'] or []
    return new_pod
