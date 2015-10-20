#!/bin/bash

TARGET_HOST=$1
VERSION=hammer
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
ssh root@$TARGET_HOST -i /var/lib/nginx/.ssh/id_rsa -o "StrictHostKeyChecking no" yum --enablerepo=Ceph install -y ceph-common
scp -r -i /var/lib/nginx/.ssh/id_rsa -o "StrictHostKeyChecking no" /var/lib/kuberdock/conf/ceph.* root@$TARGET_HOST:/etc/ceph

