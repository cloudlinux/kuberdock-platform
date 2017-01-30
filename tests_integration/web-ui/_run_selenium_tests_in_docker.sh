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
build_number=${BUILD_NUMBER:-local_$(echo $RANDOM | tr '0-9' 'a-zA-Z')}
project="appcloudunittest${build_number}"
compose="docker-compose -f selenium-compose.yml -p ${project}"
args=${ROBOT_ARGS:-$*}

rm -r ./report  # remove old report

$compose build
$compose run --name "$project" appcloud-web-ui-tests /bin/bash -c "
set -e;
  echo 'Waiting for selenium-hub and nodes';
  timeout 30 bash -c 'until [ \$(curl -s http://selenium-hub:4444/grid/console | grep -c proxyid) == 3 ]; do echo \"Waiting..\"; sleep 1; done;'
  echo '######################## Run UI tests ########################';
  IP=\$(getent hosts selenium-hub | awk '{print \$1}')
  R_CMD=\"robot -v TEST_ENV:docker -v SELENIUM_HUB_IP:\$IP -P /tests --outputdir /report $args\"
  echo \$R_CMD
  \$R_CMD
"
ret=$?

docker cp "$project":/report ./
docker rm "$project"
$compose down --rmi local -v
exit $ret
