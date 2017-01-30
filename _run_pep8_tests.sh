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
ERRORS_THRESHOLD=180

tmpfile=$(mktemp /tmp/flake8-parse.XXXXXX)
flake8 kubedock kuberdock-cli | tee $tmpfile

errors_count=$(egrep ': (E|W|F|C)[0-9]{3,3} ' $tmpfile | wc -l)
echo "####################### PEP8 results ############################"
echo "Found PEP8 errors   : ${errors_count}"
echo "PEP8 errors threshold: ${ERRORS_THRESHOLD}"
exit `[[ $errors_count -le $ERRORS_THRESHOLD ]]`
