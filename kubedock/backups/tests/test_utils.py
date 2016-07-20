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
