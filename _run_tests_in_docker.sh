#!/usr/bin/env bash
build_number=${BUILD_NUMBER:-local}
project="appcloudunittest${build_number}"
compose="docker-compose -f unittest-compose.yml -p ${project}"

$compose run --rm appcloud /bin/bash -c \
"set -e;
 echo 'Waiting for postgres 5432 port';
 timeout 30 bash -c 'until nmap --open -p5432 postgres | grep open; do echo \"Waiting..\"; sleep 1; done;'
 echo '###################### Setup requirements ######################';
 source /venv/bin/activate;
 pip install -r requirements.txt -r requirements-dev.txt;
 echo '######################## Run unit tests ########################';
 nosetests -v kubedock kuberdock-cli"
ret=$?

$compose down --rmi local -v
exit $ret
