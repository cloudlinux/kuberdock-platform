#!/usr/bin/env bash
set -e

if [ ! -d "dev-utils" ]
then
    echo "Must be run from AppCloud dir, like:"
    echo "./dev-utils/build-all-in-docker.sh"
    exit 1
fi

./dev-utils/build-rpm-in-docker.sh
./dev-utils/build-kdctl-rpm-in-docker.sh
./dev-utils/build-kdcli-rpm-in-docker.sh
