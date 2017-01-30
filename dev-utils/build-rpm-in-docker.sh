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
set -e

IMG=quay.io/sergey_gruntovsky/rpm-build:v6

if [ ! -d "dev-utils" ]
then
    echo "Must be run from AppCloud dir, like:"
    echo "./dev-utils/build-rpm-in-docker.sh"
    exit 1
fi

DST="./builds/"
CONT=rpm-build_$(echo $RANDOM | tr '[0-9]' '[a-zA-Z]')
workdir="/docker_rpmbuild"

docker run --name "$CONT" -v "$PWD":"$workdir":ro,z -w "$workdir" \
    -e JS_BUILD_MODE="$JS_BUILD_MODE" "$IMG" \
    bash dev-utils/build-rpm.sh "$workdir" "/"
docker cp "$CONT":/kuberdock.rpm "$DST"
docker rm -f "$CONT"
