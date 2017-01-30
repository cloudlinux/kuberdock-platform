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
set -e

SOURCES_DIR=${1:-"./"}
DST=${2:-"./builds/"}

VERSION=$(grep "Version:" $SOURCES_DIR/kuberdock.spec | grep -oP "\d+\.\d+.*")
BUILD_VER=$(grep "Release:" $SOURCES_DIR/kuberdock.spec | sed -rn 's/.*: (.*)%\{\?dist\}(.*)/\1.el7\2/p' | tr -d '[:blank:]')
NAME=kuberdock
TMP_PATH="/tmp/$NAME-$VERSION"

NOW=$(pwd)
cd $SOURCES_DIR
if [ -n "$KD_GIT_REF" ]; then
    echo "########## Building KD RPM of '$KD_GIT_REF' version. Changes not in this version are ignored. ##########"
    git archive --format=tar --prefix=$NAME-$VERSION/ $KD_GIT_REF | bzip2 -9 > $TMP_PATH.tar.bz2
else
    echo "########## Building KD RPM from the current state of repo. All changes are included. ##########"
    rm -rf "$TMP_PATH"
    mkdir "$TMP_PATH"
    rsync -aP --quiet --exclude=".*" --exclude="dev-utils" --exclude="kubedock/vcrpy_test_cassettes"  --exclude="*.rpm" . "$TMP_PATH/"
    cp ./kubedock/frontend/static/.babelrc "$TMP_PATH/kubedock/frontend/static/.babelrc"
    cd /tmp
    tar -cjf "$NAME-$VERSION.tar.bz2" "$NAME-$VERSION"
    cd -
fi

mkdir -p /root/rpmbuild/{SPECS,SOURCES}/

cp "$SOURCES_DIR/kuberdock.spec" /root/rpmbuild/SPECS/
mv "/tmp/$NAME-$VERSION.tar.bz2" /root/rpmbuild/SOURCES/

echo "########## Starting the RPM build ##########"
rpmbuild --define="dist .el7" --quiet -bb /root/rpmbuild/SPECS/kuberdock.spec
EXTRA_NAME=".noarch.rpm"
cp -f "/root/rpmbuild/RPMS/noarch/$NAME-$VERSION-$BUILD_VER$EXTRA_NAME" "$DST/kuberdock.rpm"
echo "########## Done RPM build. Find kuberdock.rpm ##########"
cd "$NOW"
