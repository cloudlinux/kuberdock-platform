
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

"""Simple script preparing and running JavaScript test with phantomjs"""

import os
import re
import subprocess
import sys

KUBERDOCK_DIR = '/var/opt/kuberdock'
RUNNER = 'phantomjs'
HARNESSER = 'mocha-phantomjs-core.js'
FRONTEND_RUNNER_PATH = 'kubedock/frontend/templates/tests/index.html'
CONSOLE_RUNNER_PATH = 'kubedock/frontend/test.html'     # temp file to run tests


def prepare():
    if os.path.exists(CONSOLE_RUNNER_PATH):
        os.unlink(CONSOLE_RUNNER_PATH)
    patt_s = r"\{\{\s*?url_for\('([^']+)',\s*?filename='([^']+)'\)\s*?\}\}"
    patt = re.compile(patt_s)
    with open(FRONTEND_RUNNER_PATH) as i:
        with open(CONSOLE_RUNNER_PATH, 'w') as o:
            for l in i:
                o.write(patt.sub(r"\1/\2", l))


def run():
    if os.getcwd() != KUBERDOCK_DIR:
        os.chdir(KUBERDOCK_DIR)
    prepare()
    process = subprocess.Popen(
        [RUNNER, HARNESSER, CONSOLE_RUNNER_PATH],
        stdout=subprocess.PIPE)
    for l in iter(process.stdout.readline, ''):
        sys.stdout.write(l)
    if os.path.exists(CONSOLE_RUNNER_PATH):
        os.unlink(CONSOLE_RUNNER_PATH)


if __name__ == '__main__':
    run()