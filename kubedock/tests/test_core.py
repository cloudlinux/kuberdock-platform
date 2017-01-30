
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

import unittest
import time

from kubedock.testutils.testcases import FlaskTestCase
from kubedock.testutils import create_app
from kubedock import core


class TestCase(FlaskTestCase):
    def create_app(self):
        return create_app(self)


class TestExclusiveLock(TestCase):
    """Test for core.ExclusiveLock class."""

    def setUp(self):
        self.saved_prefix = core.ExclusiveLock.lock_prefix
        core.ExclusiveLock.lock_prefix = 'kd.unittest.core.TestExclusiveLock.'

    def tearDown(self):
        core.ExclusiveLock.clean_locks()
        core.ExclusiveLock.lock_prefix = self.saved_prefix

    def test_lock_release(self):
        name = 'qwerty1234'
        lock1 = core.ExclusiveLock(name)
        self.assertTrue(lock1.lock())
        lock2 = core.ExclusiveLock(name)
        self.assertFalse(lock2.lock())

        lock1.release()
        lock2 = core.ExclusiveLock(name)
        self.assertTrue(lock2.lock())

        lock2.release()

        # test auto release
        lock = core.ExclusiveLock(name, 1)
        self.assertTrue(lock.lock())
        time.sleep(2)
        lock2 = core.ExclusiveLock(name)
        self.assertTrue(lock2.lock())
        lock2.release()

    def test_is_acquired(self):
        name = 'qwerty1234'
        lock1 = core.ExclusiveLock(name)
        self.assertTrue(lock1.lock())
        self.assertTrue(core.ExclusiveLock.is_acquired(name))
        self.assertFalse(core.ExclusiveLock.is_acquired(name + 'asdf'))

    def test_clean_locks(self):
        name1 = 'qwerty1234'
        name2 = 'qwerty1235'
        lock1 = core.ExclusiveLock(name1)
        lock2 = core.ExclusiveLock(name2)
        self.assertTrue(lock1.lock())
        self.assertTrue(lock2.lock())
        core.ExclusiveLock.clean_locks()
        lock3 = core.ExclusiveLock(name1)
        lock4 = core.ExclusiveLock(name2)
        self.assertTrue(lock3.lock())
        self.assertTrue(lock4.lock())


if __name__ == '__main__':
    unittest.main()
