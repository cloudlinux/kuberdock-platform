
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

import time

import logging
from contextlib import contextmanager
from functools import wraps

LOG = logging.getLogger(__name__)


# Copied from integration_test_utils due to cyclic import
def get_func_fqn(f):
    if hasattr(f, "im_class"):
        # func defined in a class
        return ".".join([f.im_class, f.__name__])
    # func defined in a module
    return ".".join([f.__module__, f.__name__])


def log_timing(func):
    """Decorator that logs how much time (Xm Ys) a func call takes."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            res = func(*args, **kwargs)
        finally:
            _log_elapsed(
                get_func_fqn(func),
                _calc_elapsed(start_time)
            )
        return res
    return wrapper


@contextmanager
def log_timing_ctx(op_name):
    """Context mgr that logs how much time the operation inside takes.

    Example:
        with log_timing_ctx("Operation 1"):
            # Operation 1.1
            # Operation 1.2
    """
    start_time = time.time()
    try:
        yield
    finally:
        elapsed = _calc_elapsed(start_time)
        _log_elapsed(op_name, elapsed)


@contextmanager
def timing_ctx():
    """Context mgr that returns ElapsedTime object with time that the operation
    inside takes.

    Example:
        with timing_ctx() as el:
            # Operation 1.1
            # Operation 1.2
        LOG.debug("Elapsed {}".format(el.str))
        result_times.add(el.int)
    """

    start_time = time.time()
    elapsed = ElapsedTime()
    try:
        yield elapsed
    finally:
        elapsed.value = int(time.time() - start_time)


def stopwatch():
    """Generator that used to measure time elapsed before the 1st 'next' call.

    Example:
        sw = stopwatch()
        # Operation 1
        # Operation 2
        all_ops_time = next(sw)
        LOG.debug("All ops time {}".format(all_ops_time.str))
    """

    def _sw():
        start_time = time.time()
        yield
        yield _calc_elapsed(start_time)
    sw = _sw()
    next(sw)
    return sw


class ElapsedTime(object):
    def __init__(self, value=None):
        self.value = value

    @property
    def int(self):
        return self.value

    @property
    def str(self):
        return _time_str(self.value)

    def __str__(self):
        return self.str

    def __repr__(self):
        return self.str


def _calc_elapsed(start_time):
    return ElapsedTime(int(time.time() - start_time))


def _log_elapsed(op_name, elapsed_time):
    LOG.debug(" {0} {1} took {2} {0}".format(
        5*"*", op_name, elapsed_time.str
    ))


def _time_str(t):
    mins = t // 60
    sec = t - (mins * 60)
    return "{}m {}s".format(mins, sec)
