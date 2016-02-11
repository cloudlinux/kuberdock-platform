#!/bin/bash
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
