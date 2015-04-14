import json
from .. import tasks
from ..core import db
from ..pods import Pod
from ..users import User
from uuid import uuid4
from flask.ext.login import current_user
from flask import current_app



class KubeResolver(object):

    def resolve_all(self):
        self._replicas = self._parse_replicas()
        self._pods = self._parse_pods()
        self._services = self._parse_services()
        self._merge_with_db()
        return self._pods

    def resolve_by_replica_name(self, name):
        return self._parse_replicas(name)

    @staticmethod
    def _get_replicas():
        """Get list of replicas via REST API call task"""
        return tasks.get_replicas_nodelay()

    def _parse_replicas(self, name=None):
        """Parse received list of replicas to a structure"""
        replicas = []       # replicationControllers
        data = self._get_replicas()
        if not 'items' in data:
            return replicas # Nothing to parse: no data
        for item in data['items']:
            try:
                replica_item = {
                    'id': item['uid'],
                    'sid': item['id'],
                    'replicas': item['currentState']['replicas'],
                    'replicaSelector': item['desiredState']['replicaSelector'],
                    'name': item['labels']['name']}

                if name is not None and replica_item['replicaSelector'] != name:
                    continue
                replicas.append(replica_item)
            except KeyError:
                pass
        return replicas

    @staticmethod
    def _get_pods():
        """Get list of pods via REST API call task"""
        return tasks.get_pods_nodelay()

    @staticmethod
    def _get_dockers(data):
        if not 'currentState' in data or \
           not 'status' in data['currentState'] or \
           not data['currentState']['status'] == 'Running':
            return []
        dockers = []
        for pod_name, pod_info in data['currentState']['info'].items():
            if pod_name == 'POD':
                continue
            dockers.append({
                'host': data['currentState']['host'],
                'info': pod_info,
                'podIP': data['currentState'].get('podIP', '')
            })
        return dockers

    def _parse_pods(self):
        """
        Parse received pods, learning if there are pods pertaining to certain replicas,
        and modify attributes of such pods if any
        """
        pods = []
        pod_index = set()
        data = self._get_pods()

        if 'items' not in data:
            return pods
        for item in data['items']:  # iterate through pods list

            # filter out service pods
            try:
                if item.get('labels')['kubernetes.io/cluster-service']:
                    continue
            except KeyError:
                pass
            except TypeError:
                continue

            try:    # getting UUID
                item_uuid = item['desiredState']['manifest']['uuid']
            except KeyError:
                item_uuid = item.get('uid', str(uuid4()))
            try:
                containers = item['desiredState']['manifest']['containers']
                for c in containers:
                    c['imageID'] = item['currentState']['info'].get(
                        c['name'], {}).get('imageID')
                items = {'id': item_uuid,
                         'name': item['labels']['name'],
                         'sid': item['id'],
                         'cluster': False,
                         'replicas': 1,
                         'status': item['currentState']['status'].lower(),
                         'dockers': self._get_dockers(item),
                         'containers': containers,
                         'volumes': item['desiredState']['manifest']['volumes'],
                         'service': False,
                         'labels': item['labels']}
            except KeyError:
                continue

            if hasattr(self, '_replicas'):
                for r in self._replicas:    # iterating through replicas list received earlier
                    if self._is_related(r['replicaSelector'], item['labels']):
                        items['cluster'] = True
                        for i in 'id', 'sid', 'replicas':
                            items[i] = r[i]
                        break

                if items['sid'] not in pod_index:
                    pod_index.add(items['sid'])
                    pods.append(items)
            else:
                pods.append(items)
        return pods

    @staticmethod
    def _get_services():
        return tasks.get_services_nodelay()

    def _parse_services(self):
        """
        Get services from REST API and mark pods which have entripoints
        """
        data = self._get_services()
        if 'items' not in data:
            return []

        if hasattr(self, '_pods'):
            for item in data['items']:
                for pod in self._pods:
                    try:
                        if self._is_related(pod['labels'], item['selector']):
                            pod['port'] = item['port']
                            pod['portalIP'] = item['portalIP']
                            pod['service'] = True
                            pod['servicename'] = item['labels']['name']
                            break
                    except KeyError:
                        pass
        return data['items']

    @staticmethod
    def _select_pods_from_db():
        data = {}
        for i in db.session.query(Pod).join(Pod.owner).filter(Pod.status!='deleted').values(
                Pod.id, Pod.name, User.username, Pod.config):
            # Ugly temporary workaround while DB has JSON and non-JSON entries
            try:
                conf = json.loads(i[3])
            except (ValueError, TypeError):
                conf = i[3]
            data[i[1]] = {'id': i[0], 'username': i[2], 'config':conf}
        return data

    def _merge_with_db(self):
        db_pods = self._select_pods_from_db()
        kube_names = set(map((lambda x: x['name']), self._pods))
        # We check if a pod is present in DB (by name)
        for pod_name in db_pods:
            if pod_name not in kube_names:
                # add config for displaying in front-end
                pending_pod = db_pods[pod_name]['config']
                dockers = []
                for container in pending_pod['containers']:
                    container['imageID'] = 'docker://'
                    dockers.append({
                        'host': '',
                        'info': {
                            'containerID': 'docker://',
                            'image': container['image'],
                            'imageID': container['imageID'],
                            'lastState': {},
                            'ready': False,
                            'restartCount': 0,
                            'state': {'stopped': {}},
                        }
                    })
                pending_pod['dockers'] = dockers
                pending_pod['id'] = db_pods[pod_name]['id']
                self._pods.append(pending_pod)
            else: # we want to substitute all pods UUIDs for database pods UUIDs
                diff = filter((lambda x: x['name'] == pod_name), self._pods)
                for pod in diff:
                    pod['id'] = db_pods[pod_name]['id']
                    pod['kube_type'] = db_pods[pod_name]['config']['kube_type']
        for pod in self._pods:
            try:
                pod['owner'] = db_pods[pod['name']]['username']
            except (KeyError, TypeError):
                pod['owner'] = 'unknown'

    @staticmethod
    def _is_related(one, two):
        if one is None or two is None:
            return False
        for k in two.keys():
            if k not in one:
                return False
            if one[k] != two[k]:
                return False
            return True
