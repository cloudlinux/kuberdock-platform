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