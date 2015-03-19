#!/bin/bash

KUBERDOCK_DIR=/var/opt/kuberdock
KUBE_CONF_DIR=/etc/kubernetes



#0. Import some keys
rpm --import http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
rpm --import https://dl.fedoraproject.org/pub/epel/RPM-GPG-KEY-EPEL-7
yum -y install epel-release

# TODO we must open what we want instead
systemctl stop firewalld; systemctl disable firewalld


#1. Add kubernetes repo
cat > /etc/yum.repos.d/kube-cloudlinux.repo << EOF
[kube]
name=kube
baseurl=http://repo.cloudlinux.com/kubernetes/x86_64/
enabled=1
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF



#2. Install kuberdock
yum -y install kuberdock

#2.1 Fix package path bug
mkdir /var/run/kubernetes
chown kube:kube /var/run/kubernetes

# Start as early as possible, because Flannel need it
echo "Starting etcd..."
systemctl enable etcd
systemctl restart etcd



#3. Configure kubernetes
sed -i "/^KUBE_API_ADDRESS/ {s/127.0.0.1/0.0.0.0/}" $KUBE_CONF_DIR/apiserver
sed -i "/^KUBELET_ADDRESSES/ {s/--machines=127.0.0.1//}" $KUBE_CONF_DIR/controller-manager



#4. Create and populate DB
postgresql-setup initdb
systemctl restart postgresql
python $KUBERDOCK_DIR/postgresql_setup.py
systemctl restart postgresql
cd $KUBERDOCK_DIR
python createdb.py



#5. Start services
systemctl enable redis
systemctl restart redis

systemctl enable influxdb > /dev/null 2>&1
systemctl restart influxdb



# Flannel
echo "Setuping flannel config to etcd..."
etcdctl mk /kuberdock/network/config '{"Network":"10.254.0.0/16", "SubnetLen": 24, "Backend": {"Type": "host-gw"}}' 2> /dev/null
etcdctl get /kuberdock/network/config



#6. Setuping Flannel on master ==========================================
# TODO automate inet_iface and etcd ip
cat > /etc/sysconfig/flanneld << EOF
# Flanneld configuration options

# etcd url location.  Point this to the server where etcd runs
FLANNEL_ETCD="http://127.0.0.1:4001"

# etcd config key.  This is the configuration key that flannel queries
# For address range assignment
FLANNEL_ETCD_KEY="/kuberdock/network/"

# Any additional options that you want to pass
# FLANNEL_OPTIONS="--iface={{ inet_iface }}"
EOF

echo "Starting flannel..."
systemctl enable flanneld
systemctl restart flanneld

echo "Adding bridge to flannel network..."
source /run/flannel/subnet.env

# with host-gw backend we don't have to change MTU (bridge.mtu)
# If we have working NetworkManager we can just
#nmcli -n c delete kuberdock-flannel-br0 &> /dev/null
#nmcli -n connection add type bridge ifname br0 con-name kuberdock-flannel-br0 ip4 $FLANNEL_SUBNET

yum -y install bridge-utils

cat > /etc/sysconfig/network-scripts/ifcfg-kuberdock-flannel-br0 << EOF
DEVICE=br0
STP=yes
BRIDGING_OPTS=priority=32768
TYPE=Bridge
BOOTPROTO=none
IPADDR=$(echo $FLANNEL_SUBNET | cut -f 1 -d /)
PREFIX=$(echo $FLANNEL_SUBNET | cut -f 2 -d /)
MTU=$FLANNEL_MTU
DEFROUTE=yes
IPV4_FAILURE_FATAL=no
IPV6INIT=yes
IPV6_AUTOCONF=yes
IPV6_DEFROUTE=yes
IPV6_PEERDNS=yes
IPV6_PEERROUTES=yes
IPV6_FAILURE_FATAL=no
NAME=kuberdock-flannel-br0
ONBOOT=yes
EOF

echo "Starting bridge..."
ifdown br0
ifup br0
#========================================================================



systemctl enable dnsmasq
systemctl restart dnsmasq

#7. Starting kubernetes...
for i in kube-apiserver kube-controller-manager kube-scheduler;do systemctl enable $i;done
for i in kube-apiserver kube-controller-manager kube-scheduler;do systemctl restart $i;done

#8. Starting web-interface...
systemctl enable emperor.uwsgi
systemctl restart emperor.uwsgi

systemctl enable nginx
systemctl restart nginx



# ======================================================================
echo "WARNING: Firewalld was disabled. You need to configure it to work right"
echo "Successfully done."