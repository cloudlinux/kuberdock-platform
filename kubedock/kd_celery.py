"""Creates an instance of celery application to use it in different modules.
"""
import functools
import time

from flask import current_app
from .factory import make_celery
from .core import ExclusiveLock

celery = make_celery()


def exclusive_task(timeout, task_id=None, blocking=False):
    """Exclusive celery task decorator based on redis locks.
    The decorator adds possibility to define mutually exclusive celery task.
    'Exclusive' means there may be only one task with the same name in running
    state at any moment.
    Task name will be taken from decorated function name. If there are several
    different tasks in different modules with the same names, then specify
    explicit `task_id` - any unique string identifier.
    :param timeout: time in seconds to wait task finish before starting a new
      one with the same name. If `timeout` will be expired, but the task still
      in progress, then new one will be started on schedule. So set the timeout
      high enough, to prevent undesired tasks overlapping.
    :param task_id: optional unique string task identifier. Use it when you
      have different celery tasks with the same function name.
    :param blocking: optional flag specifying whether lock should be blocking
      or not

    Usage example:

        from kubedock.kd_celery import celery, exclusive_task

        @celery.task()
        @exclusive_task(10 * 60)  # 10 minutes timeout
        def some_task(a, b, c):
            do_the_stuff()
            ...

    In this example the call of some_task.delay() will actually silently return
    if there is already running 'some_task'. Also works for scheduled jobs.
    Also will work for synchronous task run - some_task().

    """
    def wrap(wrapped):
        @functools.wraps(wrapped)
        def wrapper(*args, **kwargs):
            task_name = task_id or wrapped.__name__
            lock_id = "celery-exclusive-" + task_name
            current_app.logger.debug('Locking task %s', lock_id)
            lock = ExclusiveLock(lock_id, timeout)
            res = None
            if lock.lock(blocking=blocking):
                try:
                    start_time = time.time()
                    current_app.logger.debug(
                        'Starting exclusive task %s', task_name
                    )
                    res = wrapped(*args, **kwargs)
                finally:
                    execution_time = time.time() - start_time
                    if not timeout or (execution_time < timeout):
                        # Don't release the lock after timeout had expired,
                        # because it will be released automatically
                        current_app.logger.debug('Releasing lock %s', lock_id)
                        lock.release()
                    current_app.logger.debug(
                        'Exclusive task %s finished. Execution time: %s',
                        task_name, execution_time
                    )
            else:
                current_app.logger.debug(
                    'Celery task %s is already running.', task_name
                )
            return res
        return wrapper
    return wrap
