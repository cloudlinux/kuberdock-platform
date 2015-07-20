#!/bin/bash
# install kubernetes components on Node host

KUBERNETES_CONF_DIR=/etc/kubernetes
EXIT_MESSAGE="Installation error."

# SOME HELPERS

check_status()
{
    local temp=$?
    if [ $temp -ne 0 ];then
        echo $EXIT_MESSAGE
        exit $temp
    fi
}

yum_wrapper()
{
    if [ -z "$WITH_TESTING" ];then
        yum --enablerepo=kube $@
    else
        yum --enablerepo=kube,kube-testing $@
    fi
}

echo "Set locale to en_US.UTF-8"
export LANG=en_US.UTF-8
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

rpm -q firewalld && firewall-cmd --state
if [ $? == 0 ];then
    # TODO change rules, not disable
    echo "Setting up firewall rules..."
    systemctl stop firewalld
    check_status
    systemctl disable firewalld
    check_status
fi


# 1. create yum repo file

cat > /etc/yum.repos.d/kube-cloudlinux.repo << EOF
[kube]
name=kube
baseurl=http://repo.cloudlinux.com/kubernetes/x86_64/
enabled=0
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF

# Add kubernetes testing repo
cat > /etc/yum.repos.d/kube-cloudlinux-testing.repo << EOF
[kube-testing]
name=kube-testing
baseurl=http://repo.cloudlinux.com/kubernetes-testing/x86_64/
enabled=0
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF


# 1.1 import CloudLinux key
rpm --import http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
check_status


# 1.2 Install ntp, we need correct time for node logs
yum_wrapper install -y ntp
check_status
systemctl daemon-reload
check_status
ntpd -gq
systemctl restart ntpd
check_status
systemctl enable ntpd
check_status
ntpq -p
if [ $? -ne 0 ];then
    echo "WARNING: ntpq -p exit with error. Maybe some problems with ntpd settings and manual changes needed"
fi


# 2. install components
echo "Installing kubernetes..."
yum_wrapper -y install ${CUR_MASTER_KUBERNETES} flannel-0.4.1 cadvisor docker
check_status

# 3. If amazon instance install aws-cli, epel and jq
AWS=${AWS}
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
check_status

# 4.1 create and populate scripts directory
mkdir -p /var/lib/kuberdock/scripts
check_status
mv /pd.sh /var/lib/kuberdock/scripts/pd.sh
chmod +x /var/lib/kuberdock/scripts/pd.sh
check_status



# 5. configure Node config
echo "Configuring kubernetes..."
sed -i "/^KUBE_MASTER/ {s|http://127.0.0.1:8080|https://${MASTER_IP}:6443|}" $KUBERNETES_CONF_DIR/config
# TODO maybe unneeded and insecure:
sed -i "/^KUBELET_ADDRESS/ {s/127.0.0.1/0.0.0.0/}" $KUBERNETES_CONF_DIR/kubelet
sed -i "/^KUBELET_HOSTNAME/ {s/--hostname_override=127.0.0.1//}" $KUBERNETES_CONF_DIR/kubelet
sed -i "/^KUBELET_API_SERVER/ {s|http://127.0.0.1:8080|https://${MASTER_IP}:6443|}" $KUBERNETES_CONF_DIR/kubelet
sed -i '/^KUBELET_ARGS/ {s|""|"--kubeconfig=/etc/kubernetes/configfile --cadvisor_port=0 --cluster_dns=10.254.0.10 --cluster_domain=kuberdock --register-node=false"|}' $KUBERNETES_CONF_DIR/kubelet
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


echo "Starting Flanneld ..."
rm -f /run/flannel/docker 2>/dev/null
systemctl enable flanneld
check_status
systemctl restart flanneld
check_status



# 7. Setting kernel parameters
sysctl -w net.ipv4.ip_nonlocal_bind=1
sysctl -w net.ipv4.ip_forward=1
check_status
cat > /etc/sysctl.d/75-kuberdock.conf << EOF
net.ipv4.ip_nonlocal_bind = 1
net.ipv4.ip_forward = 1
EOF



# 8. setup rsyslog forwarding
echo "Reconfiguring rsyslog..."
cat > /etc/rsyslog.d/kuberdock.conf << EOF
*.* @127.0.0.1:5140
EOF


echo 'Restarting rsyslog...'
systemctl restart rsyslog
check_status



# 9. prepare things for logging pod

# waiting for flanneld to start.
count=0
while [ ! -f /run/flannel/docker ]
do
  sleep 0.2;
  let "count += 1"
  if [ $count -ge 100 ];then
    echo "Waiting for flanneld longer then 20 seconds. Exiting. $EXIT_MESSAGE"
    exit 1
  fi
done

echo 'Restarting docker...'
# pull images (update if already exists)
systemctl enable docker
check_status
systemctl restart docker
check_status

docker pull kuberdock/fluentd:1.0 > /dev/null 2>&1 &
docker pull kuberdock/elasticsearch:1.0 > /dev/null 2>&1 &

for c in $(docker ps -a | grep 'kuberdock-.*\.file' | awk '{print $1}'); do
  docker rm -f $c > /dev/null 2>&1
done

# fix elasticsearch home directory ownership (if ES was running as service)
if [ -d /var/lib/elasticsearch ]; then
  chown -R root:root /var/lib/elasticsearch
else
  mkdir -p /var/lib/elasticsearch
fi
check_status
chcon -Rt svirt_sandbox_file_t /var/lib/elasticsearch
check_status

if [ ! -d /var/lib/docker/containers ]; then
  mkdir -p /var/lib/docker/containers
fi
chcon -Rt svirt_sandbox_file_t /var/lib/docker/containers
check_status


cat > /var/lib/kuberdock/scripts/modify_ip.sh << 'EOF'
CMD=$1
PUBLIC_IP=$2
IFACE=$3
nmcli g &> /dev/null
if [ $? == 0 ];then
    CONNECTION=$(nmcli -f UUID,DEVICE con | awk "/$IFACE/ {print \$1; exit}")
    if [ -z $CONNECTION ];then
        echo "No connection found for interface $IFACE"
        exit 1
    fi
    if [ $CMD == 'add' ];then
        nmcli con mod "$CONNECTION" +ipv4.addresses "$PUBLIC_IP/32"
    else
        nmcli con mod "$CONNECTION" -ipv4.addresses "$PUBLIC_IP/32"
    fi
fi
ip addr $CMD $PUBLIC_IP/32 dev $IFACE
if [ $CMD == 'add' ];then
    arping -I $IFACE -A $PUBLIC_IP -c 10 -w 1
fi
exit 0
EOF


# 10. enable services
echo "Starting services..."
systemctl enable kubelet
check_status
systemctl restart kubelet
check_status
systemctl enable kube-proxy
check_status
systemctl restart kube-proxy
check_status

CADVISOR_CONF=/etc/sysconfig/cadvisor
sed -i "/^CADVISOR_STORAGE_DRIVER/ {s/\"\"/\"influxdb\"/}" $CADVISOR_CONF
sed -i "/^CADVISOR_STORAGE_DRIVER_HOST/ {s/localhost/${MASTER_IP}/}" $CADVISOR_CONF
systemctl enable cadvisor
check_status
systemctl restart cadvisor
check_status

exit 0
