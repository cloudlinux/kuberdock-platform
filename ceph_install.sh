#!/bin/bash
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
# Install ceph components on Node host

echo "Set locale to en_US.UTF-8"
export LANG=en_US.UTF-8

# 1. import gpg key
rpm --import 'https://ceph.com/git/?p=ceph.git;a=blob_plain;f=keys/release.asc'

# 2. create yum repo file for ceph-deploy (giant)
cat > /etc/yum.repos.d/ceph_noarch.repo << EOF
[ceph-noarch]
name=Ceph noarch packages
baseurl=http://ceph.com/rpm-giant/el7/noarch
enabled=1
gpgcheck=1
type=rpm-md
gpgkey=https://ceph.com/git/?p=ceph.git;a=blob_plain;f=keys/release.asc
EOF

# 3.import fedora EPEL key
rpm --import https://dl.fedoraproject.org/pub/epel/RPM-GPG-KEY-EPEL-7

# 4. install epel
yum -y install epel-release

# 5. install necessary packages
yum -y install gperftools leveldb
yum -y install ceph-deploy

# 6. ceph-deploy the host
ceph-deploy install $(hostname -s)

#7. create yum repo file for kernel modules
cat > /etc/yum.repos.d/ceph_kmod.repo << EOF
[ceph-kmod]
name=Ceph testing packages
baseurl=http://ceph.com/rpm-testing/rhel7/\$basearch
enabled=1
gpgcheck=1
type=rpm-md
gpgkey=https://ceph.com/git/?p=ceph.git;a=blob_plain;f=keys/release.asc
EOF

# 8. install rbd kmod packages
yum -y install kmod-rbd
