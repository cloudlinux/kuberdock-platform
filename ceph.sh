#!/bin/bash
# Script installs CEPH-client to a node. It is obsolete now, because CEPH
# client will be installed to node automatically, during node adding to KD
# cluster.

MANAGECMD=/var/opt/kuberdock/manage.py

while [[ $# > 1 ]]; do
    key="$1"
    case $key in
        -s|--skip-hostname-check)
        SKIPHOSTNAMECHECK=YES
        ;;
        *)
        ;;
    esac
    shift # past argument or value
done

if [[ -n $1 ]]; then
    TARGET_HOST="$1"
fi

if [[ -z $TARGET_HOST ]]; then
    echo "Empty hostname"
    exit 1
fi


VERSION=hammer
# Check existence of the node with specified hostname in kuberdock database
# to prevent invalid (incomplete) hostnames arguments.
# Skip this checking if ceph client will be installed on host which is not
# attached as a node.
if [[ -z "$SKIPHOSTNAMECHECK" ]]; then
    python $MANAGECMD node-info --nodename "$TARGET_HOST" > /dev/null 2>&1
    if [[ $? != 0 ]]; then
        echo "Node $TARGET_HOST not found in DB. Use -s|--skip-hostname-check flag for installing ceph client to hosts which are not attached as nodes yet."
        exit 1
    fi
fi
#ssh root@$TARGET_HOST -i /var/lib/nginx/.ssh/id_rsa -o "StrictHostKeyChecking no" rpm -ivh http://ceph.com/rpm-$VERSION/el7/noarch/ceph-release-1-0.el7.noarch.rpm --force 
ssh root@$TARGET_HOST -i /var/lib/nginx/.ssh/id_rsa -o "StrictHostKeyChecking no" "
cat > /etc/yum.repos.d/ceph-base << EOF
http://ceph.com/rpm-$VERSION/rhel7/\\\$basearch
http://eu.ceph.com/rpm-$VERSION/rhel7/\\\$basearch
http://au.ceph.com/rpm-$VERSION/rhel7/\\\$basearch
EOF
cat > /etc/yum.repos.d/ceph.repo << EOF
[Ceph]
name=Ceph packages
#baseurl=http://ceph.com/rpm-$VERSION/rhel7/\\\$basearch
mirrorlist=file:///etc/yum.repos.d/ceph-base
enabled=1
gpgcheck=1
type=rpm-md
gpgkey=https://ceph.com/git/?p=ceph.git;a=blob_plain;f=keys/release.asc
EOF
"
#ssh root@$TARGET_HOST -i /var/lib/nginx/.ssh/id_rsa -o "StrictHostKeyChecking no" yum --enablerepo=Ceph install -y ceph-common
CNT=1
/bin/false
while [ $? -ne 0 ]; do
    echo "Trying to install CEPH-client $CNT"
    ((CNT++))
    if [[ $CNT > 4 ]]; then
        ssh root@$TARGET_HOST -i /var/lib/nginx/.ssh/id_rsa -o "StrictHostKeyChecking no" "yum --enablerepo=Ceph --nogpgcheck install -y ceph-common"
    fi
    ssh root@$TARGET_HOST -i /var/lib/nginx/.ssh/id_rsa -o "StrictHostKeyChecking no" "yum --enablerepo=Ceph install -y ceph-common"
done
scp -r -i /var/lib/nginx/.ssh/id_rsa -o "StrictHostKeyChecking no" /var/lib/kuberdock/conf/ceph.* root@$TARGET_HOST:/etc/ceph

if [[ -z "$SKIPHOSTNAMECHECK" ]]; then
    python $MANAGECMD node-flag --nodename $TARGET_HOST --flagname ceph_installed --value true
else
    python $MANAGECMD node-flag --nodename $TARGET_HOST --flagname ceph_installed --value true 2> /dev/null
fi

