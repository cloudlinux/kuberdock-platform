"""Unit tests for kapi.usage
"""
import unittest
from uuid import uuid4

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


if __name__ == '__main__':
    # logging.basicConfig(stream=sys.stderr)
    # logging.getLogger('TestPodCollection.test_pod').setLevel(logging.DEBUG)
    unittest.main()
