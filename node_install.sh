#!/bin/bash
# install kubernetes components on Node host

# IMPORTANT: each package must be installed with separate command because of
# yum incorrect error handling!

# SOME VARS:
AWS=${AWS}
KUBERNETES_CONF_DIR='/etc/kubernetes'
EXIT_MESSAGE="Installation error."
KUBE_REPO='/etc/yum.repos.d/kube-cloudlinux.repo'
KUBE_TEST_REPO='/etc/yum.repos.d/kube-cloudlinux-testing.repo'
PLUGIN_DIR_BASE='/usr/libexec/kubernetes'
KD_WATCHER_SERVICE='/etc/systemd/system/kuberdock-watcher.service'
KD_KERNEL_VARS='/etc/sysctl.d/75-kuberdock.conf'
KD_RSYSLOG_CONF='/etc/rsyslog.d/kuberdock.conf'
KD_ELASTIC_LOGS='/var/lib/elasticsearch'
CADVISOR_CONF='/etc/sysconfig/kuberdock-cadvisor'
FSTAB_BACKUP="/var/lib/kuberdock/backups/fstab.pre-swapoff"
CEPH_VERSION=hammer
CEPH_BASE='/etc/yum.repos.d/ceph-base'
CEPH_REPO='/etc/yum.repos.d/ceph.repo'

echo "Set locale to en_US.UTF-8"
export LANG=en_US.UTF-8
echo "Using MASTER_IP=${MASTER_IP}"
echo "Set time zone to $TZ"
timedatectl set-timezone "$TZ"
echo "Deploy started: $(date)"

# SOME HELPERS

remove_unneeded(){
    rpm -q --whatrequires $@ &> /dev/null
    if [[ $? -ne 0 ]];then
        yum -y autoremove $@ &> /dev/null
    fi
}

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

del_existed(){
    for i in "$@";do
        if [[ -e "$i" ]];then
            echo "Deleting $i"
            rm -rf "$i"
        fi
    done
}

clean_node(){
    echo "=== Node clean up started ==="
    echo "ALL PACKAGES, CONFIGS AND DATA RELATED TO KUBERDOCK AND PODS WILL BE DELETED"

    echo "Stop and disable services..."
    for i in kubelet docker kube-proxy flanneld kuberdock-watcher \
             kuberdock-cadvisor ntpd;do
        systemctl disable $i &> /dev/null
        systemctl stop $i &> /dev/null
    done
    systemctl unmask docker-storage-setup &> /dev/null

    # Maybe only in some cases?
    unmap_ceph

    echo "Remove some packages (k8s, docker, etc.)..."
    {
        yum -y remove kubernetes*
        yum -y remove docker
        yum -y remove flannel*
        yum -y remove kuberdock-cadvisor
    } &> /dev/null
    remove_unneeded python-requests
    remove_unneeded python-ipaddress
    remove_unneeded ipset
    remove_unneeded ntp

    if [ "$AWS" = True ];then
        remove_unneeded aws-cli
        remove_unneeded jq
    fi

    if [ ! -z "$CEPH_CONF" ]; then
        remove_unneeded ceph-common
    fi

    # kubelet auth token and etcd certs
    echo "Deleting some files and configs..."
    del_existed $KUBERNETES_CONF_DIR
    del_existed /etc/pki/etcd

    del_existed $PLUGIN_DIR_BASE
    del_existed $KD_WATCHER_SERVICE

    del_existed /etc/sysconfig/flanneld*
    del_existed /etc/systemd/system/flanneld.service
    del_existed /run/flannel

    del_existed $KD_KERNEL_VARS

    del_existed /etc/sysconfig/docker*
    del_existed /etc/systemd/system/docker.service*

    del_existed /var/lib/docker
    del_existed /var/lib/kubelet
    del_existed /var/lib/kuberdock
    del_existed $CADVISOR_CONF*
    del_existed $KD_ELASTIC_LOGS

    del_existed $KUBE_REPO
    del_existed $KUBE_TEST_REPO

    del_existed $CEPH_BASE
    del_existed $CEPH_REPO

    del_existed $KD_RSYSLOG_CONF
    systemctl restart rsyslog &> /dev/null

    del_existed /etc/ntpd.conf*

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
clean_node

check_status()
{
    local temp=$?
    if [ $temp -ne 0 ];then
        echo $EXIT_MESSAGE
        exit $temp
    fi
}

echo "Node OS: $(cat /etc/redhat-release)"

if [[ $(getenforce) != 'Enforcing' ]];then
    echo -e "Seems like SELinux is either disabled or is in a permissive" \
    "mode on this node."\
    "\nYou should set it to \"enforcing\" mode in /etc/selinux/config," \
    "reboot the node and restart node installation."
    exit 3
fi


yum_wrapper()
{
    if [ -z "$WITH_TESTING" ];then
        yum -d 1 --enablerepo=kube $@
    else
        yum -d 1 --enablerepo=kube,kube-testing $@
    fi
}


chk_ver()
{
    python -c "from distutils.version import LooseVersion; print(LooseVersion('$1') < LooseVersion('$2'))"
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
    if [ "$MOUNTPOINT" == "/" ] && ! grep -E '^GRUB_CMDLINE_LINUX=.*rootflags=prjquota|^GRUB_CMDLINE_LINUX=.*rootflags=pquota' /etc/default/grub; then
      sed -i '/^GRUB_CMDLINE_LINUX=/s/"$/ rootflags=prjquota"/' /etc/default/grub
      grub2-mkconfig -o /boot/grub2/grub.cfg
    fi
    if ! grep -E "^[^#]\S*[[:blank:]]$MOUNTPOINT[[:blank:]].*prjquota|^[^#]\S*[[:blank:]]$MOUNTPOINT[[:blank:]].*pquota" /etc/fstab; then
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


# 1.2 Install ntp, we need correct time for node logs
# We use setup like this
# http://docs.openstack.org/juno/install-guide/install/yum/content/ch_basic_environment.html#basics-ntp
yum_wrapper install -y ntp
check_status
sed -i "/^server /d" /etc/ntp.conf
echo "server ${MASTER_IP} iburst" >> /etc/ntp.conf
systemctl daemon-reload
systemctl restart ntpd
check_status
ntpd -gq
systemctl reenable ntpd
check_status
ntpq -p
if [ $? -ne 0 ];then
    echo "WARNING: ntpq -p exit with error. Maybe some problems with ntpd settings and manual changes needed"
fi


# 2. install components
echo "Installing kubernetes..."
yum_wrapper -y install ${CUR_MASTER_KUBERNETES}
check_status
yum_wrapper -y install docker
check_status
yum_wrapper -y install flannel-0.5.3
check_status
yum_wrapper -y install kuberdock-cadvisor-0.19.5
check_status
# TODO maybe not needed, make as dependency for kuberdock-node package
yum_wrapper -y install python-requests
yum_wrapper -y install python-ipaddress
yum_wrapper -y install ipset
# tuned - daemon to set proper performance profile.
# It is installed by default, but ensure it is here
yum_wrapper -y install tuned
check_status

# 3. If amazon instance install aws-cli, epel and jq
if [ "$AWS" = True ];then
    yum_wrapper -y install aws-cli
    check_status
    # we need to install command-line json parser from epel
    rpm --import https://dl.fedoraproject.org/pub/epel/RPM-GPG-KEY-EPEL-7
    check_status
    yum_wrapper -y install epel-release
    check_status
    yum_wrapper -y install jq
    check_status
fi


# 4 copy kubelet auth token and etcd certs
echo "Copy certificates and tokens..."
mv /configfile $KUBERNETES_CONF_DIR/configfile
mkdir -p /etc/pki/etcd
check_status
mv /ca.crt /etc/pki/etcd/
mv /etcd-client.crt /etc/pki/etcd/
mv /etcd-client.key /etc/pki/etcd/
mv /etcd-dns.crt /etc/pki/etcd/
mv /etcd-dns.key /etc/pki/etcd/
check_status

# 4.1 create and populate scripts directory
mkdir -p /var/lib/kuberdock/scripts
check_status
mkdir -p /var/lib/kuberdock/backups
check_status
mv /pd.sh /var/lib/kuberdock/scripts/pd.sh
chmod +x /var/lib/kuberdock/scripts/pd.sh
mv /fslimit.py /var/lib/kuberdock/scripts/fslimit.py
chmod +x /var/lib/kuberdock/scripts/fslimit.py
mv /kubelet_args.py /var/lib/kuberdock/scripts/kubelet_args.py
chmod +x /var/lib/kuberdock/scripts/kubelet_args.py
check_status



# 4.2 kuberdock kubelet plugin stuff
echo "Setup network plugin..."
PLUGIN_DIR="$PLUGIN_DIR_BASE/kubelet-plugins/net/exec/kuberdock"
mkdir -p "$PLUGIN_DIR/data"
mv "/node_network_plugin.sh" "$PLUGIN_DIR/kuberdock"
mv "/node_network_plugin.py" "$PLUGIN_DIR/kuberdock.py"
chmod +x "$PLUGIN_DIR/kuberdock"
check_status

cat > $KD_WATCHER_SERVICE << EOF
[Unit]
Description=KuberDock Network Plugin watcher
After=flanneld.service
Requires=flanneld.service

[Service]
ExecStart=/usr/bin/env python2 $PLUGIN_DIR/kuberdock.py watch
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl reenable kuberdock-watcher
check_status



# 5. configure Node config
echo "Configuring kubernetes..."
sed -i "/^KUBE_MASTER/ {s|http://127.0.0.1:8080|https://${MASTER_IP}:6443|}" $KUBERNETES_CONF_DIR/config
sed -i "/^KUBELET_HOSTNAME/ {s/--hostname_override=127.0.0.1//}" $KUBERNETES_CONF_DIR/kubelet
sed -i "/^KUBELET_API_SERVER/ {s|http://127.0.0.1:8080|https://${MASTER_IP}:6443|}" $KUBERNETES_CONF_DIR/kubelet
if [ "$AWS" = True ];then
    sed -i '/^KUBELET_ARGS/ {s|""|"--cloud-provider=aws --kubeconfig=/etc/kubernetes/configfile --cadvisor_port=0 --cluster_dns=10.254.0.10 --cluster_domain=kuberdock --register-node=false --network-plugin=kuberdock --maximum-dead-containers=1 --maximum-dead-containers-per-container=1 --minimum-container-ttl-duration=10s --cpu-cfs-quota=true --cpu-multiplier='${CPU_MULTIPLIER}' --memory-multiplier='${MEMORY_MULTIPLIER}'"|}' $KUBERNETES_CONF_DIR/kubelet
else
    sed -i '/^KUBELET_ARGS/ {s|""|"--kubeconfig=/etc/kubernetes/configfile --cadvisor_port=0 --cluster_dns=10.254.0.10 --cluster_domain=kuberdock --register-node=false --network-plugin=kuberdock --maximum-dead-containers=1 --maximum-dead-containers-per-container=1 --minimum-container-ttl-duration=10s --cpu-cfs-quota=true --cpu-multiplier='${CPU_MULTIPLIER}' --memory-multiplier='${MEMORY_MULTIPLIER}'"|}' $KUBERNETES_CONF_DIR/kubelet
fi
sed -i '/^KUBE_PROXY_ARGS/ {s|""|"--kubeconfig=/etc/kubernetes/configfile"|}' $KUBERNETES_CONF_DIR/proxy
check_status



# 6. configure Flannel
cat > /etc/sysconfig/flanneld << EOF
# Flanneld configuration options

# etcd url location.  Point this to the server where etcd runs
FLANNEL_ETCD="https://${MASTER_IP}:2379"

# etcd config key.  This is the configuration key that flannel queries
# For address range assignment
FLANNEL_ETCD_KEY="/kuberdock/network/"

# Any additional options that you want to pass
FLANNEL_OPTIONS="--iface=${FLANNEL_IFACE}"
ETCD_CAFILE="/etc/pki/etcd/ca.crt"
ETCD_CERTFILE="/etc/pki/etcd/etcd-client.crt"
ETCD_KEYFILE="/etc/pki/etcd/etcd-client.key"
EOF

cat > /etc/systemd/system/flanneld.service << EOF
[Unit]
Description=Flanneld overlay address etcd agent
After=network.target
Before=docker.service

[Service]
Type=notify
Restart=always
RestartSec=10
EnvironmentFile=/etc/sysconfig/flanneld
EnvironmentFile=-/etc/sysconfig/docker-network
ExecStart=/usr/bin/flanneld \
    -etcd-endpoints=\${FLANNEL_ETCD} \
    -etcd-prefix=\${FLANNEL_ETCD_KEY} \
    -etcd-cafile=\${ETCD_CAFILE} \
    -etcd-certfile=\${ETCD_CERTFILE} \
    -etcd-keyfile=\${ETCD_KEYFILE} \
    \${FLANNEL_OPTIONS}
ExecStartPost=/usr/libexec/flannel/mk-docker-opts.sh -k DOCKER_NETWORK_OPTIONS -d /run/flannel/docker

[Install]
WantedBy=multi-user.target
EOF

mkdir -p /etc/systemd/system/docker.service.d

cat > /etc/systemd/system/docker.service.d/flannel.conf << EOF
[Service]
EnvironmentFile=/run/flannel/docker
EOF


echo "Enabling Flanneld ..."
rm -f /run/flannel/docker 2>/dev/null
systemctl reenable flanneld
check_status



# 7. Setting kernel parameters
modprobe bridge
sysctl -w net.ipv4.ip_nonlocal_bind=1
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.bridge.bridge-nf-call-iptables=1
sysctl -w net.bridge.bridge-nf-call-ip6tables=1
check_status
cat > $KD_KERNEL_VARS << EOF
net.ipv4.ip_nonlocal_bind = 1
net.ipv4.ip_forward = 1
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
EOF



# 8. setup rsyslog forwarding
echo "Reconfiguring rsyslog..."
cat > $KD_RSYSLOG_CONF << EOF
\$LocalHostName $NODENAME
\$template LongTagForwardFormat,"<%PRI%>%TIMESTAMP:::date-rfc3339% %HOSTNAME% %syslogtag%%msg:::sp-if-no-1st-sp%%msg%"
*.* @127.0.0.1:5140;LongTagForwardFormat
EOF



echo 'Configuring docker...'
# overlayfs enable
systemctl mask docker-storage-setup
sed -i '/^DOCKER_STORAGE_OPTIONS=/c\DOCKER_STORAGE_OPTIONS=--storage-driver=overlay' /etc/sysconfig/docker-storage


# enable registries with self-sighned certs
sed -i "s|^# \(INSECURE_REGISTRY='--insecure-registry\)'|\1=0.0.0.0/0'|" /etc/sysconfig/docker

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
systemctl reenable kubelet
check_status
systemctl reenable kube-proxy
check_status

CADVISOR_CONF=/etc/sysconfig/kuberdock-cadvisor
sed -i "/^CADVISOR_STORAGE_DRIVER/ {s/\"\"/\"influxdb\"/}" $CADVISOR_CONF
sed -i "/^CADVISOR_STORAGE_DRIVER_HOST/ {s/localhost/${MASTER_IP}/}" $CADVISOR_CONF
systemctl reenable kuberdock-cadvisor
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

# 13. Check kernel
current_kernel=$(uname -r)
check_kernel=$(chk_ver "$current_kernel" "3.10.0-327.4.4")

if [ "$check_kernel" == "True" ]
then
    echo "Current kernel is $current_kernel, upgrading..."
    yum_wrapper -y install kernel
    check_status
    yum_wrapper -y install kernel-tools
    check_status
    yum_wrapper -y install kernel-tools-libs
    check_status
    yum_wrapper -y install kernel-headers
    check_status
    yum_wrapper -y install kernel-devel
fi

# 14. Install and configure CEPH client if CEPH config is defined in envvar
if [ ! -z "$CEPH_CONF" ]; then

    install_ceph_client
    
    cp $CEPH_CONF/* /etc/ceph/
    check_status

fi


# 15. Set valid performance profile.
# We need maximum performance to valid work of cpu limits and multipliers.
# All CPUfreq drivers are built in as part of the kernel-tools package.
systemctl reenable tuned
systemctl start tuned
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

# 16. Reboot will be executed in python function
echo "Node deploy script finished: $(date)"

exit 0
