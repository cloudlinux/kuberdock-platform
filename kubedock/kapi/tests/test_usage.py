"""Unit tests for kapi.usage
"""
import unittest
import json
import mock
from uuid import uuid4
from datetime import datetime

from kubedock.core import db
from kubedock.testutils import fixtures
from kubedock.testutils.testcases import DBTestCase
from kubedock.kapi import usage
from kubedock.pods import models as pod_models
from kubedock.billing import models as bill_models
from kubedock.usage.models import PodState


class TestPodStates(DBTestCase):
    def setUp(self):
        self.user, user_password = fixtures.user_fixtures()
        self.pod1 = pod_models.Pod(
            id=str(uuid4()),
            name='p1',
            owner_id=self.user.id,
            kube_id=bill_models.Kube.get_default_kube_type(),
            config='',
            status='RUNNING'
        )
        self.pod2 = pod_models.Pod(
            id=str(uuid4()),
            name='p2',
            owner_id=self.user.id,
            kube_id=bill_models.Kube.get_default_kube_type(),
            config='',
            status='RUNNING'
        )
        db.session.add_all([self.pod1, self.pod2])
        db.session.commit()

    def test_save_state(self):
        """Test for kapi.save_pod_state function."""
        pod1_id = self.pod1.id
        pod2_id = self.pod2.id
        host1 = 'host1'
        host2 = 'host2'
        usage.save_pod_state(pod1_id, 'ADDED', host1)
        states = PodState.query.all()
        self.assertTrue(len(states), 1)
        self.assertEqual(states[0].hostname, host1)
        self.assertEqual(states[0].pod_id, pod1_id)
        self.assertEqual(states[0].last_event, 'ADDED')
        self.assertIsNone(states[0].end_time)

        usage.save_pod_state(pod1_id, 'MODIFIED', host1)
        usage.save_pod_state(pod2_id, 'ADDED', host2)
        states = PodState.query.all()
        self.assertTrue(len(states), 2)
        states = {item.pod_id: item for item in states}
        self.assertEqual(states[pod1_id].last_event, 'MODIFIED')
        self.assertEqual(states[pod2_id].hostname, host2)
        self.assertEqual(states[pod2_id].last_event, 'ADDED')

        usage.save_pod_state(pod1_id, 'ADDED', host2)
        states = PodState.query.order_by(PodState.start_time).all()
        self.assertEqual(len(states), 3)
        states = [item for item in states if item.pod_id == pod1_id]
        self.assertEqual(len(states), 2)
        self.assertIsNotNone(states[0].end_time)
        self.assertEqual(states[0].hostname, host1)
        self.assertIsNone(states[1].end_time)
        self.assertEqual(states[1].hostname, host2)
        self.assertEqual(states[1].last_event, 'ADDED')

        usage.save_pod_state(pod1_id, 'DELETED', host2)
        states = PodState.query.order_by(PodState.start_time).all()
        self.assertEqual(len(states), 3)
        states = [item for item in states if item.pod_id == pod1_id]
        self.assertEqual(len(states), 2)
        self.assertIsNotNone(states[1].end_time)
        self.assertEqual(states[1].hostname, host2)
        self.assertEqual(states[1].last_event, 'DELETED')

    def test_select_pod_states_history(self):
        """Test for kapi.select_pod_states_history function."""
        pod1_id = self.pod1.id
        pod2_id = self.pod2.id
        host1 = 'host1'
        host2 = 'host2'
        res = usage.select_pod_states_history(pod1_id)
        self.assertEqual(res, [])

        usage.save_pod_state(pod1_id, 'ADDED', host1)
        usage.save_pod_state(pod1_id, 'MODIFIED', host1)
        usage.save_pod_state(pod1_id, 'DELETED', host1)
        usage.save_pod_state(pod1_id, 'ADDED', host1)
        res = usage.select_pod_states_history(pod1_id)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]['last_event'], 'ADDED')
        self.assertEqual(res[1]['last_event'], 'DELETED')
        self.assertEqual(res[0]['hostname'], host1)
        self.assertEqual(res[1]['hostname'], host1)
        self.assertIsNone(res[0]['end_time'])
        self.assertIsNotNone(res[1]['end_time'])

        usage.save_pod_state(pod1_id, 'DELETED', host1)
        usage.save_pod_state(pod1_id, 'ADDED', host2)
        res = usage.select_pod_states_history(pod1_id)
        self.assertEqual(len(res), 3)
        self.assertEqual(res[0]['hostname'], host2)
        self.assertIsNone(res[0]['end_time'])

        # check depth parameter is working
        last_state = res[0]
        res = usage.select_pod_states_history(pod1_id, 1)
        self.assertEqual(res, [last_state])

        # check filter by pod id is working
        usage.save_pod_state(pod2_id, 'ADDED', host1)
        res = usage.select_pod_states_history(pod1_id)
        self.assertEqual(len(res), 3)


@mock.patch.object(usage, 'fix_pods_timeline_heavy', mock.Mock())
class TestUpdateContainerStates(DBTestCase):
    def setUp(self):
        self.containers = [{'name': '23edwed3', 'kubes': 3},
                           {'name': 'gacs4frs', 'kubes': 5}]
        self.pod = self.fixtures.pod(config=json.dumps({
            'containers': self.containers,
        }))
        self.pod_state = usage.PodState(pod_id=self.pod.id,
                                        start_time=datetime(2015, 11, 1)).save()
        self.event_started = [{
            'restartCount': 0,
            'name': self.containers[0]['name'],
            'image': '45.55.52.203:5000/test-rc-pd',
            'imageID': 'docker://a5790f69b866b30aa808d753c43e0a',
            'state': {'running': {'startedAt': '2015-11-25T12:42:45Z'}},
            'ready': True,
            'lastState': {},
            'containerID': 'docker://41b699c3802b599be2656235f2'
        }, {
            'restartCount': 0,
            'name': self.containers[1]['name'],
            'image': '45.55.52.203:5000/test-rc-pd',
            'imageID': 'docker://a5790f69b866b30aa808d753c43e0a',
            'state': {'running': {'startedAt': '2015-11-25T12:42:47Z'}},
            'ready': True,
            'lastState': {},
            'containerID': 'docker://f35fd17d8e36702f55b06ede7b'
        }]

    def test_kubes_are_saved(self):
        CS = usage.ContainerState

        usage.update_containers_state(self.pod.id, self.event_started)
        for container in self.pod.get_dbconfig('containers'):
            self.assertIsNotNone(CS.query.filter(
                CS.container_name == container['name'],
                CS.kubes == container['kubes'],
            ).first())


if __name__ == '__main__':
    # logging.basicConfig(stream=sys.stderr)
    # logging.getLogger('TestPodCollection.test_pod').setLevel(logging.DEBUG)
    unittest.main()
