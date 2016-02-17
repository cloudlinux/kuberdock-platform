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

echo "Set locale to en_US.UTF-8"
export LANG=en_US.UTF-8

# SOME HELPERS

remove_unneeded(){
    rpm -q --whatrequires $@
    if [[ $? -ne 0 ]];then
        yum -y autoremove $@
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

clean_node(){
    echo "=== Node clean up started ==="
    echo "ALL PACKAGES, CONFIGS AND DATA RELATED TO KUBERDOCK AND PODS WILL BE DELETED"

    echo "Stop and disable services..."
    for i in kubelet docker kube-proxy flanneld kuberdock-watcher \
             kuberdock-cadvisor ntpd;do
        systemctl disable $i
        systemctl stop $i
    done
    systemctl unmask docker-storage-setup

    # Maybe only in some cases?
    unmap_ceph

    yum -y remove kubernetes*
    yum -y remove docker
    yum -y remove flannel*
    yum -y remove kuberdock-cadvisor
    remove_unneeded python-requests
    remove_unneeded python-ipaddress
    remove_unneeded ipset
    remove_unneeded ntp

    if [ "$AWS" = True ];then
        remove_unneeded aws-cli
        remove_unneeded jq
    fi

    # kubelet auth token and etcd certs
    rm -rf $KUBERNETES_CONF_DIR
    rm -rf /etc/pki/etcd

    rm -rf $PLUGIN_DIR_BASE
    rm -f $KD_WATCHER_SERVICE

    rm -f /etc/sysconfig/flanneld*
    rm -f /etc/systemd/system/flanneld.service
    rm -rf /run/flannel

    rm -f $KD_KERNEL_VARS

    rm -rf /etc/sysconfig/docker*

    rm -rf /var/lib/docker
    rm -rf /var/lib/kubelet
    rm -rf /var/lib/kuberdock
    rm -rf $CADVISOR_CONF*
    rm -rf $KD_ELASTIC_LOGS

    rm -f $KUBE_REPO
    rm -f $KUBE_TEST_REPO

    rm -f $KD_RSYSLOG_CONF
    systemctl restart rsyslog

    rm -f /etc/ntpd.conf*

    systemctl daemon-reload

    systemctl stop firewalld
    iptables -w -F
    iptables -w -X
    iptables -w -F -t mangle
    iptables -w -X -t mangle
    iptables -w -F -t nat
    iptables -w -X -t nat

    echo "=== Node clean up finished ==="
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
    echo "Seems like SELinux is disabled on this node."\
    "You should enable it (may require to reboot node) and restart node "\
    "installation again."
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


echo "Set time zone to $TZ"
timedatectl set-timezone "$TZ"
echo "Using MASTER_IP=${MASTER_IP}"

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
yum_wrapper -y install kuberdock-cadvisor
check_status
# TODO maybe not needed, make as dependency for kuberdock-node package
yum_wrapper -y install python-requests
yum_wrapper -y install python-ipaddress
yum_wrapper -y install ipset
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
sed -i '/^KUBELET_ARGS/ {s|""|"--kubeconfig=/etc/kubernetes/configfile --cadvisor_port=0 --cluster_dns=10.254.0.10 --cluster_domain=kuberdock --register-node=false --network-plugin=kuberdock --maximum-dead-containers=1 --maximum-dead-containers-per-container=1 --minimum-container-ttl-duration=10s --cpu-cfs-quota=true"|}' $KUBERNETES_CONF_DIR/kubelet
sed -i '/^KUBE_PROXY_ARGS/ {s|""|"--kubeconfig=/etc/kubernetes/configfile"|}' $KUBERNETES_CONF_DIR/proxy
sed -i '/^KUBE_ALLOW_PRIV/ {s/--allow_privileged=false/--allow_privileged=true/}' $KUBERNETES_CONF_DIR/config
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
cat > $KD_RSYSLOG_CONF << 'EOF'
$LocalHostName $NODENAME
$template LongTagForwardFormat,"<%PRI%>%TIMESTAMP:::date-rfc3339% %HOSTNAME% %syslogtag%%msg:::sp-if-no-1st-sp%%msg%"
*.* @127.0.0.1:5140;LongTagForwardFormat
EOF



# overlayfs enable
systemctl mask docker-storage-setup
sed -i '/^DOCKER_STORAGE_OPTIONS=/c\DOCKER_STORAGE_OPTIONS=--storage-driver=overlay' /etc/sysconfig/docker-storage


# enable registries with self-sighned certs
sed -i "s|^# \(INSECURE_REGISTRY='--insecure-registry\)'|\1=0.0.0.0/0'|" /etc/sysconfig/docker

echo 'Enabling docker...'
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
if [ ! -d /var/lib/docker/overlay ]; then
  mkdir -p /var/lib/docker/overlay
fi
FS=$(df --print-type /var/lib/docker/overlay | tail -1)
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
  echo "Only XFS supported as backing filesystem for disk space limits"
fi


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

# 12. Check kernel
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

# 13. Reboot will be executed in python function

exit 0
