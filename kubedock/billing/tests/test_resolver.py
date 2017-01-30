
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

import mock
import unittest

from kubedock.billing.resolver import BillingFactory


class TestBillingFactory(unittest.TestCase):

    @mock.patch('kubedock.billing.resolver.os.listdir')
    @mock.patch('kubedock.billing.resolver.os.path.isdir')
    def test_get_plugins(self, _isdir, _list):
        """
        Tests that 'BillingFactory._get_billing_plugin' returns expected data
        with proper number of callables calls.
        """
        path = 'test_plugin_path'
        first, second = '---\nname: FIRST\n', '---\nname: SECOND\n'
        bf = BillingFactory(plugin_dir=path)

        _list.return_value = ['valid1.yml', 'invalid.txt', 'valid2.yaml']
        _isdir.return_value = True

        with mock.patch('kubedock.billing.resolver.open',
                        mock.mock_open(),
                        create=True) as _open:
            _open.return_value.read = mock.Mock(side_effect=[first, second])
            rv = bf._get_billing_plugins()
            _list.assert_called_once_with(path)
            _open.assert_has_calls([
                mock.call('/'.join([path, 'valid1.yml'])),
                mock.call().__enter__(),
                mock.call().read(),
                mock.call().__exit__(None, None, None),
                mock.call('/'.join([path, 'valid2.yaml'])),
                mock.call().__enter__(),
                mock.call().read(),
                mock.call().__exit__(None, None, None)
            ], "Number of 'open' calls differ from expected ones")
            self.assertTrue(sorted(rv.keys()) == ['FIRST', 'SECOND'],
                            "Found plugin names differ from expeced ones")
            self.assertTrue(rv.values() == [{}, {}],
                            "Found plugin data differ from expected ones")
