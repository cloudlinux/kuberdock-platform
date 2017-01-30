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

cp Dockerfile.eslint-test ./kubedock/frontend/static/
cd ./kubedock/frontend/static/
docker build -f Dockerfile.eslint-test -t "$project" .
docker run --rm "$project" node run-eslint.js
ret=$?
docker rmi "$project" >/dev/null
rm Dockerfile.eslint-test
exit $ret
