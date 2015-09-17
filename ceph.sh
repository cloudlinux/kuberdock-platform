#!/bin/bash

TARGET_HOST=$1
VERSION=hammer
ssh root@$TARGET_HOST -i /var/lib/nginx/.ssh/id_rsa -o "StrictHostKeyChecking no" rpm -ivh http://ceph.com/rpm-$VERSION/el7/noarch/ceph-release-1-0.el7.noarch.rpm --force 
ssh root@$TARGET_HOST -i /var/lib/nginx/.ssh/id_rsa -o "StrictHostKeyChecking no" yum --enablerepo=Ceph install -y ceph-common
scp -r -i /var/lib/nginx/.ssh/id_rsa -o "StrictHostKeyChecking no" /var/lib/kuberdock/conf/ceph.* root@$TARGET_HOST:/etc/ceph



