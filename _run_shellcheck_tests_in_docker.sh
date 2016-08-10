#!/usr/bin/env bash

build_number=${BUILD_NUMBER:-local_$(echo $RANDOM | tr '[0-9]' '[a-zA-Z]')}
project="appcloudunittest${build_number}"

image="tyzhnenko/shellcheck:v1"

docker run --rm \
    -v `pwd`:/AppCloud -w /AppCloud \
    --name "$project" $image ./_run_shellcheck_tests.sh
ret=$?
exit $ret
