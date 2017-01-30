
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

"""Methods for implementing locking on pod operations.
Every pod operation which may be affected by another such operation with
unpredictable results is locked so, we cant simultaneously run deleting a pod,
while there is performing redeploying of the same pod.

Every pod lock comes with operation name which acquired the lock and
optional celery task identifier to make it possible to interrupt the task.

"""
import time
from contextlib import contextmanager
from functools import wraps

import celery

from ..exceptions import PodIsLockedByAnotherOperation
from ..core import ExclusiveLock


class PodIsLockedError(Exception):
    """Internal exception for handling pod locks.
    """
    def __init__(self, pod_id='', operation=''):
        self.pod_id = pod_id
        self.operation = operation
        super(PodIsLockedError, self).__init__(
            'Pod "{}" is locked by opearation {}'.format(pod_id, operation)
        )


#: Default value for pod operations timeout (10 minutes, the number is not
# something proved, may be tuned further)
DEFAULT_POD_OPERATION_TIMEOUT = 60 * 10


class PodOperations(object):
    """Enum for possible pod operations which must be exclusive on one pod"""
    CREATE = 'create'
    PREPARE_FOR_START = 'prepare'
    START = 'start'
    STOP = 'stop'
    DELETE = 'delete'
    EDIT = 'edit'
    RESTART = 'restart'
    CHANGE_CONFIG = 'change config'
    REDEPLOY = 'redeploy'
    UNBIND_IP = 'unbind public IP'
    STOP_UNPAIND = 'stop unpaid pod'


def get_pod_lock(pod_id, operation, celery_task_id=None,
                 ttl=DEFAULT_POD_OPERATION_TIMEOUT,
                 retry_count=0, retry_pause=1, acquire_lock=True):
    """Tries to aquire exclusive lock for pod operations.
    :param pod_id: string identifier of a pod for which must be acquired a lock
    :param operation: name of operation (one of PodOperations) which requires
        a lock
    :param celery_task_id: optional celery task identifier to save in lock
        information
    :param ttl: timeout for a lock in seconds (lock will be released after
        this timeout)
    :param retry_count: number of tries to acquire a lock
    :param retry_pause: time interval between lock acquire tries.
    :param acquire_lock: boolean flag if set to False, then the method actually
        does nothing and returns None. It may be useful in client code, to
        prevent unneeded if/else branching.
    :return: object of  ExclusiveLock class if lock is acquired, None if lock
        should not be acquired. Raises PodIsLockedError in case of lock can't
        be acquired.
    """
    if not acquire_lock:
        return None
    lock_name = 'POD.{}'.format(pod_id)
    payload = {'operation': operation}
    if celery_task_id:
        payload['celery_task_id'] = celery_task_id
    lock = ExclusiveLock(lock_name, ttl, json_payload=payload)
    locked = False
    for _ in xrange(retry_count + 1):
        if lock.lock():
            locked = True
            break
        time.sleep(retry_pause)
    if not locked:
        payload = ExclusiveLock.get_payload(lock_name)
        operation = 'unknown'
        if payload:
            operation = payload.get('operation', 'unknown')
        raise PodIsLockedError(
            pod_id=pod_id,
            operation=operation,
        )
    return lock


@contextmanager
def pod_lock_context(pod_id, operation, celery_task_id=None,
                     ttl=DEFAULT_POD_OPERATION_TIMEOUT,
                     retry_count=0, retry_pause=1, acquire_lock=True):
    """Context for locking pod to exclusively use by one operation.
    If lock for the pod is already acquired, then raises
    PodIsLockedError.
    Lock will be automatically released on exit from context.
    Lock will be valid for some time (TTL).
    Actually it is a context wrapper for get_pod_lock function call.

    """
    lock = get_pod_lock(pod_id, operation, celery_task_id,
                        ttl, retry_count, retry_pause, acquire_lock)
    if not acquire_lock:
        yield lock
        return
    try:
        yield lock
    finally:
        lock.release()


def catch_locked_pod(func):
    """Decorator raises proper API errors in case of some Pod Lock exceptions.
    """
    @wraps(func)
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except PodIsLockedError as err:
            raise PodIsLockedByAnotherOperation(
                details=dict(
                    pod_id=err.pod_id,
                    operation=err.operation
                )
            )
    return wrapped


def _podlock_task_reinit(serialized_lock, celery_task):
    """Recreates lock object by given it's serialized data.
    Adds celery task information to lock's payload.
    It is useful when lock is passed to celery task, so that this celery task
        holding a lock and is responsible for it's releasing.

    :param serialized_lock: value which returned from
        ExclusiveLock.serialize method
    :param celery_task: celery task context
    :return: object of recreated ExclusiveLock object or None if serialized
        data is empty.
    """
    if not serialized_lock:
        return None
    podlock = ExclusiveLock(None, serialized=serialized_lock)
    if celery_task.request.id:
        podlock.update_payload(
            celery_task_id=celery_task.request.id
        )
    return podlock


def task_release_podlock(func):
    """Decorator for celery tasks which may be called with already acquired
    lock for a pod. With this decorator lock will be released on task finish.
    Also it will add celery task id to the lock payload.
    Decorated celery task must accept 'serialized_lock' parameter and must be
    declared with bind=True, to provide access to task's context.

    """
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        assert isinstance(self, celery.Task), \
            "Decorated celery task must be declared with bind=True"
        serialized_lock = kwargs.pop('serialized_lock', None)
        podlock = _podlock_task_reinit(serialized_lock, self)
        try:
            func(self, *args, **kwargs)
        finally:
            if podlock:
                podlock.release()
    return wrapped
