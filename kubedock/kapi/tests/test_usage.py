"""Unit tests for kapi.usage
"""
import unittest
import json
import mock
from uuid import uuid4
from datetime import datetime, timedelta

from kubedock.core import db
from kubedock.testutils import fixtures
from kubedock.testutils.testcases import DBTestCase
from kubedock.kapi import usage
from kubedock.pods import models as pod_models
from kubedock.billing import models as bill_models
from kubedock.usage.models import PodState


class TestPodStates(DBTestCase):
    """kapi.usage.update_states: tests for pod states."""
    def setUp(self):
        self.user, user_password = fixtures.user_fixtures()
        self.containers = [{'name': '23edwed3', 'kubes': 3},
                           {'name': 'gacs4frs', 'kubes': 5}]
        self.pod1 = pod_models.Pod(
            id=str(uuid4()),
            name='p1',
            owner_id=self.user.id,
            kube_id=bill_models.Kube.get_default_kube_type(),
            config=json.dumps({'containers': self.containers}),
            status='RUNNING'
        )
        self.pod2 = pod_models.Pod(
            id=str(uuid4()),
            name='p2',
            owner_id=self.user.id,
            kube_id=bill_models.Kube.get_default_kube_type(),
            config=json.dumps({'containers': self.containers}),
            status='RUNNING'
        )
        db.session.add_all([self.pod1, self.pod2])
        db.session.commit()

    @staticmethod
    def _upd_state(pod_id, event, start_time=None, host=None):
        usage.update_states({
            'metadata': {'labels': {'kuberdock-pod-uid': pod_id}},
            'spec': {'nodeName': host},
            'status': {'startTime': start_time},
        }, event)

    def test_save_state(self):
        pod1_id = self.pod1.id
        pod2_id = self.pod2.id
        host1 = 'host1'
        host2 = 'host2'
        self._upd_state(pod1_id, 'ADDED')  # ignored
        self._upd_state(pod1_id, 'MODIFIED', datetime(2015, 11, 25, 12), host1)
        states = PodState.query.all()
        self.assertTrue(len(states), 1)
        self.assertEqual(states[0].pod_id, pod1_id)
        self.assertEqual(states[0].last_event, 'MODIFIED')
        self.assertIsNone(states[0].end_time)
        self.assertEqual(states[0].hostname, host1)

        # self._upd_state(pod2_id, 'ADDED')  # ignored
        self._upd_state(pod2_id, 'MODIFIED', datetime(2015, 11, 25, 12), host2)
        states = PodState.query.all()
        self.assertTrue(len(states), 2)
        states = {item.pod_id: item for item in states}
        self.assertEqual(states[pod1_id].last_event, 'MODIFIED')
        self.assertEqual(states[pod2_id].hostname, host2)
        self.assertEqual(states[pod2_id].last_event, 'MODIFIED')

        def check_2_of_3():
            states = PodState.query.order_by(PodState.start_time).all()
            self.assertEqual(len(states), 3)
            states = [item for item in states if item.pod_id == pod1_id]
            self.assertEqual(len(states), 2)
            return states

        # self._upd_state(pod1_id, 'ADDED')  # ignored
        self._upd_state(pod1_id, 'MODIFIED', datetime(2015, 11, 25, 14), host2)
        states = check_2_of_3()
        self.assertIsNotNone(states[0].end_time)
        self.assertEqual(states[0].hostname, host1)
        self.assertIsNone(states[1].end_time)
        self.assertEqual(states[1].hostname, host2)
        self.assertEqual(states[1].last_event, 'MODIFIED')

        self._upd_state(pod1_id, 'DELETED', datetime(2015, 11, 25, 14), host2)
        states = check_2_of_3()
        self.assertIsNotNone(states[1].end_time)
        self.assertEqual(states[1].hostname, host2)
        self.assertEqual(states[1].last_event, 'DELETED')

    def test_select_pod_states_history(self):
        """Test for kapi.usage.select_pod_states_history function."""
        pod1_id = self.pod1.id
        pod2_id = self.pod2.id
        host1 = 'host1'
        host2 = 'host2'
        res = usage.select_pod_states_history(pod1_id)
        self.assertEqual(res, [])

        self._upd_state(pod1_id, 'ADDED')
        self._upd_state(pod1_id, 'MODIFIED', datetime(2015, 11, 25, 12), host1)
        self._upd_state(pod1_id, 'DELETED', datetime(2015, 11, 25, 12), host1)
        self._upd_state(pod1_id, 'ADDED')
        self._upd_state(pod1_id, 'MODIFIED', datetime(2015, 11, 25, 13), host1)

        res = usage.select_pod_states_history(pod1_id)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]['last_event'], 'MODIFIED')
        self.assertEqual(res[1]['last_event'], 'DELETED')
        self.assertEqual(res[0]['hostname'], host1)
        self.assertEqual(res[1]['hostname'], host1)
        self.assertIsNone(res[0]['end_time'])
        self.assertIsNotNone(res[1]['end_time'])

        self._upd_state(pod1_id, 'DELETED', datetime(2015, 11, 25, 13), host1)
        self._upd_state(pod1_id, 'ADDED')
        self._upd_state(pod1_id, 'MODIFIED', datetime(2015, 11, 25, 14), host2)
        res = usage.select_pod_states_history(pod1_id)
        self.assertEqual(len(res), 3)
        self.assertEqual(res[0]['hostname'], host2)
        self.assertIsNone(res[0]['end_time'])

        # check depth parameter is working
        last_state = res[0]
        res = usage.select_pod_states_history(pod1_id, 1)
        self.assertEqual(res, [last_state])

        # check filter by pod id is working
        self._upd_state(pod2_id, 'ADDED')
        self._upd_state(pod2_id, 'MODIFIED', datetime(2015, 11, 25, 13), host1)
        res = usage.select_pod_states_history(pod1_id)
        self.assertEqual(len(res), 3)

    def test_close_other_pod_states(self):
        """Test for PodState.close_other_pod_states function."""
        dt = datetime.utcnow()

        def PS(**kwargs):
            if 'last_event_time' not in kwargs:
                if kwargs.get('last_event') == 'ADDED':
                    kwargs['last_event_time'] = kwargs.get('start_time')
                elif kwargs.get('last_event') == 'DELETED':
                    kwargs['last_event_time'] = kwargs.get('end_time')
            return PodState(**dict({'pod': self.pod1,
                                    'kube_id': self.pod1.kube_id,
                                    'last_event': 'ADDED'}, **kwargs))

        pod_states = [
            PS(start_time=dt - timedelta(hours=50),
               end_time=dt - timedelta(hours=45),
               last_event='DELETED', hostname='kdnode1'),
            PS(start_time=dt - timedelta(hours=44),  # not finished
               last_event='MODIFIED', hostname='kdnode1'),
            PS(start_time=dt - timedelta(hours=42),  # ok
               end_time=dt - timedelta(hours=40),
               last_event='DELETED', hostname='kdnode1'),
            PS(start_time=dt - timedelta(hours=39),  # not finished too
               last_event='ADDED', hostname='kdnode1'),
            PS(start_time=dt - timedelta(hours=35),  # current
               last_event='ADDED', hostname='kdnode1'),
        ]

        self.db.session.add_all(pod_states)
        PodState.close_other_pod_states(self.pod1.id, dt - timedelta(hours=35))
        pod_states[1].end_time = dt - timedelta(hours=35)
        pod_states[3].end_time = dt - timedelta(hours=35)
        self.assertEqual([ps.to_dict() for ps in self.pod1.states],
                         [ps.to_dict() for ps in pod_states])

    def test_kube_id_state(self):
        pod1_id = self.pod1.id
        self.pod1.kube_id = 0
        self._upd_state(pod1_id, 'ADDED', datetime(2015, 11, 25, 11))
        self.pod1.kube_id = 1
        self._upd_state(pod1_id, 'MODIFIED', datetime(2015, 11, 25, 12))
        states = PodState.query.all()
        self.assertEqual(len(states), 2)
        self.assertEqual(states[0].pod_id, pod1_id)
        self.assertEqual(states[0].last_event, 'MODIFIED')
        self.assertIsNone(states[0].end_time)
        self.assertEqual(states[0].kube_id, 1)
        self.assertEqual(states[1].kube_id, 0)
        self.pod1.kube_id = bill_models.Kube.get_default_kube_type(),


@mock.patch.object(usage, 'fix_pods_timeline_heavy', mock.Mock())
class TestUpdateStates(DBTestCase):
    def setUp(self):
        self.containers = [{'name': '23edwed3', 'kubes': 3},
                           {'name': 'gacs4frs', 'kubes': 5},
                           {'name': '4eoncsrh'}]
        self.pod = self.fixtures.pod(config=json.dumps({
            'containers': self.containers,
        }))
        self.event_started = {
            'metadata': {'labels': {'kuberdock-pod-uid': self.pod.id}},
            'spec': {},
            'status': {
                'containerStatuses': [{
                    'restartCount': 0,
                    'name': self.containers[0]['name'],
                    'image': '45.55.52.203:5000/test-rc-pd',
                    'imageID': 'docker://a5790f69b866b30aa808d753c43e0a',
                    'state': {'running': {'startedAt': datetime(2015, 11, 25, 12, 42, 45)}},
                    'ready': True,
                    'lastState': {},
                    'containerID': 'docker://41b699c3802b599be2656235f2'
                }, {
                    'restartCount': 0,
                    'name': self.containers[1]['name'],
                    'image': '45.55.52.203:5000/test-rc-pd',
                    'imageID': 'docker://753c43e0aa5790f69b866b30aa808d',
                    'state': {'running': {'startedAt': datetime(2015, 11, 25, 12, 42, 47)}},
                    'ready': True,
                    'lastState': {},
                    'containerID': 'docker://f35fd17d8e36702f55b06ede7b'
                }, {
                    'restartCount': 0,
                    'name': self.containers[2]['name'],
                    'image': '45.55.52.203:5000/test-rc-pd',
                    'imageID': 'docker://0aa808d753c43e0aa5790f69b866b3',
                    'state': {'running': {'startedAt': datetime(2015, 11, 25, 12, 42, 46)}},
                    'ready': True,
                    'lastState': {},
                    'containerID': 'docker://6702f55b06ede7bf35fd17d8e3'
                }],
                'startTime': datetime(2015, 11, 10, 12, 12, 12),
            }
        }

        self.pod_state = usage.PodState(
            pod_id=self.pod.id,
            kube_id=self.pod.kube_id,
            start_time=self.event_started['status']['startTime']).save()

    def test_kubes_are_saved(self):
        """kubes == value from k8s-pod annotaions or value from database or 1"""
        CS = usage.ContainerState

        kubes_in_annotations = {self.containers[0]['name']: 7}
        event = self.event_started
        event['metadata']['annotations'] = {
            'kuberdock-container-kubes': json.dumps(kubes_in_annotations),
        }
        usage.update_states(event)
        for container in self.pod.get_dbconfig('containers'):
            name = container['name']
            self.assertIsNotNone(CS.query.filter(
                CS.container_name == name,
                CS.kubes == (kubes_in_annotations.get(name) or
                             container.get('kubes', 1)),
            ).first())

    def test_pod_state_is_not_created(self):
        self.assertEqual(len(self.pod.states), 1)
        usage.update_states(self.event_started)
        self.assertEqual(len(self.pod.states), 1)

    def test_pod_state_is_created_if_not_found(self):
        db.session.delete(self.pod_state)
        CS = usage.ContainerState

        usage.update_states(self.event_started)
        for container in self.pod.get_dbconfig('containers'):
            cs = CS.query.filter(
                CS.container_name == container['name'],
                CS.kubes == container.get('kubes', 1),
            ).first()
            self.assertIsNotNone(cs)
            self.assertIsNotNone(cs.pod_state)
            self.assertLessEqual(cs.pod_state.start_time, cs.start_time)
            self.assertGreaterEqual(cs.pod_state.end_time, cs.end_time)

    def test_pod_start_time_used(self):
        db.session.delete(self.pod_state)
        usage.update_states(self.event_started)
        self.assertEqual(self.pod.states[0].start_time,
                         self.event_started['status']['startTime'])

    def test_event_time_used(self):
        db.session.delete(self.pod_state)
        CS = usage.ContainerState
        event_time = datetime(2015, 11, 30, 12, 12, 12)

        usage.update_states(self.event_started,
                            event_type='DELETED', event_time=event_time)
        self.assertEqual(self.pod.states[0].end_time, event_time)
        for container in self.pod.get_dbconfig('containers'):
            self.assertIsNotNone(CS.query.filter(
                CS.container_name == container['name'],
                CS.kubes == container.get('kubes', 1),
                CS.end_time == event_time,
            ).first())


if __name__ == '__main__':
    # logging.basicConfig(stream=sys.stderr)
    # logging.getLogger('TestPodCollection.test_pod').setLevel(logging.DEBUG)
    unittest.main()
