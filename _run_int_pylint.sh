#!/usr/bin/env bash
#
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.
#
ERRORS_THRESHOLD=200

tmpfile=$(mktemp /tmp/int-pylint-parse.XXXXXX)
pylint --ignore-patterns=tests_integration/lib/vendor --rcfile=tests_integration/.pylintrc \
    run_integration_tests.py \
    $(find tests_integration/ -maxdepth 1 -name "*.py" -print) \
    $(find tests_integration/tests_* -maxdepth 1 -name "*.py" -print) \
    $(find tests_integration/lib -maxdepth 1 -name "*.py" -print) | tee $tmpfile

errors_count=$(egrep '\[(E|W|R|C)[0-9]{4,4}' $tmpfile | wc -l)
echo "####################### PyLint results ############################"
echo "Found PyLint errors   : ${errors_count}"
echo "PyLint errors threshold: ${ERRORS_THRESHOLD}"
exit `[[ $errors_count -le $ERRORS_THRESHOLD ]]`
