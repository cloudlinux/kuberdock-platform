#!/usr/bin/env bash
build_number=${BUILD_NUMBER:-local}
project="appcloudunittest${build_number}"
compose="docker-compose -f unittest-compose.yml -p ${project}"

$compose run --rm appcloud /bin/bash -c \
"echo 'Sleep 30 sec - wait other services. FIXME in AC-3267';
 sleep 30;
 echo '###################### Setup requirements ######################';
 source /venv/bin/activate;
 pip install -r requirements.txt -r requirements-dev.txt;
 echo '######################## Run unit tests ########################';
 nosetests -v kubedock kuberdock-cli"
ret=$?

$compose down --rmi local -v
exit $ret
