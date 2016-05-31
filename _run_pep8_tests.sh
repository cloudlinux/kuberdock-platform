#!/usr/bin/env bash
ERRORS_TRESHOLD=982

tmpfile=$(mktemp /tmp/flake8-parse.XXXXXX)
flake8 kubedock kuberdock-cli | tee $tmpfile

errors_count=$(egrep ': (E|W|F|C)[0-9]{3,3} ' $tmpfile | wc -l)
echo "####################### PEP8 results ############################"
echo "Found PEP8 errors   : ${errors_count}"
echo "PEP8 errors treshold: ${ERRORS_TRESHOLD}"
exit `[[ $errors_count -le $ERRORS_TRESHOLD ]]`
