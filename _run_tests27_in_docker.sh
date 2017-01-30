#!/usr/bin/env bash
#
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
#
build_number=${BUILD_NUMBER:-local_$(echo $RANDOM | tr '[0-9]' '[a-zA-Z]')}
project="appcloudunittest${build_number}"
compose="docker-compose -f tests27-compose.yml -p ${project}"

$compose build
$compose run --rm appcloud /bin/bash -c \
"set -e;
 echo 'Waiting for postgres 5432 port';
 timeout 30 bash -c 'until nmap --open -p5432 postgres | grep open; do echo \"Waiting..\"; sleep 1; done;'
 echo '###################### Setup requirements ######################';
 source /venv/bin/activate;
 pip install -r requirements.txt -r requirements-dev.txt;
 echo '######################## Run unit tests ########################';
 py.test -v \
    --cov-config .coveragerc \
    --cov-report xml:/artifacts/cov.xml \
    --cov-report html:/artifacts/htmlcov \
    --cov-report term \
    --cov=kubedock \
    --cov=kuberdock-cli \
    --cov=kuberdock-manage \
    kubedock kuberdock-cli kuberdock-manage node_storage_manage"
ret=$?

$compose down --rmi local -v
exit $ret
