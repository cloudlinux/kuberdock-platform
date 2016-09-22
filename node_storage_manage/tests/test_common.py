"""Unittests for node_storage_manage.common"""

import os
import unittest
import tempfile
import shutil

from .. import common


class TestCommonFuncs(unittest.TestCase):

    def test_volume_can_be_resized_to(self):
        path = tempfile.mkdtemp()
        try:
            new_size = 1024 ** 2
            # size of the path now is 0
            ok, err_message = common.volume_can_be_resized_to(path, new_size)
            self.assertTrue(ok)
            self.assertIsNone(err_message)

            # create a file with size equal to new size
            big_file = os.path.join(path, 'test1')
            with open(big_file, 'wb') as fout:
                fout.write('0' * new_size)
            ok, err_message = common.volume_can_be_resized_to(path, new_size)
            self.assertFalse(ok)
            self.assertTrue(isinstance(err_message, basestring))

            # Should also returns error for not existing path
            unknown_path = os.path.join(path, 'qwerty')
            ok, err_message = common.volume_can_be_resized_to(
                unknown_path, new_size)
            self.assertFalse(ok)
            self.assertTrue(isinstance(err_message, basestring))

            # remove first file and check again
            os.remove(big_file)
            ok, err_message = common.volume_can_be_resized_to(path, new_size)
            self.assertTrue(ok)
            self.assertIsNone(err_message)
        finally:
            shutil.rmtree(path)


if __name__ == '__main__':
    unittest.main()
