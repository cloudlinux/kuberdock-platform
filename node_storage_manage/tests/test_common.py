
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
