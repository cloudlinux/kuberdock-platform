from flask import current_app
import datetime
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from ..core import db
from ..usage.models import PodState, ContainerState
from ..tasks import fix_pods_timeline_heavy

DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


def save_pod_state(pod_id, event_type, host):
    PodState.save_state(pod_id, event_type, host)


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


def update_containers_state(pod_id, containers, deleted=False):
    """Update and fix container states using data from k8s pod event.

    :param pod_id: id of the container's pod
    :param containers: k8s Pod.status.containerStatuses
    """
    pod_state = None
    for container in containers:
        if 'containerID' not in container:
            continue
        container_name = container['name']
        kubes = container.get('kubes', 1)  # FIXME: kubes in k8s???

        # k8s fires "MODIFIED" pod event when docker_id of container changes.
        # k8s provides us last state of previous docker container and the
        # current state of a new one.

        # if we will read only "state", we may miss the moment when container
        # terminates; if we will read only "lastState", we definitely will miss
        # the moment when container starts... so, read both
        for state_type, state in (container['lastState'].items() +
                                  container['state'].items()):
            docker_id_source = (state if state_type == 'terminated' else container)
            docker_id = docker_id_source['containerID'].split('docker://')[-1]

            start = state.get('startedAt')
            if start is None:
                continue
            start = datetime.datetime.strptime(start, DATETIME_FORMAT)
            cs = ContainerState.query.filter(
                ContainerState.container_name == container_name,
                ContainerState.docker_id == docker_id,
                ContainerState.kubes == kubes,
                ContainerState.start_time == start,
            ).first()
            end = state.get('finishedAt')
            if end is not None:
                end = datetime.datetime.strptime(end, DATETIME_FORMAT)
            elif state_type == 'terminated' or deleted:
                end = datetime.datetime.utcnow().replace(microsecond=0)
            if cs:
                cs.end_time = end
            else:
                pod_state = pod_state or PodState.query.filter(
                    PodState.pod_id == pod_id,
                    PodState.start_time <= start,
                ).order_by(PodState.start_time.desc()).first()
                if pod_state is None:
                    current_app.logger.warn('PodState for {0} not found'.format(pod_id))
                    continue

                cs = ContainerState(
                    pod_state=pod_state,
                    container_name=container_name,
                    docker_id=docker_id,
                    kubes=kubes,
                    start_time=start,
                    end_time=end,
                )
                db.session.add(cs)
            if state_type == 'terminated':
                cs.exit_code = state.get('exitCode')
                reason, message = state.get('reason'), state.get('message')
                if reason and message:
                    cs.reason = u'{0}: {1}'.format(reason, message)
                elif reason or message:
                    cs.reason = reason or message
            elif deleted and cs.exit_code is None:
                cs.exit_code = 0
                cs.reason = u'Pod was stopped.'

            # fix overlaping
            try:
                prev_cs = ContainerState.query.filter(
                    ContainerState.pod_state.has(pod_id=pod_id),
                    ContainerState.container_name == container_name,
                    ContainerState.start_time < start,
                    db.or_(ContainerState.end_time > start,
                           ContainerState.end_time.is_(None)),
                ).one()
            except MultipleResultsFound:
                fix_pods_timeline_heavy.delay()
            except NoResultFound:
                pass
            else:
                prev_cs.fix_overlap(start)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
