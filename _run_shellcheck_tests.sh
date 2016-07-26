#!/usr/bin/env bash
ERRORS_TRESHOLD=929


tmpfile=$(mktemp /tmp/shellcheck-parse.XXXXXX)
find -iname '*.sh' | xargs shellcheck -s bash | tee $tmpfile

errors_count=$(egrep -- '-- SC' $tmpfile | wc -l)
echo "####################### Shellcheck results ############################"
echo "Found Shell errors   : ${errors_count}"
echo "Shell errors treshold: ${ERRORS_TRESHOLD}"
exit `[[ $errors_count -le $ERRORS_TRESHOLD ]]`
