#!/usr/bin/env bash
build_number=${BUILD_NUMBER:-local}
project="appcloudunittest${build_number}"
compose="docker-compose -f unittest-compose.yml -p ${project}"

#$compose build
echo "##################### Running unit tests ###########################"
$compose run --rm appcloud /bin/bash -c \
"echo 'Sleep 30 sec - wait other services. FIXME in AC-3267';
 sleep 30;
 echo 'Run unit tests';
 tox -epy27"
ret=$?
echo "##################### Finished unit tests ###########################"
$compose down --rmi local -v
exit $ret
