
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

import pytest

from kubedock.backups import utils


class TestUrlJoin(object):
    test_cases = [
        # base, path, expected
        ('http://example.com', '', 'http://example.com'),

        ('http://example.com/', '', 'http://example.com'),

        ('http://example.com', '/my/path', 'http://example.com/my/path'),

        ('http://example.com', 'my/path', 'http://example.com/my/path'),

        ('http://example.com/', '/my/path', 'http://example.com/my/path'),

        ('http://example.com/', 'my/path', 'http://example.com/my/path'),

        ('http://example.com/somewhere', '/my/path',
         'http://example.com/somewhere/my/path'),

        ('http://example.com/somewhere/', '/my/path',
         'http://example.com/somewhere/my/path'),

        ('http://example.com/somewhere', 'my/path',
         'http://example.com/somewhere/my/path'),

        ('http://example.com/somewhere/', 'my/path',
         'http://example.com/somewhere/my/path'),

        ('http://example.com/?user=user', '/my/path',
         'http://example.com/my/path?user=user'),

        ('http://example.com/?user=user&password=23', '/my/path?param=1',
         'http://example.com/my/path?user=user&password=23&param=1'),

        ('http://example.com/?user=user&password=23',
         '/my/path?user=kitty',
         'http://example.com/my/path?user=user&password=23&user=kitty'),
    ]

    @pytest.mark.parametrize('base, path, expected', test_cases)
    def test_all(self, base, path, expected):
        assert utils.join_url(base, path) == expected
