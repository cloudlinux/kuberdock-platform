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
# install kubernetes components on Node host

# IMPORTANT: each package must be installed with separate command because of
# yum incorrect error handling!

source "$(dirname "${BASH_SOURCE}")/node_install_common.sh"

ami()
{
    [ -n "${AMI}" ]
}

check_iface_and_ip()
{
# check public interface and node ip
if [ -z "$NODE_IP" ]; then
    >&2 echo "NODE_IP is not set"
    exit 1
else
    if [ -z "$(ip -o addr | grep $NODE_IP)" ]; then
        >&2 echo "IP address $NODE_IP is not found"
        exit 1
    fi
fi

if [ -z "$PUBLIC_INTERFACE" ]; then
    PUBLIC_INTERFACE="$(ip -o ad | grep $NODE_IP | awk '{ print $2 }')"
    if [ -z "$PUBLIC_INTERFACE" ]; then
        >&2 echo "Interface for IP $NODE_IP is not found"
        exit 1;
    fi
else
    if [ -z "$(ip -o addr | grep $PUBLIC_INTERFACE)" ]; then
        >&2 echo "Interface $PUBLIC_INTERFACE not found"
        exit 1
    fi
fi
# // check public interface and node ip
}

ami || check_iface_and_ip

echo "Set locale to en_US.UTF-8"
export LANG=en_US.UTF-8
ami || echo "Using MASTER_IP=${MASTER_IP}"
if [ "$ZFS" = yes ]; then
    echo "Using ZFS as storage backend"
elif [ ! -z "$CEPH_CONF" ]; then
    echo "Using CEPH as storage backend"
else
    echo "Using LVM as storage backend"
fi
ami || set_timezone
echo "Deploy started: $(date)"

# This should be as early as possible because outdated metadata (one that was
# before sync time with ntpd) could cause troubles with https metalink for
# repos like EPEL.
yum clean metadata

# ======================== JUST COMMON HELPERS ================================
# SHOULD BE DEFINED FIRST, AND BEFORE USE
# Most common helpers are defined first.
yum_wrapper()
{
    if [ -z "$WITH_TESTING" ];then
        yum -d 1 --enablerepo=kube $@
    else
        yum -d 1 --enablerepo=kube,kube-testing $@
    fi
    check_status
}


chk_ver()
{
    python -c "import rpmUtils.miscutils as misc; print misc.compareEVR(misc.stringToVersion('$1'), misc.stringToVersion('$2')) < 0"
}
# ========================== // HELPERS =======================================



# ========================== Node cleanup procedure ===========================
unmap_ceph(){
    which rbd &> /dev/null
    if [[ $? -eq 0 ]];then
        echo "Try unmount and unmap all rbd drives"
        for i in $(ls -1 /dev/ | grep -P 'rbd\d+');do
            umount "/dev/$i"
            rbd unmap "/dev/$i"
        done
    fi
}


remove_unneeded(){
    rpm -q --whatrequires $@ &> /dev/null
    if [[ $? -ne 0 ]];then
        yum -y autoremove $@ &> /dev/null
    fi
}


del_existed(){
    for i in "$@";do
        if [[ -e "$i" ]];then
            echo "Deleting $i"
            rm -rf "$i"
        fi
    done
}


# WARN: This helper used both to setup and cleanup cron
setup_cron(){
    if [[ "$1" = 'cleanup' ]];then
        (crontab -l 2>/dev/null) | grep -v "$KD_SSH_GC_CRON" | crontab -
    else
        (crontab -l 2>/dev/null; echo "$KD_SSH_GC_CRON")| crontab -
    fi
}


# Setup proper backend for local storage to enable it's cleanup in clean_node
cd /${NODE_STORAGE_MANAGE_DIR}
rm -f storage.py
if [ "$ZFS" = yes ]; then
    echo "Will cleanup ZFS-based storage"
    ln -s node_zfs_manage.py storage.py
else
    echo "Will cleanup LVM-based storage"
    ln -s node_lvm_manage.py storage.py
fi
check_status
cd - > /dev/null


clean_node(){
    echo "=== Node clean up started ==="
    echo "ALL PACKAGES, CONFIGS AND DATA RELATED TO KUBERDOCK AND PODS WILL BE DELETED"

    # Delete this before stopping docker because we use 10min timeout for docker service stop/restart
    # and don't need to wait it during cleanup
    del_existed /etc/systemd/system/docker.service.d/*
    systemctl daemon-reload

    echo "Stop and disable services..."
    for i in kubelet docker kube-proxy kuberdock-watcher ntpd; do
        systemctl disable $i &> /dev/null
        systemctl stop $i &> /dev/null
    done
    systemctl unmask docker-storage-setup &> /dev/null

    # Maybe only in some cases?
    unmap_ceph

    setup_cron 'cleanup'

    echo "Remove some packages (k8s, docker, etc.)..."
    {
        # We should prevent bash pre-processing with quotes
        yum -y remove 'kubernetes*'
        yum -y remove docker
        yum -y remove docker-selinux
        yum -y remove kuberdock-cadvisor  # obsolete package
        yum -y remove calicoctl
        yum -y remove calico-cni
    } &> /dev/null
    remove_unneeded python-requests
    remove_unneeded python-ipaddress
    remove_unneeded ipset
    remove_unneeded ntp

    if [ "$AWS" = True ];then
        remove_unneeded awscli
        remove_unneeded jq
        remove_unneeded python2-boto
        remove_unneeded python2-botocore
    fi

    if [ ! -z "$CEPH_CONF" ]; then
        remove_unneeded ceph-common
    else
        # clean any LocalStorage (LVM group, ZFS pool)
        echo "Clean local storage ..."

        # TODO remove along with deprecated LVM
        # Needed because of import error lvm in case of cluster with non-zfs and
        # non-lvm LocalStorage
        # Use "raw" yum because yum_wrapper needs kube repos
        yum -d 1 -y install lvm2-python-libs
        # AC-5434 Not sure, but looks like this is temporary workaround during CentOS 7.2 to 7.3 upgrade period,
        # without this Yum will 100% fail to install any package:
        vgs &> /dev/null

        PYTHONPATH=/ python2 -m ${NODE_STORAGE_MANAGE_DIR}.manage remove-storage
        remove_unneeded zfs
        remove_unneeded zfs-release

        del_existed "$ZFS_MODULES_LOAD_CONF"
        del_existed "$ZFS_POOLS_LOAD_CONF"
    fi

    # kubelet auth token and etcd certs
    echo "Deleting some files and configs..."
    del_existed $KUBERNETES_CONF_DIR
    del_existed /etc/pki/etcd

    del_existed $PLUGIN_DIR_BASE
    del_existed $KD_WATCHER_SERVICE

    del_existed $KD_KERNEL_VARS

    del_existed /etc/sysconfig/docker*
    del_existed /etc/systemd/system/docker.service*
    del_existed /etc/systemd/system/kube-proxy.service*
    del_existed /etc/systemd/system/ntpd.service*

    del_existed /var/lib/docker
    del_existed /var/lib/kubelet
    del_existed /var/lib/kuberdock
    del_existed $KD_ELASTIC_LOGS

    del_existed $KUBE_REPO
    del_existed $KUBE_TEST_REPO

    del_existed $CEPH_BASE
    del_existed $CEPH_REPO

    del_existed $KD_RSYSLOG_CONF
    systemctl restart rsyslog &> /dev/null

    del_existed /etc/ntpd.conf*

    del_existed /etc/cni
    del_existed /var/log/calico
    del_existed /var/run/calico

    systemctl daemon-reload

    systemctl stop firewalld &> /dev/null
    iptables -w -F
    iptables -w -X
    iptables -w -F -t mangle
    iptables -w -X -t mangle
    iptables -w -F -t nat
    iptables -w -X -t nat

    echo "=== Node clean up finished === $(date)"
}

# TODO run only when node already been installed in KD. This will require
# file-marker and upgrade script to place it on all nodes
clean_node  # actual clean up
# ========================== //Node cleanup procedure =========================



# =============== Various KD requirements checking (after cleanup!) ===========
RELEASE="CentOS Linux release 7.[2-3]"
ARCH="x86_64"
MIN_RAM_KB=1572864
MIN_DISK_SIZE=10
WARN_DISK_SIZE=50

ERRORS=""
WARNS=""

check_release()
{
    cat /etc/redhat-release | grep -P "$RELEASE" > /dev/null
    if [ $? -ne 0 ] || [ `uname -m` != $ARCH ];then
        ERRORS="$ERRORS Inappropriate OS version\n"
    fi
}

check_selinux(){
    if [[ $(getenforce) != 'Enforcing' ]];then
        ERRORS="$ERRORS Seems like SELinux is either disabled or is in a permissive mode on this node.\n\
You should set it to \"enforcing\" mode in /etc/selinux/config, reboot the node and restart node installation.\n"
    fi
}

check_mem(){
    MEM=$(vmstat -s | head -n 1 | awk '{print $1}')
    if [[ $MEM -lt $MIN_RAM_KB ]]; then
        ERRORS="$ERRORS Node RAM space is insufficient\n"
    fi
}

check_disk(){
    DISK_SIZE=$(df --output=avail -BG / | tail -n +2)
    if [ ${DISK_SIZE%?} -lt $MIN_DISK_SIZE ]; then
        ERRORS="$ERRORS Node free disk space is insufficient\n"
    fi
}

check_disk_for_production(){
    if [ ${DISK_SIZE%?} -lt $WARN_DISK_SIZE ]; then
        WARNS="$WARNS It is strongly recommended to free more disk space to avoid performance problems\n"
    fi
}

check_xfs()
{
  if [ ! -d "$1" ]; then
    mkdir -p "$1"
  fi
  FS=$(df --print-type "$1" | tail -1)
  FS_TYPE=$(awk '{print $2}' <<< "$FS")
  if [ "$FS_TYPE" != "xfs" ]; then
    ERRORS="$ERRORS Only XFS supported as backing filesystem for disk space limits ($1)\n"
  fi
}

check_release
ami || check_mem
check_selinux
check_xfs "/var/lib/docker/overlay"

if [ "$ZFS" != "yes" -a "$AWS" != True ]; then
    check_xfs "/var/lib/kuberdock/storage"
fi

if [[ $ERRORS ]]; then
    printf "Following noncompliances of KD cluster requirements have been detected:\n"
    printf "$ERRORS"
    printf "For details refer Requirements section of KuberDock Documentation, http://docs.kuberdock.com/index.html?requirements.htm\n"
    exit 3
fi

ami || check_disk

if [[ $ERRORS ]]; then
    printf "Following noncompliances of KD cluster requirements have been detected:\n"
    printf "$ERRORS"
    printf "For details refer Requirements section of KuberDock Documentation, http://docs.kuberdock.com/index.html?requirements.htm\n"
    exit 3
fi

ami || check_disk_for_production

if [[ $WARNS ]]; then
    printf "Warning:\n"
    printf "$WARNS"
    printf "For details refer Requirements section of KuberDock Documentation, http://docs.kuberdock.com/index.html?requirements.htm\n"
fi

setup_ntpd ()
{
    # TODO Actually we can use here yum wrapper if we sure about added repos
    # AC-3199 Remove chrony which prevents ntpd service to start after boot
    yum -d 1 erase -y chrony
    check_status
    if rpm -q epel-release >> /dev/null; then
      # prevent EPEL metadata update before time sync
      yum -d 1 install -y ntp --disablerepo=epel
    else
      yum -d 1 install -y ntp
    fi
    check_status

    local ntp_config="/etc/ntp.conf"

    _sync_time() {
        grep '^server' "$ntp_config" | awk '{print $2}' | xargs ntpdate -u
    }

    # We use setup like this
    # http://docs.openstack.org/juno/install-guide/install/yum/content/ch_basic_environment.html#basics-ntp
    # Decrease poll interval to be more closer to master time
    for _retry in $(seq 3); do
        # http://www.planetcobalt.net/sdb/ntp_leap.shtml
        echo "Attempt $_retry to run ntpdate -u ..." && \
        _sync_time && break || sleep 30;
    done
    _sync_time
    check_status

    ami || configure_ntpd

    systemctl daemon-reload
    systemctl restart ntpd
    check_status
    systemctl reenable ntpd
    check_status
}


prjquota_enable()
{
  if [ ! -d "$1" ]; then
    mkdir -p "$1"
  fi
  FS=$(df --print-type "$1" | tail -1)
  FS_TYPE=$(awk '{print $2}' <<< "$FS")
  if [ "$FS_TYPE" == "xfs" ]; then
    MOUNTPOINT=$(awk '{print $7}' <<< "$FS")
    if [ "$MOUNTPOINT" == "/" ]; then
      if ! rpm -q grubby >> /dev/null; then
        yum_wrapper -y install grubby
      fi
      echo "Enabling XFS Project Quota in GRUB"
      grubby --args=rootflags=prjquota --update-kernel=ALL
    fi
    if ! grep -E "^[^#]\S*[[:blank:]]$MOUNTPOINT[[:blank:]].*prjquota|^[^#]\S*[[:blank:]]$MOUNTPOINT[[:blank:]].*pquota" /etc/fstab; then
      echo "Enabling XFS Project Quota for $MOUNTPOINT in /etc/fstab"
      sed -i "\|^[^#]\S*[[:blank:]]$MOUNTPOINT[[:blank:]]|s|defaults|defaults,prjquota|" /etc/fstab
    fi
  else
    echo "Only XFS supported as backing filesystem for disk space limits ($1)"
  fi
}


install_ceph_client()
{

  which rbd &> /dev/null
  if [[ $? -eq 0 ]];then
    return
  fi

cat > $CEPH_BASE << EOF
http://download.ceph.com/rpm-$CEPH_VERSION/rhel7/\$basearch
http://eu.ceph.com/rpm-$CEPH_VERSION/el7/\$basearch
http://au.ceph.com/rpm-$CEPH_VERSION/el7/\$basearch
EOF

cat > $CEPH_REPO << EOF
[Ceph]
name=Ceph packages
#baseurl=http://download.ceph.com/rpm-$CEPH_VERSION/rhel7/\$basearch
mirrorlist=file:///etc/yum.repos.d/ceph-base
enabled=1
gpgcheck=1
type=rpm-md
gpgkey=https://ceph.com/git/?p=ceph.git;a=blob_plain;f=keys/release.asc
EOF

  CNT=1
  /bin/false
  while [ $? -ne 0 ]; do
      echo "Trying to install CEPH-client $CNT"
      ((CNT++))
      if [[ $CNT > 4 ]]; then
          yum --enablerepo=Ceph --nogpgcheck install -y ceph-common
          check_status
      else
          yum --enablerepo=Ceph install -y ceph-common
      fi
  done
  echo "CEPH-client has been installed"

}


enable_epel()
{
  rpm --import https://dl.fedoraproject.org/pub/epel/RPM-GPG-KEY-EPEL-7
  rpm -q epel-release &> /dev/null || yum_wrapper -y install epel-release
  check_status

  # Clean metadata once again if it's outdated after time sync with ntpd
  yum -d 1 --disablerepo=* --enablerepo=epel clean metadata

  # sometimes certificates can be outdated and this could cause
  # EPEL https metalink problems
  yum_wrapper -y --disablerepo=epel upgrade ca-certificates
  check_status
  yum_wrapper -y --disablerepo=epel install yum-utils
  check_status
  yum-config-manager --save --setopt timeout=60.0
  yum-config-manager --save --setopt retries=30
  check_status

  _get_epel_metadata() {
    # download metadata only for EPEL repo
    yum -d 1 --disablerepo=* --enablerepo=epel clean metadata
    yum -d 1 --disablerepo=* --enablerepo=epel makecache fast
  }

  for _retry in $(seq 5); do
    echo "Attempt $_retry to get metadata for EPEL repo ..."
    _get_epel_metadata && return || sleep 10
  done
  _get_epel_metadata
  check_status
}


# Workaround for CentOS 7 minimal CD bug.
# https://github.com/GoogleCloudPlatform/kubernetes/issues/5243#issuecomment-78080787
SWITCH=`cat /etc/nsswitch.conf | grep "^hosts:"`
if [ -z "$SWITCH" ];then
    echo "WARNING: Can't find \"hosts:\" line in /etc/nsswitch.conf"
    echo "Please, modify it to include myhostname at \"hosts:\" line"
else
    if [[ ! $SWITCH == *"myhostname"* ]];then
        sed -i "/^hosts:/ {s/$SWITCH/$SWITCH myhostname/}" /etc/nsswitch.conf
        echo 'We modify your /etc/nsswitch.conf to include "myhostname" at "hosts:" line'
    fi
fi

rpm -q firewalld
if [ $? == 0 ];then
    echo "Stop firewalld. Dynamic Iptables rules will be used instead."
    systemctl stop firewalld
    systemctl mask firewalld
fi

# 1. create yum repo file

cat > $KUBE_REPO << EOF
[kube]
name=kube
baseurl=http://repo.cloudlinux.com/kubernetes/x86_64/
enabled=0
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF

# Add kubernetes testing repo
cat > $KUBE_TEST_REPO << EOF
[kube-testing]
name=kube-testing
baseurl=http://repo.cloudlinux.com/kubernetes-testing/x86_64/
enabled=0
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF


# 1.0 import CloudLinux key
rpm --import http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
check_status

# Ensure latest packages from new repos
yum --enablerepo=kube,kube-testing clean metadata


# Should be done at the very beginning to ensure yum https works correctly
# for example EPEL https metalink will not work if time is incorrect
setup_ntpd

enable_epel

# Check kernel
current_kernel=$(uname -r)
check_kernel=$(chk_ver "$current_kernel" "3.10.0-327.4.4")

if [ "$check_kernel" == "True" ]
then
    if [ "$ZFS" = yes ]; then
        echo "================================================================================"
        echo "Your kernel is too old, please upgrade it first, reboot the machine and readd the node to KuberDock to " \
             "continue installation"
        exit 1
    fi

    # If ZFS was not needed it is safe to upgrade the kernel
    echo "Current kernel is $current_kernel, upgrading..."
    yum_wrapper -y install kernel
    yum_wrapper -y install kernel-tools
    yum_wrapper -y install kernel-tools-libs
    yum_wrapper -y install kernel-headers
    yum_wrapper -y install kernel-devel

elif [ "$ZFS" = yes ]; then
   yum info --enablerepo=kube,kube-testing $(rpm --quiet -q epel-release && echo '--disablerepo=epel') -q kernel-devel-$current_kernel
   if [ $? -ne 0 ]; then
       echo "================================================================================"
       echo "kernel-devel-$current_kernel is not available. Please install it manually or upgrade kernel and " \
            "readd the node to KuberDock to continue installation"
       exit 1
   fi
fi
# ================= // Various KD requirements checking ====================



# 2. install components
echo "Installing kubernetes..."
yum_wrapper -y install ${NODE_KUBERNETES}
echo "Installing docker..."
yum_wrapper -y install docker-selinux-1.12.1-5.el7
yum_wrapper -y install docker-1.12.1-5.el7
# TODO maybe not needed, make as dependency for kuberdock-node package
yum_wrapper -y install python-requests
yum_wrapper -y install python-ipaddress
# tuned - daemon to set proper performance profile.
# It is installed by default, but ensure it is here
# TODO why installed here but used very later in script?
yum_wrapper -y install tuned
# kdtools - statically linked binaries to provide ssh access into containers
yum_wrapper -y install kdtools

# TODO AC-4871: move to kube-proxy dependencies
yum_wrapper -y install conntrack-tools

# 3. If amazon instance install additional packages from epel
if [ "$AWS" = True ];then
    # we need to install command-line json parser from epel
    yum_wrapper -y install awscli
    yum_wrapper -y install jq
    yum_wrapper -y install python2-botocore
    yum_wrapper -y install python2-boto
fi


# 4 copy kubelet auth token and etcd certs
copy_kubelet_auth_and_etcd_certs()
{
echo "Copy certificates and tokens..."
mv /configfile $KUBERNETES_CONF_DIR/configfile
check_status
mv /ca.crt /etc/pki/etcd/
mv /etcd-client.crt /etc/pki/etcd/
mv /etcd-client.key /etc/pki/etcd/
mv /etcd-dns.crt /etc/pki/etcd/
mv /etcd-dns.key /etc/pki/etcd/
check_status
}

mkdir -p /etc/pki/etcd
ami || copy_kubelet_auth_and_etcd_certs

# 4.1 create and populate scripts directory
# TODO refactor this staff to kdnode package or copy folder ones
mkdir -p /var/lib/kuberdock/scripts
check_status
mkdir -p /var/lib/kuberdock/backups
check_status
mv /pd.sh /var/lib/kuberdock/scripts/pd.sh      # TODO remove, obsoleted
chmod +x /var/lib/kuberdock/scripts/pd.sh
mv /fslimit.py /var/lib/kuberdock/scripts/fslimit.py
chmod +x /var/lib/kuberdock/scripts/fslimit.py
mv /kubelet_args.py /var/lib/kuberdock/scripts/kubelet_args.py
chmod +x /var/lib/kuberdock/scripts/kubelet_args.py
check_status

mv /kd-ssh-user.sh /var/lib/kuberdock/scripts/kd-ssh-user.sh
chmod +x /var/lib/kuberdock/scripts/kd-ssh-user.sh
check_status
mv /kd-docker-exec.sh /var/lib/kuberdock/scripts/kd-docker-exec.sh
chmod +x /var/lib/kuberdock/scripts/kd-docker-exec.sh
check_status
mv /kd-ssh-user-update.sh /var/lib/kuberdock/scripts/kd-ssh-user-update.sh
chmod +x /var/lib/kuberdock/scripts/kd-ssh-user-update.sh
check_status

mv /kd-ssh-gc "$KD_SSH_GC_PATH"
chmod +x "$KD_SSH_GC_PATH"
check_status

chmod +x "/usr/bin/kd-backup-node"
check_status
chmod +x "/usr/bin/kd-backup-node-merge"
check_status

# For direct ssh feature
groupadd kddockersshuser
# Config patching should be idempotent
! grep -q 'kddockersshuser' /etc/sudoers && \
echo -e '\n%kddockersshuser ALL=(ALL) NOPASSWD: /var/lib/kuberdock/scripts/kd-docker-exec.sh' >> /etc/sudoers
! grep -q 'Defaults:%kddockersshuser' /etc/sudoers && \
echo -e '\nDefaults:%kddockersshuser !requiretty' >> /etc/sudoers

! grep -q 'kddockersshuser' /etc/ssh/sshd_config && \
printf '\nMatch group kddockersshuser
  PasswordAuthentication yes
  X11Forwarding no
  AllowTcpForwarding no
  ForceCommand /var/lib/kuberdock/scripts/kd-ssh-user.sh\n' >> /etc/ssh/sshd_config

# Append SSH GC to cron
setup_cron

# Useless if we do reboot:
# systemctl restart sshd.service

mv /${NODE_STORAGE_MANAGE_DIR} /var/lib/kuberdock/scripts/

ami || kuberdock_json

# 5. configure Node config
ami || configure_kubelet


# 6a. configure Calico CNI plugin
echo "Enabling Calico CNI plugin ..."
yum_wrapper -y install calico-cni-1.3.1-3.el7

ami || configure_cni

pushd /var/lib/kuberdock/scripts
python kubelet_args.py --network-plugin=
python kubelet_args.py --network-plugin=cni --network-plugin-dir=/etc/cni/net.d
popd

# 7. Setting kernel parameters
modprobe bridge
sysctl -w net.ipv4.ip_nonlocal_bind=1
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.bridge.bridge-nf-call-iptables=1
sysctl -w net.bridge.bridge-nf-call-ip6tables=1
# AC-4738. This is needed because MySQL(and many other) containers actively
# uses aio and consume lots of this resource which is by default 65535 so we
# should increase it to achieve much higher density of containers. No kernel
# data structures are pre-allocated for this.
sysctl -w fs.aio-max-nr=1048576
check_status
cat > $KD_KERNEL_VARS << EOF
net.ipv4.ip_nonlocal_bind = 1
net.ipv4.ip_forward = 1
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
fs.aio-max-nr = 1048576
EOF



# 8. setup rsyslog forwarding
ami || configure_rsyslog


echo 'Configuring docker...'
# overlayfs enable
systemctl mask docker-storage-setup
sed -i '/^DOCKER_STORAGE_OPTIONS=/c\DOCKER_STORAGE_OPTIONS=--storage-driver=overlay' /etc/sysconfig/docker-storage


# enable registries with self-sighned certs
sed -i "s|^# \(INSECURE_REGISTRY='--insecure-registry\)'|\1=0.0.0.0/0'|" /etc/sysconfig/docker

# AC-3191 additional docker params
sed -i "s|^OPTIONS='\(.*\)'|OPTIONS='\1 ${DOCKER_PARAMS}'|" /etc/sysconfig/docker

# Docker is extremely slow on restart/stop/start when there are many containers
# was running. This could lead to timeouts during upgrade.
# Maybe this value is too high but we don't know yet what will be the case on
# production clusters under heavy load
mkdir -p /etc/systemd/system/docker.service.d
cat << EOF > /etc/systemd/system/docker.service.d/timeouts.conf
[Service]
TimeoutSec=600
EOF

# TODO we will get reed of this later in favor of drop-ins or in packaged files
cat > /etc/systemd/system/docker.service << 'EOF'
[Unit]
Description=Docker Application Container Engine
Documentation=http://docs.docker.com
After=network.target

[Service]
Type=notify
EnvironmentFile=-/etc/sysconfig/docker
EnvironmentFile=-/etc/sysconfig/docker-storage
EnvironmentFile=-/etc/sysconfig/docker-network
Environment=GOTRACEBACK=crash
ExecStart=/usr/bin/docker daemon $OPTIONS \
          $DOCKER_STORAGE_OPTIONS \
          $DOCKER_NETWORK_OPTIONS \
          $ADD_REGISTRY \
          $BLOCK_REGISTRY \
          $INSECURE_REGISTRY
LimitNOFILE=1048576
LimitNPROC=1048576
LimitCORE=infinity
MountFlags=slave
TimeoutStartSec=1min
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl reenable docker
check_status

# 9. prepare things for logging pod

# fix elasticsearch home directory ownership (if ES was running as service)
if [ -d /var/lib/elasticsearch ]; then
  chown -R root:root /var/lib/elasticsearch
else
  mkdir -p /var/lib/elasticsearch
fi
check_status
chcon -Rt svirt_sandbox_file_t /var/lib/elasticsearch
check_status
mv "/make_elastic_config.py" "/var/lib/elasticsearch"
chmod +x "/var/lib/elasticsearch/make_elastic_config.py"

# prjquota enable
prjquota_enable "/var/lib/docker/overlay"
prjquota_enable "/var/lib/kuberdock/storage"


# 10. enable services
echo "Enabling services..."
systemctl daemon-reload
ami || systemctl reenable kubelet
check_status

mkdir -p /etc/systemd/system/kube-proxy.service.d
echo -e "[Unit]
After=network-online.target

[Service]
Restart=always
RestartSec=5s" > /etc/systemd/system/kube-proxy.service.d/restart.conf
systemctl daemon-reload

ami || systemctl reenable kube-proxy
check_status

# 11. disable swap for best performance
echo "Disabling swap"
swapoff -a

echo "Backing up fstab to: ${FSTAB_BACKUP}"
cp /etc/fstab ${FSTAB_BACKUP}
check_status

echo "Removing swap entries from fstab"
sed -r -i '/[[:space:]]+swap[[:space:]]+/d' /etc/fstab
check_status

# 12. Enable restart for ntpd
echo "Enabling restart for ntpd.service"
mkdir -p /etc/systemd/system/ntpd.service.d
echo -e "[Service]
Restart=always
RestartSec=1s" > /etc/systemd/system/ntpd.service.d/restart.conf
systemctl daemon-reload

# 13. Install and configure CEPH client if CEPH config is defined in envvar
#     Or packages for local storage backend
if [ ! -z "$CEPH_CONF" ]; then

    install_ceph_client

    chmod 600 $CEPH_CONF/*
    chmod 644 $CEPH_CONF/ceph.conf
    mv $CEPH_CONF/* /etc/ceph/
    check_status

else
    if [ "$ZFS" = yes ]; then
        yum_wrapper -y install --nogpgcheck http://download.zfsonlinux.org/epel/zfs-release$(rpm -E %dist).noarch.rpm
        # Use exact version of kernel-headers as current kernel.
        # If it differs, then installation of spl-dkms, zfs-dkms will fail
        yum_wrapper -y install kernel-devel-$current_kernel
        yum_wrapper -y install zfs
        # Zfs could mount pools automatically at boot time even without
        # fstab records, but this is disabled by default in most
        # cases (e.g. AWS case) so enable this:
        echo 'options zfs zfs_autoimport_disable=0' > "$ZFS_POOLS_LOAD_CONF"
        # Set Adaptive replacement cache size to 1/3 of available memory.
        # We want to tune storage for DB better performance, there is built-in
        # tools for caching. Also zfs is not the only FS on a node, so some
        # memory should be available for native kernel cache tools.
        total_memory=$(free -b | awk '/^Mem:/{print $2}')
        zfs_arc_max=$(($total_memory / 3))
        echo "options zfs zfs_arc_max=$zfs_arc_max" >> "$ZFS_POOLS_LOAD_CONF"
        # Disable prefetch for zfs because we assume random reads as general
        # load for persistent volumes.
        echo 'options zfs zfs_prefetch_disable=1' >> "$ZFS_POOLS_LOAD_CONF"

        # Kernel will load zfs modules automatically only in case when zfs is
        # detected on any block device attached to the node. But we should load
        # them explicitly because in case of deploy/workflow errors we could
        # stay in not usable state
        echo 'zfs' > "$ZFS_MODULES_LOAD_CONF"

        /sbin/modprobe zfs
        check_status

        systemctl enable zfs.target
        systemctl enable zfs-import-cache
        systemctl enable zfs-mount
    else
        # If it is not CEPH-enabled installation, then manage persistent storage
        # via LVM.
        # Python bindings to manage LVM
        yum_wrapper -y install lvm2-python-libs
    fi
fi


# 14. Set valid performance profile.
# We need maximum performance to valid work of cpu limits and multipliers.
# All CPUfreq drivers are built in as part of the kernel-tools package.
systemctl reenable tuned
systemctl restart tuned
# check if we are in guest VN
systemd-detect-virt --vm --quiet
if [ $? -ne 0 ]; then
    # We are on host system or in some kind of container. Just set profile to
    # maximum performance.
    tuned-adm profile latency-performance
else
    # we are in guest VM, there is special profile 'virtual-guest' for guest
    # VM's. It provides 'performance' governor for cpufreq.
    # It is active by default on guest systems, but ensure it is there.
    tuned-adm profile virtual-guest
fi


# 15. Run Docker and Calico node
echo "Starting Calico node..."
systemctl restart docker
yum_wrapper -y install calicoctl-0.22.0-3.el7

# Separate pull command helps to prevent timeout bugs in calicoctl (AC-4679)
# during deploy process under heavy IO (slow dev clusters).
# If it's not enough we could add few retries with sleep here
CALICO_NODE_IMAGE="kuberdock/calico-node:0.22.0-kd2"
echo "Pulling Calico node image..."
docker pull "$CALICO_NODE_IMAGE" > /dev/null
time sync
#sleep 10   # even harder workaround

ami || start_calico_node

# 16. Reboot will be executed in python function
echo "Node deploy script finished: $(date)"

exit 0
