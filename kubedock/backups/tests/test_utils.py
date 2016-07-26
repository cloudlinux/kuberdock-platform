import unittest

from kubedock.backups import utils


class TestUrlJoin(unittest.TestCase):
    def test_all(self):
        test_cases = [
            # base, path, result
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
        for base, path, result in test_cases:
            actual = utils.join_url(base, path)
            print base, path, actual
            self.assertEqual(actual, result)
