from flask import current_app
from datetime import datetime
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from ..core import db, ConnectionPool
from ..pods.models import Pod
from ..usage.models import PodState, ContainerState
from ..utils import atomic


def select_pod_states_history(pod_id, depth=0):
    """Selects pod start-stop history, with host names where the pod was
    started. Entries will be ordered by start_time in descending order - from
    last to first.
    :param depth: number of history entries to retrieve. If it is None or zero,
    then will be returned all history of the pod.
    :return: list of dicts, each dict contains fields:
        'hostname' name of node where the pod had run
        'start_time' first time of pod start at this node
        'end_time' time when pod was 'deleted'
    """
    query = PodState.query.filter(
        PodState.pod_id == pod_id,
    ).order_by(PodState.start_time.desc())
    if depth:
        query = query.limit(depth)
    return [item.to_dict() for item in query]


@atomic(nested=False)
def update_states(pod_id, k8s_pod_status, event_type=None, host=None, event_time=None):
    """Update and fix container and pod states using data from k8s pod resource.
    Works well even if `k8s_pod_status`es are processed in a wrong order.

    :param pod_id: id of the container's pod
    :param k8s_pod_status: k8s Pod.status
    :param event_type: k8s event type or None
    :param host: optional, node hostname (will be saved in PodState)
    :param event_time: optional, used as the best version of "current" time
    :returns: set of updated/created ContainerState
    """
    updated_CS = set()
    event_time = event_time or datetime.utcnow().replace(microsecond=0)
    pod_start_time = k8s_pod_status.get('startTime')
    if pod_start_time is None:
        return updated_CS
    needs_heavy_timeline_fix = False
    deleted = event_type == 'DELETED'

    # get or create pod state
    pod_state = PodState.query.filter(PodState.start_time == pod_start_time,
                                      PodState.pod_id == pod_id).first()
    if pod_state is None:
        current_app.logger.debug('create PS: {0} {1}'.format(pod_id, host,
                                                             pod_start_time))
        pod_state = PodState(pod_id=pod_id, hostname=host, start_time=pod_start_time)
        db.session.add(pod_state)
    if event_type is not None and (pod_state.last_event_time is None or
                                   event_time >= pod_state.last_event_time):
        pod_state.last_event = event_type
        pod_state.last_event_time = event_time

    # get data from our db
    pod = Pod.query.get(pod_id)
    containers_config = {container.get('name'): container
                         for container in pod.get_dbconfig('containers', [])}

    # process container states
    for container in (k8s_pod_status.get('containerStatuses') or []):
        if 'containerID' not in container:
            continue
        container_name = container['name']
        kubes = containers_config.get(container_name).get('kubes', 1)

        # k8s fires "MODIFIED" pod event when docker_id of container changes.
        # (container restart in the same pod)
        # k8s provides us last state of previous docker container and the
        # current state of a new one.
        for state_type, state in (container['lastState'].items() +
                                  container['state'].items()):
            if state_type == 'terminated':
                # Terminated state may optionally include containerID. It means
                # previous container in running state. There are some issues
                # about wrong assignment of terminated state:
                # https://github.com/kubernetes/kubernetes/issues/17971
                # https://github.com/kubernetes/kubernetes/issues/21125
                docker_id_source = state
            else:
                docker_id_source = container
            if 'containerID' not in docker_id_source:
                # Do not process states with empty container id. The field is
                # optional. We can't process such states.
                continue
            docker_id = docker_id_source['containerID'].split('docker://')[-1]

            start = state.get('startedAt')
            if start is None:
                continue

            # get or create CS
            cs = ContainerState.query.filter(
                ContainerState.container_name == container_name,
                ContainerState.docker_id == docker_id,
                ContainerState.kubes == kubes,
                ContainerState.start_time == start,
            ).first()
            if cs is None:
                cs = ContainerState(
                    pod_state=pod_state,
                    container_name=container_name,
                    docker_id=docker_id,
                    kubes=kubes,
                    start_time=start,
                )
                db.session.add(cs)
            updated_CS.add(cs)

            # reset CS if it was marked as missing
            if ((state_type == 'terminated' or deleted) and
                    (cs.exit_code, cs.reason) == ContainerState.REASONS.missed):
                cs.end_time, cs.exit_code, cs.reason = None, None, None

            # get end_time
            cs.end_time = state.get('finishedAt') or cs.end_time
            if cs.end_time is None and (state_type == 'terminated' or deleted):
                cs.end_time = event_time

            # extend pod state so all container states fit in
            # pod_state.start_time = min(pod_state.start_time, start)
            if deleted and (pod_state.end_time is None or
                            pod_state.end_time < cs.end_time):
                pod_state.end_time = cs.end_time

            # get exit_code and reason
            if state_type == 'terminated':
                cs.exit_code = state.get('exitCode')
                reason, message = state.get('reason'), state.get('message')
                if reason and message:
                    cs.reason = u'{0}: {1}'.format(reason, message)
                elif reason or message:
                    cs.reason = reason or message
                # fix k8s 1.1.3 issue: succeeded containers have reason=Error
                if cs.exit_code == 0 and cs.reason == 'Error':
                    cs.reason = None
            elif deleted and cs.exit_code is None:
                cs.exit_code, cs.reason = ContainerState.REASONS.pod_was_stopped

            # fix overlaping
            try:
                prev_cs = ContainerState.query.join(PodState).filter(
                    PodState.pod_id == pod_id,
                    ContainerState.container_name == container_name,
                    ContainerState.start_time < start,
                    db.or_(ContainerState.end_time > start,
                           ContainerState.end_time.is_(None)),
                ).one()
            except MultipleResultsFound:
                needs_heavy_timeline_fix = True
            except NoResultFound:
                pass
            else:
                prev_cs.fix_overlap(start)
                updated_CS.add(prev_cs)
    prev_ps = PodState.query.filter(PodState.pod_id == pod_id,
                                    PodState.start_time < pod_state.start_time,
                                    db.or_(PodState.end_time > pod_state.start_time,
                                           PodState.end_time.is_(None))).first()
    if prev_ps:
        PodState.close_other_pod_states(pod_id, pod_state.start_time, commit=False)

    if deleted and (pod_state.end_time is None or
                    k8s_pod_status.get('phase') == 'Failed'):
        pod_state.end_time = event_time

    if needs_heavy_timeline_fix:
        updated_CS.update(fix_pods_timeline_heavy())

    return updated_CS


def fix_pods_timeline_heavy():
    """
    Fix time lines overlapping
    This task should not be performed during normal operation
    :returns: set of updated ContainerStates
    """
    updated_CS = set()
    redis = ConnectionPool.get_connection()

    if redis.get('fix_pods_timeline_heavy'):
        return updated_CS

    redis.setex('fix_pods_timeline_heavy', 3600, 'true')

    # t0 = datetime.now()

    cs1 = db.aliased(ContainerState, name='cs1')
    ps1 = db.aliased(PodState, name='ps1')
    cs2 = db.session.query(ContainerState, PodState.pod_id).join(PodState).subquery()
    cs_query = db.session.query(cs1, cs2.c.start_time).join(
        ps1, ps1.id == cs1.pod_state_id
    ).join(
        cs2, db.and_(ps1.pod_id == cs2.c.pod_id,
                     cs1.container_name == cs2.c.container_name)
    ).filter(
        cs1.start_time < cs2.c.start_time,
        db.or_(cs1.end_time > cs2.c.start_time,
               cs1.end_time.is_(None))
    ).order_by(
        ps1.pod_id, cs1.container_name, db.desc(cs1.start_time), cs2.c.start_time
    )

    prev_cs = None
    for cs1_obj, cs2_start_time in cs_query:
        if cs1_obj is not prev_cs:
            cs1_obj.fix_overlap(cs2_start_time)
            updated_CS.add(cs1_obj)
        prev_cs = cs1_obj

    # print('fix_pods_timeline_heavy: {0}'.format(datetime.now() - t0))

    redis.delete('fix_pods_timeline_heavy')
    return updated_CS
