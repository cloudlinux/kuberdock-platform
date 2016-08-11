#!/usr/bin/env bash
build_number=${BUILD_NUMBER:-local_$(echo $RANDOM | tr '[0-9]' '[a-zA-Z]')}
project="appcloudunittest${build_number}"
compose="docker-compose -f unittest-compose.yml -p ${project}"

$compose build
$compose run --rm appcloud /bin/bash -c \
"set -e;
 echo 'Waiting for postgres 5432 port';
 timeout 30 bash -c 'until nmap --open -p5432 postgres | grep open; do echo \"Waiting..\"; sleep 1; done;'
 echo '###################### Setup requirements ######################';
 source /venv/bin/activate;
 pip install -r requirements.txt -r requirements-dev.txt;
 echo '######################## Run unit tests ########################';
 py.test -v \
    --cov-config .coveragerc \
    --cov-report xml:/artifacts/cov.xml \
    --cov-report term \
    --cov=kubedock \
    --cov=kuberdock-cli \
    --cov=kuberdock-manage \
    kubedock kuberdock-cli"
ret=$?

$compose down --rmi local -v
exit $ret
