set -e

SRC=$1
DST=$2
TEMP_DIR=`mktemp -d`
CURRENT_DIR=`pwd`

rpm2cpio $SRC/kuberdock*.rpm > $TEMP_DIR/k.cpio
cd $TEMP_DIR
cpio -idm < $TEMP_DIR/k.cpio
cp $TEMP_DIR/var/opt/kuberdock/deploy.sh $DST
cd $CURRENT_DIR
rm -rf $TEMP_DIR
