# coding=utf-8
import pytest

from ..io import IO


@pytest.fixture()
def io():
    return IO(json_only=False)


class TestUnicode(object):
    strings = [
        'Hello world',
        'Привет мир',
        u'Привет мир',
    ]

    @pytest.mark.parametrize('s', strings)
    def test_out_text(self, s, io):
        io.out_text(s)

    @pytest.mark.parametrize('s', strings)
    def test_out_json(self, s, io):
        io.out_json(s)
