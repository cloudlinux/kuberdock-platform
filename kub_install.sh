#!/bin/bash
# install kubernetes components on Node host

# TODO change rules, not disable
echo "Setting up firewall rules..."
systemctl stop firewalld
systemctl disable firewalld

# TODO somehow remove and automate this(read from some global cluster config, because this script is running on Node machine )
MASTER_IP="192.168.56.100"
echo "Using MASTER_IP=$MASTER_IP"

# 1. create yum repo file

cat > /etc/yum.repos.d/kube-cloudlinux.repo << EOF
[kube]
name=kube
baseurl=http://repo.cloudlinux.com/kubernetes/x86_64/
enabled=1
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF

# 2. install components
echo "Installing kubernetes..."
yum -y install kubernetes
# Direct links for some cases...
# yum -y install http://el6.cloudlinux.com/kubernetes-0.9.1-1.el7.centos.x86_64.rpm     # unstable speed
# yum -y install http://repo.cloudlinux.com/cloudlinux/sources/kubernetes-0.9.1-1.el7.centos.x86_64.rpm
# yum -y install http://repo.cloudlinux.com/kubernetes/x86_64/kubernetes-0.10.0-1.el7.centos.x86_64.rpm

# 3. configure Node config
echo "Configuring services..."
cat > /etc/kubernetes/config << EOF
###
# kubernetes system config
#
# The following values are used to configure various aspects of all
# kubernetes services, including
#
#   kubernetes-apiserver.service
#   kubernetes-controller-manager.service
#   kubernetes-scheduler.service
#   kubelet.service
#   kubernetes-proxy.service

# Comma seperated list of nodes in the etcd cluster
KUBE_ETCD_SERVERS="--etcd_servers=http://$MASTER_IP:4001"

# logging to stderr means we get it in the systemd journal
KUBE_LOGTOSTDERR="--logtostderr=true"

# journal message level, 0 is debug
KUBE_LOG_LEVEL="--v=0"

# Should this cluster be allowed to run privleged docker containers
KUBE_ALLOW_PRIV="--allow_privileged=false"
EOF

# 4. configure Node kubelet

cat > /etc/kubernetes/kubelet << EOF
###
# kubernetes kubelet (Node) config

# The address for the info server to serve on (set to 0.0.0.0 or "" for all interfaces)
KUBELET_ADDRESS="--address=0.0.0.0"

# The port for the info server to serve on
KUBELET_PORT="--port=10250"

# You may leave this blank to use the actual hostname
KUBELET_HOSTNAME=""

# Add your own!
KUBELET_ARGS=""
EOF

# 5. enable services
echo "Starting services..."
systemctl enable cadvisor; systemctl start cadvisor
systemctl enable kube-proxy; systemctl start kube-proxy
systemctl enable kubelet; systemctl start kubelet
systemctl enable docker; systemctl start docker