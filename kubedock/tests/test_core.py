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
