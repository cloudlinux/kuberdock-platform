import logging

from tests_integration.lib.utils import (
    assert_eq, assert_raises, log_debug, POD_STATUSES)
from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.exceptions import NonZeroRetCodeException

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


def assert_pv_states(pv_info, expected_states, pod_names=None):
    """
    Check that PV states are correct and that pods from pod_names are listed
    in linkedPods
    :param pv_info: PV info dictionary
    :param exected_states: States to check, ex. {'forbidDeletion': False}
    :param pod_names: Check that pod_names are present in linkedPods of a PV
                      Defaults to None, i.e. don't check
    """
    for state_name, state_value in expected_states.items():
        assert_eq(pv_info[state_name], state_value)

    if pod_names is None:
        return

    linked_pods = pv_info['linkedPods']
    assert_eq(len(linked_pods), len(pod_names))

    for pod_name in pod_names:
        assert_eq(len([p for p in linked_pods if p['name'] == pod_name]), 1)


@pipeline('main')
@pipeline('main_upgraded')
@pipeline('zfs')
@pipeline('zfs_upgraded')
@pipeline('zfs_aws')
@pipeline('zfs_aws_upgraded')
@pipeline('ceph', skip_reason='FIXME in AC-5206')
@pipeline('ceph_upgraded', skip_reason='FIXME in AC-5206')
def test_pv_states_and_deletion_via_kcli2(cluster):
    """
    TestRail Case: Different states of persistent volumes (kcli2)
    https://cloudlinux.testrail.net/index.php?/cases/view/145

    TestRail Case: Removing persistent volume (kcli2)
    https://cloudlinux.testrail.net/index.php?/cases/view/143

    TestRail Case: Try to remove persistent volume which is in use (kcli2)
    https://cloudlinux.testrail.net/index.php?/cases/view/146
    """
    pv1_name = 'disk1'
    pv2_name = 'disk2'
    pv1_mpath = '/nginxpv1'
    pv2_mpath = '/nginxpv2'
    pv1 = cluster.pvs.add('dummy', pv1_name, pv1_mpath)
    pv2 = cluster.pvs.add('dummy', pv2_name, pv2_mpath)
    pod_name = 'test_nginx_pv_states_via_kcli'
    pod = cluster.pods.create(
        'nginx', pod_name, pvs=[pv1, pv2], start=True,
        wait_for_status=POD_STATUSES.running)

    log_debug('Get PV info via kcli2 using PV name', LOG)
    pv1_info = pv1.info()
    pv2_info = pv2.info()
    # Get 'disk1' and 'disk2' ids
    pv1_id = pv1_info['id']
    pv2_id = pv2_info['id']

    # Disk1 states: 'forbidDeletion': True, 'in_use': True
    # 'test_nginx_pv_states_via_kcli' in 'disk1' linkedPods
    assert_pv_states(pv1_info,
                     expected_states=dict(forbidDeletion=True, in_use=True),
                     pod_names=[pod_name])

    # Disk2 states: 'forbidDeletion': True, 'in_use': True
    # 'test_nginx_pv_states_via_kcli' in 'disk2' linkedPods
    assert_pv_states(pv2_info,
                     expected_states=dict(forbidDeletion=True, in_use=True),
                     pod_names=[pod_name])

    log_debug('Get PV info via kcli2 using PV id', LOG)
    pv1_info = pv1.info(id=pv1_id)
    pv2_info = pv2.info(id=pv2_id)

    # Disk1 states: 'forbidDeletion': True, 'in_use': True
    # 'test_nginx_pv_states_via_kcli' in 'disk1' linkedPods
    assert_pv_states(pv1_info,
                     expected_states=dict(forbidDeletion=True, in_use=True),
                     pod_names=[pod_name])

    # Disk2 states: 'forbidDeletion': True, 'in_use': True
    # 'test_nginx_pv_states_via_kcli' in 'disk2' linkedPods
    assert_pv_states(pv2_info,
                     expected_states=dict(forbidDeletion=True, in_use=True),
                     pod_names=[pod_name])

    log_debug("Try to delete PVs 'disk1' and 'disk2' with pod 'running'", LOG)
    with assert_raises(NonZeroRetCodeException, 'Persistent disk is used.*'):
        pv1.delete(name=pv1_name)

    with assert_raises(NonZeroRetCodeException, 'Persistent disk is used.*'):
        pv2.delete(id=pv2_id)

    log_debug('List PVs using kcli2', LOG)
    pv_list = cluster.pvs.filter()

    log_debug("Make sure 'disk1' and 'disk2' are in the list", LOG)
    assert_eq(pv1_name in [pv['name'] for pv in pv_list], True)
    assert_eq(pv2_name in [pv['name'] for pv in pv_list], True)

    # Stop the pod
    pod.stop()
    pod.wait_for_status(POD_STATUSES.stopped)

    log_debug("Try to delete PVs 'disk1' and 'disk2' with pod 'stopped'", LOG)
    with assert_raises(NonZeroRetCodeException, 'Volume can not be deleted.'
                       ' Reason: Persistent Disk is linked by pods:.*'):
        pv1.delete(name=pv1_name)

    with assert_raises(NonZeroRetCodeException, 'Volume can not be deleted.'
                       ' Reason: Persistent Disk is linked by pods:.*'):
        pv2.delete(id=pv2_id)

    # Get disk info once again
    log_debug("Pod is stopped and 'in_use' should become 'False'", LOG)
    pv1_info = pv1.info()
    pv2_info = pv2.info()

    # Disk1 states: 'forbidDeletion': True, 'in_use': False
    # 'test_nginx_pv_states_via_kcli' should still be in 'disk1' linkedPods
    assert_pv_states(pv1_info,
                     expected_states=dict(forbidDeletion=True, in_use=False),
                     pod_names=[pod_name])
    # Disk2 states: 'forbidDeletion': True, 'in_use': False
    # 'test_nginx_pv_states_via_kcli' should still be in 'disk2' linkedPods
    assert_pv_states(pv2_info,
                     expected_states=dict(forbidDeletion=True, in_use=False),
                     pod_names=[pod_name])

    pod.delete()

    log_debug("Pod is deleted and both 'forbidDeletion' and 'in_use' should "
              "become 'False'", LOG)
    pv1_info = pv1.info()
    pv2_info = pv2.info()

    # Disk1 states: 'forbidDeletion': False, 'in_use': False
    assert_pv_states(pv1_info,
                     expected_states=dict(forbidDeletion=False, in_use=False),
                     pod_names=[])
    # Disk2 states: 'forbidDeletion': False, 'in_use': False
    assert_pv_states(pv2_info,
                     expected_states=dict(forbidDeletion=False, in_use=False),
                     pod_names=[])

    log_debug("Delete 'disk1' using '--name'", LOG)
    res = pv1.delete(name=pv1_name)
    assert_eq(res['status'], 'OK')

    log_debug("Delete 'disk2' using '--id'", LOG)
    res = pv2.delete(id=pv2_id)
    assert_eq(res['status'], 'OK')

    log_debug("Check that 'disk1' is deleted", LOG)
    with assert_raises(NonZeroRetCodeException, 'Error: Unknown name'):
        pv1.info()

    log_debug("Check that 'disk2' is deleted", LOG)
    with assert_raises(NonZeroRetCodeException, 'Error: Unknown name'):
        pv2.info()
