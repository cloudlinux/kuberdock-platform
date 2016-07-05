#!/usr/bin/env bash

if [ ! -d "dev-utils" ]
then
    echo "Must be run from AppCloud dir, like:"
    echo "./dev-utils/build-rpm-in-docker.sh"
    exit 1
fi

DST=${KD_BUILD_DIR:-"./builds/"}

IMG=rpm-build_$(echo $RANDOM | tr '[0-9]' '[a-zA-Z]')
CONT=rpm-build_$(echo $RANDOM | tr '[0-9]' '[a-zA-Z]')

docker build -t $IMG -f dev-utils/Dockerfile.kd-rpm-build --rm=true --no-cache=true .
docker run --name $CONT $IMG bash dev-utils/build-rpm.sh
docker cp $CONT:/vagrant/kuberdock.rpm $DST
docker rm -f $CONT
docker rmi $IMG
