#!/bin/sh

KUBERDOCK_DIR=/var/opt/kuberdock
KUBERNETES_CONF_DIR=/etc/kubernetes
KUBERDOCK_MAIN_CONFIG=/etc/sysconfig/kuberdock/kuberdock.conf
KNOWN_TOKENS_FILE="$KUBERNETES_CONF_DIR/known_tokens.csv"
WEBAPP_USER=nginx

if [ $USER != "root" ]; then
    echo "Superuser privileges required"
    exit 1
fi

#yesno()
## $1 = Message prompt
## Returns ans=0 for no, ans=1 for yes
#{
#   if [[ $dry_run -eq 1 ]]
#   then
#      echo "Would be asked here if you wanted to"
#      echo "$1 (y/n - y is assumed)"
#      ans=1
#   else
#      ans=2
#   fi
#
#   while [ $ans -eq 2 ]
#   do
#      echo -n "$1 (y/n)? " ; read reply
#      case "$reply" in
#      Y*|y*) ans=1 ;;
#      N*|n*) ans=0 ;;
#          *) echo "Please answer y or n" ;;
#      esac
#   done
#}



# ====== Set initial vars, WILL WRITE THEM AFTER INSTALL kuberdock.rpm =========

#MASTER_IP=$(hostname -i)
#yesno "Is your MASTER IP $MASTER_IP"
#
#if [ ! $ans -eq 1 ]; then
#    read -p "Enter MASTER IP: " MASTER_IP
#    echo "Will use $MASTER_IP"
#fi
#
## TODO make if '' provided than don't use any customizations
#
#NODE_TOBIND_EXTERNAL_IPS="enp0s5"
#yesno "On which node interface to bind external ips? $NODE_TOBIND_EXTERNAL_IPS"
#
#if [ ! $ans -eq 1 ]; then
#    read -p "Enter interface name: " NODE_TOBIND_EXTERNAL_IPS
#    echo "Will use $NODE_TOBIND_EXTERNAL_IPS"
#fi
#
#MASTER_TOBIND_FLANNEL="enp0s5"
#yesno "Interface to bind for Flannel network on master is $MASTER_TOBIND_FLANNEL"
#
#if [ ! $ans -eq 1 ]; then
#    read -p "Enter interface name: " MASTER_TOBIND_FLANNEL
#    echo "Will use $MASTER_TOBIND_FLANNEL"
#fi
#
#NODE_TOBIND_FLANNEL="enp0s5"
#yesno "Interface to bind for Flannel network on nodes(inter-host comminication and with master) is $NODE_TOBIND_FLANNEL"
#
#if [ ! $ans -eq 1 ]; then
#    read -p "Enter interface name: " NODE_TOBIND_FLANNEL
#    echo "Will use $NODE_TOBIND_FLANNEL"
#fi

# ==== More elaborate interfaces setting ====

DEFAULT_IFACE=""
DEFAULT_MASTER_IP=""

DEFAULT_IFACE=$(ip -o link show | awk -F: '$3 ~ /LOWER_UP/ {gsub(/ /, "", $2); if ($2 != "lo"){print $2;exit}}')

read -p "Enter interface for inter-host communication[$DEFAULT_IFACE]: " IFACE
if [ -z "$IFACE" ];then
    IFACE=$DEFAULT_IFACE
fi

if [ -n "$IFACE" ];then
    DEFAULT_MASTER_IP=$(ip -o -4 address show $IFACE|awk 'NR>1 {exit}; /inet/ {sub(/\/.*$/, "", $4); print $4}')
    if [ -n "$DEFAULT_MASTER_IP" ];then
        PROMPT="Enter master IP address [$DEFAULT_MASTER_IP]: "
    else
        PROMPT="Enter master IP address: "
    fi
fi

read -p "$PROMPT" MASTER_IP
if [ -z "$MASTER_IP" ];then
    MASTER_IP=$DEFAULT_MASTER_IP
fi

read -p "Enter a node interface for binding to public IPs [$DEFAULT_IFACE]: " NODE_TOBIND_EXTERNAL_IPS
if [ -z "$NODE_TOBIND_EXTERNAL_IPS" ];then
    NODE_TOBIND_EXTERNAL_IPS=$DEFAULT_IFACE
fi

read -p "Enter master interface for flanneld [$DEFAULT_IFACE]: " MASTER_TOBIND_FLANNEL
if [ -z "$MASTER_TOBIND_FLANNEL" ];then
    MASTER_TOBIND_FLANNEL=$DEFAULT_IFACE
fi

read -p "Enter a node interface for flanneld (inter-host communication) [$DEFAULT_IFACE]: " NODE_TOBIND_FLANNEL
if [ -z "$NODE_TOBIND_FLANNEL" ];then
    NODE_TOBIND_FLANNEL=$DEFAULT_IFACE
fi

# ==============================================================================



#1 Import some keys
rpm --import http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
rpm --import https://dl.fedoraproject.org/pub/epel/RPM-GPG-KEY-EPEL-7
yum -y install epel-release

# TODO we must open what we want instead
echo "WARNING: we stop firewalld!"
systemctl stop firewalld; systemctl disable firewalld

echo "Adding SELinux rule for http on port 9200"
semanage port -a -t http_port_t -p tcp 9200



#2 Install ntp, we need correct time for node logs
yum install -y ntp
ntpd -gq
systemctl start ntpd; systemctl enable ntpd
ntpq -p



#3. Add kubernetes repo
cat > /etc/yum.repos.d/kube-cloudlinux.repo << EOF
[kube]
name=kube
baseurl=http://repo.cloudlinux.com/kubernetes/x86_64/
enabled=1
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF



#4. Install kuberdock
yum -y install kuberdock
if [ $? -ne 0 ];then
    echo "Package in repo not found, trying to install local one"
fi
for p in $(ls kuberdock*.rpm);do
    yum -y install $p
    break
done

#4.1 Fix package path bug
mkdir /var/run/kubernetes || /bin/true
chown kube:kube /var/run/kubernetes

#5 Write settings that hoster enter above (only after yum kuberdock.rpm)
echo "MASTER_IP=$MASTER_IP" >> $KUBERDOCK_MAIN_CONFIG
echo "MASTER_TOBIND_FLANNEL=$MASTER_TOBIND_FLANNEL" >> $KUBERDOCK_MAIN_CONFIG
echo "NODE_TOBIND_EXTERNAL_IPS=$NODE_TOBIND_EXTERNAL_IPS" >> $KUBERDOCK_MAIN_CONFIG
echo "NODE_TOBIND_FLANNEL=$NODE_TOBIND_FLANNEL" >> $KUBERDOCK_MAIN_CONFIG



#6 Setting up etcd
yum -y install etcd-ca
echo "Generating etcd-ca certificates..."
mkdir /etc/pki/etcd
etcd-ca init --passphrase ""
etcd-ca export --insecure --passphrase "" | tar -xf -
mv ca.crt /etc/pki/etcd/
rm -f ca.key.insecure

# first instance of etcd cluster
etcd1=$(hostname -f)
etcd-ca new-cert --ip "127.0.0.1,$MASTER_IP" --passphrase "" $etcd1
etcd-ca sign --passphrase "" $etcd1
etcd-ca export $etcd1 --insecure --passphrase "" | tar -xf -
mv $etcd1.crt /etc/pki/etcd/
mv $etcd1.key.insecure /etc/pki/etcd/$etcd1.key

# generate client's certificate
etcd-ca new-cert --passphrase "" etcd-client
etcd-ca sign --passphrase "" etcd-client
etcd-ca export etcd-client --insecure --passphrase "" | tar -xf -
mv etcd-client.crt /etc/pki/etcd/
mv etcd-client.key.insecure /etc/pki/etcd/etcd-client.key


cat > /etc/systemd/system/etcd.service << EOF
[Unit]
Description=Etcd Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/var/lib/etcd/
EnvironmentFile=-/etc/etcd/etcd.conf
User=etcd
ExecStart=/usr/bin/etcd \
    --name \${ETCD_NAME} \
    --data-dir \${ETCD_DATA_DIR} \
    --listen-client-urls \${ETCD_LISTEN_CLIENT_URLS} \
    --advertise-client-urls \${ETCD_ADVERTISE_CLIENT_URLS} \
    --ca-file \${ETCD_CA_FILE} \
    --cert-file \${ETCD_CERT_FILE} \
    --key-file \${ETCD_KEY_FILE}

[Install]
WantedBy=multi-user.target
EOF


cat > /etc/etcd/etcd.conf << EOF
# [member]
ETCD_NAME=default
ETCD_DATA_DIR="/var/lib/etcd/default.etcd"
#ETCD_SNAPSHOT_COUNTER="10000"
#ETCD_HEARTBEAT_INTERVAL="100"
#ETCD_ELECTION_TIMEOUT="1000"
#ETCD_LISTEN_PEER_URLS="http://localhost:2380,http://localhost:7001"
ETCD_LISTEN_CLIENT_URLS="https://0.0.0.0:2379,http://127.0.0.1:4001"
#ETCD_MAX_SNAPSHOTS="5"
#ETCD_MAX_WALS="5"
#ETCD_CORS=""
#
#[cluster]
#ETCD_INITIAL_ADVERTISE_PEER_URLS="http://localhost:2380,http://localhost:7001"
# if you use different ETCD_NAME (e.g. test), set ETCD_INITIAL_CLUSTER value for this name, i.e. "test=http://..."
#ETCD_INITIAL_CLUSTER="default=http://localhost:2380,default=http://localhost:7001"
#ETCD_INITIAL_CLUSTER_STATE="new"
#ETCD_INITIAL_CLUSTER_TOKEN="etcd-cluster"
ETCD_ADVERTISE_CLIENT_URLS="https://0.0.0.0:2379,http://127.0.0.1:4001"
#ETCD_DISCOVERY=""
#ETCD_DISCOVERY_SRV=""
#ETCD_DISCOVERY_FALLBACK="proxy"
#ETCD_DISCOVERY_PROXY=""
#
#[proxy]
#ETCD_PROXY="off"
#
#[security]
ETCD_CA_FILE="/etc/pki/etcd/ca.crt"
ETCD_CERT_FILE="/etc/pki/etcd/$etcd1.crt"
ETCD_KEY_FILE="/etc/pki/etcd/$etcd1.key"
#ETCD_PEER_CA_FILE=""
#ETCD_PEER_CERT_FILE=""
#ETCD_PEER_KEY_FILE=""
EOF


#7 Start as early as possible, because Flannel need it
echo "Starting etcd..."
systemctl enable etcd
systemctl restart etcd



# Start early or curl connection refused
systemctl enable influxdb > /dev/null 2>&1
systemctl restart influxdb



#8 Generate a shared secret (bearer token) to
# apiserver and kubelet so that kubelet can authenticate to
# apiserver to send events.
kubelet_token=$(cat /dev/urandom | base64 | tr -d "=+/" | dd bs=32 count=1 2> /dev/null)
(umask u=rw,go= ; echo "$kubelet_token,kubelet,kubelet" > $KNOWN_TOKENS_FILE)
# Kubernetes need to read it
chown kube:kube $KNOWN_TOKENS_FILE
(umask u=rw,go= ; echo "{\"BearerToken\": \"$kubelet_token\", \"Insecure\": true }" > $KUBERNETES_CONF_DIR/kubelet_token.dat)
# To send it to nodes we need to read it
chown $WEBAPP_USER $KUBERNETES_CONF_DIR/kubelet_token.dat



#9. Configure kubernetes
sed -i "/^KUBE_API_ARGS/ {s|\"\"|\"--token_auth_file=$KNOWN_TOKENS_FILE --public_address_override=$MASTER_IP\"|}" $KUBERNETES_CONF_DIR/apiserver
# This plugins enabled by default
# sed -i "/^KUBE_ADMISSION_CONTROL/ {s|--admission_control=NamespaceAutoProvision,LimitRanger,ResourceQuota||}" $KUBERNETES_CONF_DIR/apiserver
sed -i "/^KUBELET_ADDRESSES/ {s/--machines=127.0.0.1//}" $KUBERNETES_CONF_DIR/controller-manager



#10. Create and populate DB
systemctl enable postgresql
postgresql-setup initdb
systemctl restart postgresql
python $KUBERDOCK_DIR/postgresql_setup.py
systemctl restart postgresql
cd $KUBERDOCK_DIR
python createdb.py



#11. Start services
systemctl enable redis
systemctl restart redis



#12 Flannel
echo "Setuping flannel config to etcd..."
etcdctl mk /kuberdock/network/config '{"Network":"10.254.0.0/16", "SubnetLen": 24, "Backend": {"Type": "host-gw"}}' 2> /dev/null
etcdctl get /kuberdock/network/config



#13 Setuping Flannel on master ==========================================
# Only on master flannel can use non https connection
cat > /etc/sysconfig/flanneld << EOF
# Flanneld configuration options

# etcd url location.  Point this to the server where etcd runs
FLANNEL_ETCD="http://127.0.0.1:4001"

# etcd config key.  This is the configuration key that flannel queries
# For address range assignment
FLANNEL_ETCD_KEY="/kuberdock/network/"

# Any additional options that you want to pass
FLANNEL_OPTIONS="--iface=$MASTER_TOBIND_FLANNEL"
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



#14 Create cadvisor database
# Only after influxdb is fully loaded
curl -X POST 'http://localhost:8086/db?u=root&p=root' -d '{"name": "cadvisor"}'



#15. Starting kubernetes
echo "Starting kubernetes..."
for i in kube-apiserver kube-controller-manager kube-scheduler;do systemctl enable $i;done
for i in kube-apiserver kube-controller-manager kube-scheduler;do systemctl restart $i;done



#16. Starting web-interface
echo "Starting kuberdock web-interface..."
systemctl enable emperor.uwsgi
systemctl restart emperor.uwsgi

systemctl enable nginx
systemctl restart nginx



#17. Setup cluster DNS
echo "Setupping cluster DNS"

cat << EOF | kubectl create -f -
apiVersion: v1beta3
kind: Pod
metadata:
  labels:
    name: kuberdock-dns
  name: kuberdock-dns
spec:
  containers:
  - args:
    - -listen-client-urls=http://0.0.0.0:2379,http://0.0.0.0:4001
    - -initial-cluster-token=skydns-etcd
    - -advertise-client-urls=http://127.0.0.1:4001
    image: quay.io/coreos/etcd:v2.0.3
    name: etcd
    resources:
      limits:
        memory: 64Mi
  - args:
    - -domain=kuberdock
    image: gcr.io/google-containers/kube2sky:1.1
    name: kube2sky
    resources:
      limits:
        memory: 64Mi
  - args:
    - -machines=http://127.0.0.1:4001
    - -addr=0.0.0.0:53
    - -domain=kuberdock.
    image: gcr.io/google-containers/skydns:2015-03-11-001
    name: skydns
    ports:
    - containerPort: 53
      protocol: udp
    resources:
      limits:
        memory: 64Mi
EOF

cat << EOF | kubectl create -f -
apiVersion: v1beta3
kind: Service
metadata:
  annotations:
    public-ip-state: '{"assigned-public-ip": null}'
  labels:
    name: kuberdock-dns
  name: kuberdock-dns
spec:
  portalIP: 10.254.0.10
  ports:
  - name: ""
    port: 53
    protocol: UDP
    targetPort: 53
  selector:
    name: kuberdock-dns
EOF

# 19. Create root ssh keys if missing and copy'em  to WEBAPP_USER homedir
ENT=$(getent passwd $WEBAPP_USER)
if [ -z "$ENT" ]; then
    echo "User $WEBAPP_USER does not exist"
    exit 1
fi

KEY=id_rsa
TGT_HOME=$(echo $ENT | cut -d: -f6)
TGT_DIR=$TGT_HOME/.ssh
TGT_PATH=$TGT_DIR/$KEY

if [ ! -d $TGT_DIR ];then
    mkdir -p $TGT_DIR
fi

if [ ! -e $TGT_PATH ]; then
    ssh-keygen -N "" -f $TGT_PATH
fi

chown -R $WEBAPP_USER.$WEBAPP_USER $TGT_DIR

# ======================================================================
echo "WARNING: Firewalld was disabled. You need to configure it to work right"
echo "WARNING: $WEBAPP_USER need ssh access to nodes as 'root'"
echo "We will use $TGT_PATH Please, copy it to all your nodes with ssh-copy-id"
echo "Installation Completed. KuberDock is available at https://$MASTER_IP/"
