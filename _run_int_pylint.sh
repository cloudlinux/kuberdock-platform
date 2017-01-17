#!/usr/bin/env bash
ERRORS_THRESHOLD=250

tmpfile=$(mktemp /tmp/int-pylint-parse.XXXXXX)
pylint  --rcfile=tests_integration/.pylintrc run_integration_tests.py $(find tests_integration/ -name "*.py" -print) | tee $tmpfile

errors_count=$(egrep '\[(E|W|R|C)[0-9]{4,4}' $tmpfile | wc -l)
echo "####################### PyLint results ############################"
echo "Found PyLint errors   : ${errors_count}"
echo "PyLint errors threshold: ${ERRORS_THRESHOLD}"
exit `[[ $errors_count -le $ERRORS_THRESHOLD ]]`
