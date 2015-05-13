#!/bin/bash

KUBERDOCK_DIR=/var/opt/kuberdock
KUBERNETES_CONF_DIR=/etc/kubernetes
KUBERDOCK_MAIN_CONFIG=/etc/sysconfig/kuberdock/kuberdock.conf
KNOWN_TOKENS_FILE="$KUBERNETES_CONF_DIR/known_tokens.csv"
WEBAPP_USER=nginx
DEPLOY_LOG_FILE=/var/tmp/kuberdock_master_deploy.log
EXIT_MESSAGE="Installation error. Install log saved to $DEPLOY_LOG_FILE"

if [ $USER != "root" ]; then
    echo "Superuser privileges required" | tee -a $DEPLOY_LOG_FILE
    exit 1
fi


# SOME HELPERS
do_and_log()
# Log all output to LOG-file and screen, and stop script on error
{
    "$@" 2>&1 | tee -a $DEPLOY_LOG_FILE
    temp=$PIPESTATUS
    if [ $temp -ne 0 ];then
      echo $EXIT_MESSAGE
      exit $temp
    fi
}

log_errors()
# Log only stderr to LOG-file, and stop script on error
{
    echo "Doing $@" >> $DEPLOY_LOG_FILE
    "$@" 2> >(tee -a $DEPLOY_LOG_FILE)
    temp=$PIPESTATUS
    if [ $temp -ne 0 ];then
      echo $EXIT_MESSAGE
      exit $temp
    fi
}

log_it()
# Just log all output to LOG-file and screen
{
    "$@" 2>&1 | tee -a $DEPLOY_LOG_FILE
    return $PIPESTATUS
}

get_network()
# get network by ip
{
    local temp=$(ip -o ad | awk "/$1/ {print \$4}")
    if [ -z "$temp" ];then
        return 1
    fi
    local temp2=$(ipcalc $temp -n -p)
    if [ $? -ne 0 ];then
        return 2
    else
        eval $temp2
        echo "$NETWORK/$PREFIX"
    fi
    return 0
}

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

# Get number of interfaces up
IFACE_NUM=$(ip -o link show | awk -F: '$3 ~ /LOWER_UP/ {gsub(/ /, "", $2); if ($2 != "lo"){print $2;}}'|wc -l)

MASTER_TOBIND_FLANNEL=""
MASTER_IP=""

if [ $IFACE_NUM -eq 0 ]; then    # no working interfaces found...
    read -p "No interfaces found. Enter inner network interface IP: " MASTER_IP
    if [ -z "$MASTER_IP" ]; then
        log_it echo "No IP addresses obtained. Exit"
        exit 1
    fi
else
    # get first interface from found ones
    FIRST_IFACE=$(ip -o link show | awk -F: '$3 ~ /LOWER_UP/ {gsub(/ /, "", $2); if ($2 != "lo"){print $2;exit}}')

    # get this interface ip address
    FIRST_IP=$(ip -o -4 address show $FIRST_IFACE|awk '/inet/ {sub(/\/.*$/, "", $4); print $4;exit;}')

    # read user confirmation
    read -p "Enter inner network interface IP address [$FIRST_IP]: " MASTER_IP
    if [ -z "$MASTER_IP" ]; then
        MASTER_IP=$FIRST_IP
        MASTER_TOBIND_FLANNEL=$FIRST_IFACE
    else
        MASTER_TOBIND_FLANNEL=$(ip -o -4 address show| awk "{sub(/\/.*\$/, \"\", \$4); if(\$4==\"$MASTER_IP\"){print \$2;exit}}")
    fi
fi

# if entered ip not found or invalid
if [ -z "$MASTER_TOBIND_FLANNEL" ]; then
    log_it echo "No IP addresses obtained. Exit"
    exit 1
fi

echo "MASTER_IP has been set to $MASTER_IP" >> $DEPLOY_LOG_FILE
echo "MASTER_TOBIND_FLANNEL was set to $MASTER_TOBIND_FLANNEL" >> $DEPLOY_LOG_FILE

# We question here for a node interface to bind external IPs to
read -p "Enter interface to bind public IP addresses on nodes [$MASTER_TOBIND_FLANNEL]: " NODE_TOBIND_EXTERNAL_IPS
if [ -z "$NODE_TOBIND_EXTERNAL_IPS" ]; then
    NODE_TOBIND_EXTERNAL_IPS=$MASTER_TOBIND_FLANNEL
fi

# Just a workaround for compatibility
NODE_TOBIND_FLANNEL=$MASTER_TOBIND_FLANNEL


# Workaround for CentOS 7 minimal CD bug.
# https://github.com/GoogleCloudPlatform/kubernetes/issues/5243#issuecomment-78080787
SWITCH=`cat /etc/nsswitch.conf | grep "^hosts:"`
if [ -z "$SWITCH" ];then
    log_it echo "WARNING: Can't find \"hosts:\" line in /etc/nsswitch.conf"
    log_it echo "Please, modify it to include \"myhostname\" at \"hosts:\" line"
else
    if [[ ! $SWITCH == *"myhostname"* ]];then
        sed -i "/^hosts:/ {s/$SWITCH/$SWITCH myhostname/}" /etc/nsswitch.conf
        log_it echo 'We modify your /etc/nsswitch.conf to include "myhostname" at "hosts:" line'
    fi
fi



#1 Import some keys
do_and_log rpm --import http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
do_and_log rpm --import https://dl.fedoraproject.org/pub/epel/RPM-GPG-KEY-EPEL-7
log_errors yum -y install epel-release


CLUSTER_NETWORK=$(get_network $MASTER_IP)
if [ $? -ne 0 ];then
    log_it echo "Error during get cluster network via $MASTER_IP"
    echo $EXIT_MESSAGE
    exit 1
fi
log_it echo "CLUSTER_NETWORK has been determined as $CLUSTER_NETWORK"


log_it firewall-cmd --state
if [ $? -ne 0 ];then
    log_it echo 'Firewalld is not running. Skip adding any new rules.'
else
    log_it echo 'Adding Firewalld rules...'
    # nginx
    do_and_log firewall-cmd --permanent --zone=public --add-port=80/tcp
    do_and_log firewall-cmd --permanent --zone=public --add-port=443/tcp

    # this ports should be seen only from inside the cluster:
    log_it echo 'Adding cluster-only visible ports...'
    # kube-apiserver insecure ro
    do_and_log firewall-cmd --permanent --zone=public --add-rich-rule="rule family="ipv4" source address=$CLUSTER_NETWORK port port="7080" protocol="tcp" accept"
    # influxdb
    do_and_log firewall-cmd --permanent --zone=public --add-rich-rule="rule family="ipv4" source address=$CLUSTER_NETWORK port port="8086" protocol="tcp" accept"
    # cluster dns
    do_and_log firewall-cmd --permanent --zone=public --add-rich-rule="rule family="ipv4" source address=$CLUSTER_NETWORK port port="53" protocol="tcp" accept"

    # kube-apiserver secure
    do_and_log firewall-cmd --permanent --zone=public --add-port=6443/tcp
    # etcd secure
    do_and_log firewall-cmd --permanent --zone=public --add-port=2379/tcp

    log_it echo 'Reload firewall...'
    do_and_log firewall-cmd --reload
fi


#2 Install ntp, we need correct time for node logs
log_errors yum install -y ntp
do_and_log ntpd -g
do_and_log systemctl restart ntpd
do_and_log systemctl enable ntpd
do_and_log ntpq -p



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
PACKAGE=$(ls -1 |awk '/kuberdock.*\.rpm/ {print $1; exit}')
if [ ! -z $PACKAGE ];then
    log_errors yum -y install $PACKAGE
fi
log_errors yum -y install kuberdock

#4.1 Fix package path bug
mkdir /var/run/kubernetes || /bin/true
do_and_log chown kube:kube /var/run/kubernetes


#4.2 SELinux rules
# After kuberdock, we need installed semanage
log_it echo 'Adding SELinux rule for http on port 9200'
do_and_log semanage port -a -t http_port_t -p tcp 9200



#5 Write settings that hoster enter above (only after yum kuberdock.rpm)
echo "MASTER_IP=$MASTER_IP" >> $KUBERDOCK_MAIN_CONFIG
echo "MASTER_TOBIND_FLANNEL=$MASTER_TOBIND_FLANNEL" >> $KUBERDOCK_MAIN_CONFIG
echo "NODE_TOBIND_EXTERNAL_IPS=$NODE_TOBIND_EXTERNAL_IPS" >> $KUBERDOCK_MAIN_CONFIG
echo "NODE_TOBIND_FLANNEL=$NODE_TOBIND_FLANNEL" >> $KUBERDOCK_MAIN_CONFIG



#6 Setting up etcd
log_errors yum -y install etcd-ca
log_it echo 'Generating etcd-ca certificates...'
do_and_log mkdir /etc/pki/etcd
etcd-ca init --passphrase ""
etcd-ca export --insecure --passphrase "" | tar -xf -
do_and_log mv ca.crt /etc/pki/etcd/
do_and_log rm -f ca.key.insecure

# first instance of etcd cluster
etcd1=$(hostname -f)
etcd-ca new-cert --ip "127.0.0.1,$MASTER_IP" --passphrase "" $etcd1
etcd-ca sign --passphrase "" $etcd1
etcd-ca export $etcd1 --insecure --passphrase "" | tar -xf -
do_and_log mv $etcd1.crt /etc/pki/etcd/
do_and_log mv $etcd1.key.insecure /etc/pki/etcd/$etcd1.key

# generate client's certificate
etcd-ca new-cert --passphrase "" etcd-client
etcd-ca sign --passphrase "" etcd-client
etcd-ca export etcd-client --insecure --passphrase "" | tar -xf -
do_and_log mv etcd-client.crt /etc/pki/etcd/
do_and_log mv etcd-client.key.insecure /etc/pki/etcd/etcd-client.key


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
log_it echo 'Starting etcd...'
do_and_log systemctl enable etcd
do_and_log systemctl restart etcd



# Start early or curl connection refused
do_and_log systemctl enable influxdb
do_and_log systemctl restart influxdb



#8 Generate a shared secret (bearer token) to
# apiserver and kubelet so that kubelet can authenticate to
# apiserver to send events.
log_it echo 'Generate a bearer token'
kubelet_token=$(cat /dev/urandom | base64 | tr -d "=+/" | dd bs=32 count=1 2> /dev/null)
(umask u=rw,go= ; echo "$kubelet_token,kubelet,kubelet" > $KNOWN_TOKENS_FILE)
# Kubernetes need to read it
chown kube:kube $KNOWN_TOKENS_FILE
(umask u=rw,go= ; echo "{\"BearerToken\": \"$kubelet_token\", \"Insecure\": true }" > $KUBERNETES_CONF_DIR/kubelet_token.dat)
# To send it to nodes we need to read it
chown $WEBAPP_USER $KUBERNETES_CONF_DIR/kubelet_token.dat



#9. Configure kubernetes
log_it echo "Configure kubernetes"
sed -i "/^KUBE_API_ARGS/ {s|\"\"|\"--token_auth_file=$KNOWN_TOKENS_FILE --public_address_override=$MASTER_IP\"|}" $KUBERNETES_CONF_DIR/apiserver
# This plugins enabled by default
# sed -i "/^KUBE_ADMISSION_CONTROL/ {s|--admission_control=NamespaceAutoProvision,LimitRanger,ResourceQuota||}" $KUBERNETES_CONF_DIR/apiserver
sed -i "/^KUBELET_ADDRESSES/ {s/--machines=127.0.0.1//}" $KUBERNETES_CONF_DIR/controller-manager



#10. Create and populate DB
log_it echo 'Create and populate DB'
do_and_log systemctl enable postgresql
do_and_log postgresql-setup initdb
do_and_log systemctl restart postgresql
do_and_log python $KUBERDOCK_DIR/postgresql_setup.py
do_and_log systemctl restart postgresql
cd $KUBERDOCK_DIR
do_and_log python createdb.py



#11. Start services
do_and_log systemctl enable redis
do_and_log systemctl restart redis



#12 Flannel
log_it echo "Setuping flannel config to etcd..."
etcdctl mk /kuberdock/network/config '{"Network":"10.254.0.0/16", "SubnetLen": 24, "Backend": {"Type": "host-gw"}}' 2> /dev/null
do_and_log etcdctl get /kuberdock/network/config



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

log_it echo "Starting flannel..."
do_and_log systemctl enable flanneld
do_and_log systemctl restart flanneld

log_it echo "Adding bridge to flannel network..."
do_and_log source /run/flannel/subnet.env

# with host-gw backend we don't have to change MTU (bridge.mtu)
# If we have working NetworkManager we can just
#nmcli -n c delete kuberdock-flannel-br0 &> /dev/null
#nmcli -n connection add type bridge ifname br0 con-name kuberdock-flannel-br0 ip4 $FLANNEL_SUBNET

log_errors yum -y install bridge-utils

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

log_it echo "Starting bridge..."
do_and_log ifdown br0
do_and_log ifup br0
#========================================================================



do_and_log systemctl enable dnsmasq
do_and_log systemctl restart dnsmasq



#14 Create cadvisor database
# Only after influxdb is fully loaded
curl -X POST 'http://localhost:8086/db?u=root&p=root' -d '{"name": "cadvisor"}'
if [ $? -ne 0 ];then
    log_it echo "Error create cadvisor database"
    echo $EXIT_MESSAGE
    exit 1
fi



#15. Starting kubernetes
log_it echo "Starting kubernetes..."
for i in kube-apiserver kube-controller-manager kube-scheduler;
    do do_and_log systemctl enable $i;done
for i in kube-apiserver kube-controller-manager kube-scheduler;
    do do_and_log systemctl restart $i;done



#16. Starting web-interface
log_it echo "Starting kuberdock web-interface..."
do_and_log systemctl enable emperor.uwsgi
do_and_log systemctl restart emperor.uwsgi

do_and_log systemctl enable nginx
do_and_log systemctl restart nginx



#17. Setup cluster DNS
log_it echo "Setupping cluster DNS"

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
    log_it echo "User $WEBAPP_USER does not exist"
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
    log_it echo "Trying to generate ssh-key..."
    ssh-keygen -N '' -f $TGT_PATH
    if [ $? -ne 0 ];then
        log_it echo "Error during generating ssh-key"
        echo $EXIT_MESSAGE
        exit 1
    fi
    log_it echo "Generated new key: $TGT_PATH"
fi

do_and_log chown -R $WEBAPP_USER.$WEBAPP_USER $TGT_DIR

# ======================================================================
log_it echo "WARNING: Firewalld will be disabled on nodes. Will use iptables instead"
log_it echo "WARNING: $WEBAPP_USER need ssh access to nodes as 'root'"
log_it echo "Will be used $TGT_PATH Please, copy it to all your nodes with command like this:"
log_it echo "ssh-copy-id -i $TGT_PATH.pub root@your_node"
log_it echo "Installation completed and log saved to $DEPLOY_LOG_FILE"
log_it echo "KuberDock is available at https://$MASTER_IP/"
