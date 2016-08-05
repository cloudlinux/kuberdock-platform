import json
from copy import copy
import time

from ..core import ExclusiveLock
from .helpers import KubeQuery
from ..settings import NODE_CEPH_AWARE_KUBERDOCK_LABEL


class NodeException(Exception):
    pass


class NodeNotFound(NodeException):
    pass


class NodeExceptionIPCounterMissing(NodeException):
    pass


class NodeExceptionUpdateFailure(NodeException):
    pass


class NodeExceptionNegativeFreeIPCount(NodeException):
    pass


class Node(object):
    FREE_PUBLIC_IP_COUNTER_FIELD = 'kuberdock-free-ips-count'
    K8S_CONFLICT_CODE = 409
    K8S_SUCCESS_CODE = 200

    def __init__(self, hostname, kube_type=None):
        self.hostname, self.kube_type = hostname, kube_type
        self._k8s_data = None
        self.k8squery = KubeQuery()

    @property
    def k8s_data(self):
        if not self._k8s_data:
            self.fetch_data_from_k8s()
        return self._k8s_data

    def fetch_data_from_k8s(self):
        """
        Retrieves node data from K8S by it's hostname. Raises exception in
        case K8S API returns a response with a Failure status
        """
        data = self.k8squery.get(['nodes', self.hostname])
        if data.get('status') == 'Failure':
            if data['code'] == 404:
                raise NodeNotFound(data['message'])
            raise NodeException('{} {}'.format(data['code'], data['message']))
        self._k8s_data = data

    def update_data_on_k8s(self):
        """
        Updates k8s node spec using the spec saved in self.k8s_data
        :return: True if update succeeded and False there was a
        successful concurrent update which altered pod spec version
        """
        data = copy(self.k8s_data)
        # Drop if exists status because it's not needed during update
        data.pop('status', None)

        result = self.k8squery.put(['nodes', self.hostname], json.dumps(data))
        return result.get('code') != self.K8S_CONFLICT_CODE

    def increment_free_public_ip_count(self, delta=1, max_retries=5):
        """
        Atomically increases the number of public IP addresses available on a
        node. Fetches a K8S node information beforehand
        :param max_retries: how many times we try to update the counter if
        somebody concurrently updated spec
        :param delta: positive or negative number which is added to the
        current ip count
        """
        lock = ExclusiveLock('NODE.PUBLIC_IP_INCR_{}'.format(self.hostname))
        lock.lock(blocking=True)
        try:
            for _ in range(max_retries):
                self.fetch_data_from_k8s()
                new_count = self.free_public_ip_count + delta

                # For example we have 1 free ip and scheduler scheduled a
                # pod, decreasing this number by 1 and here we are trying to
                # decrease it once more. We'll get new_count == -1 and
                # that's an error, we need to prohibit the caller from
                # blocking or removing IP
                if new_count < 0:
                    raise NodeExceptionNegativeFreeIPCount()
                if self.update_free_public_ip_count(new_count):
                    return
                time.sleep(0.1)
        finally:
            lock.release()

        raise NodeExceptionUpdateFailure('Could not update public ip  counter '
                                         'node. There were concurrent'
                                         'updates, blocking this update for '
                                         'too long')

    @property
    def free_public_ip_count(self):
        try:
            return int(self.k8s_data['metadata']['annotations'][
                           self.FREE_PUBLIC_IP_COUNTER_FIELD])
        except KeyError:
            # We have no idea what does a missing IP counter annotation mean
            # Should we set a counter to 0 or recalculate free public IPs
            # from DB: let a callee side to decide
            raise NodeExceptionIPCounterMissing()

    @free_public_ip_count.setter
    def free_public_ip_count(self, value):
        self.k8s_data['metadata']['annotations'][
            self.FREE_PUBLIC_IP_COUNTER_FIELD] = value

    def update_free_public_ip_count(self, count):
        """
        Updates the number of free public IP available on a node by
        updating K8S node annotation
        :param count: the number of free IPs to set
        :return: True if update succeeded and False if there was a
        concurrent update which altered node spec and thus changed resource
        version
        """
        self.free_public_ip_count = str(count)
        return self.update_data_on_k8s()

    def patch_annotations(self, annotations):
        """
        Patches annotations metadata in K8S using JSON-Patch.
        :param annotations: dictionary of annotations to be used in patch.
        The patch behaviour is described here:
        https://tools.ietf.org/html/rfc7386 for dict format
        """
        data = {
            'metadata': {
                'annotations': annotations
            }
        }
        self.k8squery.patch(['nodes', self.hostname], json.dumps(data))

    def patch_labels(self, labels):
        """
        Patches labels metadata in K8S using JSON-Patch.
        :param labels: dictionary of labels to be used in patch.
        The patch behaviour is described here:
        https://tools.ietf.org/html/rfc7386 for dict format
        """
        data = {
            'metadata': {
                'labels': labels
            }
        }
        self.k8squery.patch(['nodes', self.hostname], json.dumps(data))

    def add_to_k8s(self, use_ceph=False):
        """
        Add node to K8S by calling K8S API server with default metadata
        based on node's fields
        :param use_ceph: bool flag if CEPH is enabled on a node
        :return: False if everything went OK. Error message otherwise
        """
        data = {
            'metadata': {
                'name': self.hostname,
                'labels': {
                    'kuberdock-node-hostname': self.hostname,
                    'kuberdock-kube-type':
                        'type_{}'.format(self.kube_type)
                },
                'annotations': {
                    self.FREE_PUBLIC_IP_COUNTER_FIELD: '0'
                }
            },
            'spec': {
                'externalID': self.hostname,
            }
        }
        if use_ceph:
            data['metadata']['labels'][
                NODE_CEPH_AWARE_KUBERDOCK_LABEL] = 'True'
        try:
            response = self.k8squery.post(['nodes'], json.dumps(data))
            return response.text if not response.ok else False
        except SystemExit as e:
            return str(e)
