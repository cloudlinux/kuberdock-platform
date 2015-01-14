#!/bin/bash
# install kubernetes components on minion host

# TODO change rules, not disable
echo "Setting up firewall rules..."
systemctl stop firewalld
systemctl disable firewalld

# TODO somehow remove and automate this(read from some system config)
MASTER_IP="192.168.56.100"

# 1. create yum repo file

cat > /etc/yum.repos.d/eparis-kubernetes-epel-7.repo << EOF
[eparis-kubernetes-epel-7]
name=Copr repo for kubernetes-epel-7 owned by eparis
baseurl=http://copr-be.cloud.fedoraproject.org/results/eparis/kubernetes-epel-7/epel-7-\$basearch/
skip_if_unavailable=True
gpgcheck=0
enabled=1
EOF

# 2. install components
echo "Installing kubernetes..."
yum -y install kubernetes

# 3. configure minion config
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

# 4. configure minion kubelet

cat > /etc/kubernetes/kubelet << EOF
###
# kubernetes kubelet (minion) config

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