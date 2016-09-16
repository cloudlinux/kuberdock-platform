#!/usr/bin/env bash
set -e

IMG=lobur/rpm-build:v1

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
    bash dev-utils/build-rpm.sh "$workdir" "/"
docker cp "$CONT":/kuberdock.rpm "$DST"
docker rm -f "$CONT"
