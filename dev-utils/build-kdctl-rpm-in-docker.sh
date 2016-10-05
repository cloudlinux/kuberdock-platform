#!/usr/bin/env bash
set -e

IMG=quay.io/sergey_gruntovsky/rpm-build:v5

if [ ! -d "dev-utils" ]
then
    echo "Must be run from AppCloud dir, like:"
    echo "./dev-utils/build-rpm-in-docker.sh"
    exit 1
fi

DST="./builds/"
CONT=rpm-build_$(echo $RANDOM | tr '[0-9]' '[a-zA-Z]')
workdir="/docker_rpmbuild"

docker run --name "$CONT" -v "$PWD":"$workdir":ro -w "$workdir" "$IMG" \
    bash dev-utils/build-kdctl-rpm.sh "$workdir/kuberdock-manage" "/"
docker cp "$CONT":/kdctl.rpm "$DST"
docker rm -f "$CONT"
