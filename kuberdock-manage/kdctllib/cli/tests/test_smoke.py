
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

import importlib
import json
import os
import re
import sys
from functools import partial

import pytest
import pytest_mock
import responses
from click.testing import CliRunner

from ..utils import file_utils

THIS_DIR = os.path.dirname(__file__)

SOME_JSON = '{"hello": "world"}'
SOME_JSON_FILE = file_utils.resolve_path('hello.json', THIS_DIR)

RESPONSE_BODY = json.dumps({
    'data': None,
    'status': 'ok'
})


def _read_commands(file_name):
    file_name = file_utils.resolve_path(file_name, THIS_DIR)
    d = {'some_json': SOME_JSON, 'some_json_file': SOME_JSON_FILE}
    rv = []

    with open(file_name) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                command = [c.format(**d) for c in re.split('\s+', line)]
                rv.append(command)

    return rv


def _unload_cli_modules():
    for m in sys.modules.keys():
        if m.startswith('kdctllib.cli'):
            del sys.modules[m]
    importlib.import_module('kdctllib.cli')


@pytest.fixture(scope='class')
def mocker():
    result = pytest_mock.MockFixture()
    yield result
    result.stopall()


@pytest.fixture(scope='class')
def mock_all(mocker):
    all_urls = re.compile('.*')

    with responses.RequestsMock(assert_all_requests_are_fired=False) as r:
        methods = (r.GET, r.POST, r.PUT, r.DELETE)
        for m in methods:
            r.add(m, all_urls, body=RESPONSE_BODY)

        mocker.patch('kdctllib.cli.utils.misc.get_id_by_name',
                     return_value='some_id')
        yield


@pytest.fixture(scope='class')
def kdctl_init():
    """It must be called before any other fixtures"""
    _unload_cli_modules()
    from .. import access, settings, initialize
    initialize(access.ADMIN, settings.KDCtlSettings)


@pytest.fixture(scope='class')
def kcli2_init():
    """It must be called before any other fixtures"""
    _unload_cli_modules()
    from .. import access, settings, initialize
    initialize(access.USER, settings.KCliSettings)


@pytest.fixture(scope='class')
def cli(tmpdir_factory):
    conf_dir = str(tmpdir_factory.mktemp(''))
    from .. import main
    main.settings.working_directory = conf_dir
    yield main.main


@pytest.fixture(scope='class')
def runner():
    return CliRunner()


@pytest.fixture(scope='class')
def invoke(runner, cli, mock_all):
    return partial(runner.invoke, cli, catch_exceptions=False)


@pytest.fixture(scope='class')
def login(invoke):
    with responses.RequestsMock() as r:
        r.add(r.GET, re.compile(r'.*/token\??.*'),
              body='{"token": "some_token", "status": "ok"}')
        invoke(['login', '-u', 'u', '-p', 'p'])


@pytest.mark.usefixtures('login')
@pytest.mark.usefixtures('kdctl_init')
class TestKDCtl:
    @pytest.mark.parametrize('command', _read_commands('kdctl.txt'))
    def test_smoke(self, command, invoke):
        result = invoke(command)

        print result.output
        assert result.exit_code == 0


@pytest.mark.usefixtures('login')
@pytest.mark.usefixtures('kcli2_init')
class TestKCli2:
    @pytest.mark.parametrize('command', _read_commands('kcli2.txt'))
    def test_smoke(self, command, invoke):
        result = invoke(command)

        print result.output
        assert result.exit_code == 0
