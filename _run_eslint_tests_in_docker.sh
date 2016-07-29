#!/usr/bin/env bash
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
