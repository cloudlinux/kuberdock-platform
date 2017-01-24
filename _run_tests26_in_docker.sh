#!/usr/bin/env bash
IMAGE='lobur/centos6-test-base:v2'

docker run -v $(pwd):/appcloud:ro -w /appcloud $IMAGE /bin/bash -c \
"set -e;
 echo '###################### Setup requirements ######################';
 source /venv/bin/activate;
 pip install -r requirements-dev.txt;
 echo '######################## Run unit tests ########################';
 py.test -p no:cacheprovider -v \
    kuberdock-cli"
ret=$?
# TODO AC-4879: add kuberdock-manage to py.test above

exit $ret
