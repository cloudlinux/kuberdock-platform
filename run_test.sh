#!/bin/bash
set -x

FLAKE8="flake8"
PEP8="pep8"
TOXENV=${TOXENV:-py27}
USER_ID=$(id -u)
TRESHOLD_ERRORS=953

# Flags for logic manipulation
flake8_checks=0
integration_tests=0
kuberdock_tests=0
docker_run_tests=0
docker_not_wipe=0
testropts=
testrargs=

function usage {
  echo "Usage: $0 [OPTION]..."
  echo "Run KuberDock test suite(s)"
  echo ""
  echo "  -h, --help                  Print this usage message"
  echo "  -i, --integration           Run integration test"
  echo "  -p, --flake8                Run FLAKE8(PEP8) compliance check"
  echo "  -t, --tests                 Run unittest"
  echo "  -d, --docker                Run tests by Docker-Compose"
  echo "  -n, --no-wipe               Won't wipe containeres after run"
  echo ""
  echo "Note: with no options specified, the script will run unittest only."
  exit
}

function argparse {
  for arg in $@; do
    case "$arg" in
      -h|--help) usage;;
      -i|--integration) integration_tests=1;;
      -p|--flake8) flake8_checks=1;;
      -t|--tests) kuberdock_tests=1;;
      -d|--docker) docker_run_tests=1;;
      -n|--not-wipe) docker_not_wipe=1;;
      -*) testropts="$testopts $arg";;
      *) testrargs="$testargs $arg"
    esac
  done
}

function run_clean {
  find . -type f -name "*.pyc" -delete
}

function run_unittest {
  tox -epy27 || ret=1
  return ret
}

function run_tests_in_docker {
  local suffix=${1:-local}
  local kuberdock="${PWD}/kubedock"
  local project="appcloud${suffix}"
  local compose="docker-compose -f ${kuberdock}/testutils/run_test-compose.yml -p ${project}"
  local container="${project}_appcloud_1"

  # Mock settings to run inside container
  # cat ${kuberdock}/testutils/kuberdock-settings-for-test.py >> ${kuberdock}/settings.py

  # $compose up --build -d
  # $compose logs -f appcloud
  # EXIT_CODE=$(docker wait ${container})
  $compose build
  echo "################################################"
  echo "################################################"
  echo "################################################"
  $compose run appcloud /bin/bash -c \
    "echo 'Sleep 30 sec, need wait to up other services';
     sleep 30;
     echo 'Add unitest user with uid $USER_ID'; \
     useradd unittest -m -u $USER_ID && \
     echo 'Run unittest'; \
     su unittest -c 'tox $testopts $testargs'" && ret=0 || ret=1
  if [[ $docker_not_wipe -eq 0 ]]; then
    $compose down
  fi
  echo "################################################"
  echo "################################################"
  echo "################################################"
  return $ret
  # return $EXIT_CODE
}

function run_flake8 {
  ret=1
  local treshold_errors=${1:-0}
  tox -epep8 | tee flake8.log
  local errors_count=$(egrep ': (E|W|F|C)[0-9]{3,3} ' flake8.log | wc -l)

  if [[ $errors_count -le $treshold_errors ]]; then
    echo "#############################################"
    echo "Found ${errors_count} errors but it is equal or less then ${treshold_errors}"
    ret=0
  else
    echo "#############################################"
    echo "Found ${errors_count} errors and it is more then ${treshold_errors}"
    ret=1
  fi

  return $ret
}

function run_integration {
  tox -eint || ret=1 && ret=0
  return $ret
}

function run_test {
  run_clean
  local errors=""


  # Default behavior.
  if [[ $kuberdock_tests -eq 0 &&
        $flake8_checks -eq 0 &&
        $docker_run_tests -eq 0 &&
        $integration_tests -eq 0 ]]; then
    kuberdock_tests=1
  fi

  if [[ $flake8_checks -eq 1 ]]; then
    run_flake8 $TRESHOLD_ERRORS || errors+=" flake8_checks"
  fi

  if [[ $kuberdock_tests -eq 1 &&
        $docker_run_tests -eq 0 ]]; then
    run_unittest || errors+=" kuberdock_tests"
  fi

  if [[ $docker_run_tests -eq 1 &&
        $kuberdock_tests -eq 0 ]]; then
    run_tests_in_docker ${BUILD_NUMBER} || errors+=" docker_run_tests"
  fi

  if [[ $integration_tests -eq 1 ]]; then
    run_integration || errors+=" integration_tests"
  fi

  if [ -n "$errors" ]; then
    echo Failed tests: $errors
    exit 1
  fi

  exit
}

argparse $@
run_test
