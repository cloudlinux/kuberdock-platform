from ..usage.models import PodState

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
