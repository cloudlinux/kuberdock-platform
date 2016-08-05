#!/usr/bin/env bash
set -e

SOURCES_DIR=${1:-"./kuberdock-manage/"}
DST=${2:-"./builds/"}

VERSION=$(grep "Version:" $SOURCES_DIR/kuberdock-manage.spec | grep -oP "\d+\.\d+.*")
BUILD_VER=$(grep "Release:" $SOURCES_DIR/kuberdock-manage.spec | sed -rn 's/.*: (.*)%\{\?dist\}(.*)/\1.el7\2/p' | tr -d '[:blank:]')
NAME=kuberdock-manage
TMP_PATH=/tmp/$NAME-$VERSION

NOW=$(pwd)
cd $SOURCES_DIR
if [ -n "$KDCTL_GIT_REF" ]; then
    echo "########## Building KD CTL RPM of '$KDCTL_GIT_REF' version. Changes not in this version are ignored. ##########"
    git archive --format=tar --prefix=$NAME-$VERSION/ $KDCTL_GIT_REF | bzip2 -9 > $TMP_PATH.tar.bz2
else
    echo "########## Building KD CTL RPM from the current state of repo. All changes are included. ##########"
    rm -rf $TMP_PATH
    mkdir $TMP_PATH
    rsync -aP --quiet --exclude=".*" --exclude="dev-utils" --exclude="*.rpm" . $TMP_PATH/
    cd /tmp
    tar -cjf $NAME-$VERSION.tar.bz2 $NAME-$VERSION
    cd -
fi

mkdir -p /root/rpmbuild/{SPECS,SOURCES}/

cp $SOURCES_DIR/kuberdock-manage.spec /root/rpmbuild/SPECS/
mv /tmp/$NAME-$VERSION.tar.bz2 /root/rpmbuild/SOURCES/

echo "########## Starting the RPM build ##########"
rpmbuild --define="dist .el7" --quiet -bb /root/rpmbuild/SPECS/kuberdock-manage.spec
EXTRA_NAME=".noarch.rpm"
cp -f /root/rpmbuild/RPMS/noarch/$NAME-$VERSION-$BUILD_VER$EXTRA_NAME "$DST/kdctl.rpm"
echo "########## Done RPM build. Find kdctl.rpm ##########"
cd $NOW
