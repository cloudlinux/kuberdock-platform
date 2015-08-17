#!/bin/bash

KUBERDOCK_DIR=/var/opt/kuberdock
KUBERNETES_CONF_DIR=/etc/kubernetes
KUBERDOCK_MAIN_CONFIG=/etc/sysconfig/kuberdock/kuberdock.conf
KNOWN_TOKENS_FILE="$KUBERNETES_CONF_DIR/known_tokens.csv"
WEBAPP_USER=nginx
DEPLOY_LOG_FILE=/var/log/kuberdock_master_deploy.log
EXIT_MESSAGE="Installation error. Install log saved to $DEPLOY_LOG_FILE"

if [ $USER != "root" ]; then
    echo "Superuser privileges required" | tee -a $DEPLOY_LOG_FILE
    exit 1
fi


# Parse args


CONF_FLANNEL_BACKEND='host-gw'
while [[ $# > 0 ]];do
    key="$1"
    case $key in
        -c|--cleanup)
        CLEANUP=yes
        ;;
        -t|--testing)
        WITH_TESTING=yes
        ;;
        -u|--udp-backend)
        CONF_FLANNEL_BACKEND=udp
        ;;
        *)
        echo "Unknown option: $key"
        exit 1
        ;;
    esac
    shift # past argument or value
done


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


ISAMAZON=false
check_amazon()
{
    log_it echo "Checking AWS..."
    if [[ ! -z $(curl --connect-timeout 1 -s http://169.254.169.254/latest/) ]];then
      ISAMAZON=true
      log_it echo "Looks like we are on AWS."
    else
      log_it echo "Not on AWS."
    fi
}
check_amazon

yum_wrapper()
{
    if [ -z "$WITH_TESTING" ];then
        log_errors yum --enablerepo=kube $@
    else
        log_errors yum --enablerepo=kube,kube-testing $@
    fi
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

##########
# Deploy #
##########


do_deploy()
{

if [ "$ISAMAZON" = true ] && [ -z "$ROUTE_TABLE_ID" ];then
    echo "ROUTE_TABLE_ID as envvar is expected for AWS setup"
    exit 1
fi

log_it echo "Flannel backend has been set to $CONF_FLANNEL_BACKEND"

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
    if [ "$ISAMAZON" = true ];then
        MASTER_IP=$FIRST_IP
        MASTER_TOBIND_FLANNEL=$FIRST_IFACE
    else
        read -p "Enter inner network interface IP address [$FIRST_IP]: " MASTER_IP
        if [ -z "$MASTER_IP" ]; then
            MASTER_IP=$FIRST_IP
            MASTER_TOBIND_FLANNEL=$FIRST_IFACE
        else
            MASTER_TOBIND_FLANNEL=$(ip -o -4 address show| awk "{sub(/\/.*\$/, \"\", \$4); if(\$4==\"$MASTER_IP\"){print \$2;exit}}")
        fi
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
if [ "$ISAMAZON" = true ];then
    NODE_TOBIND_EXTERNAL_IPS=$MASTER_TOBIND_FLANNEL
else
    read -p "Enter interface to bind public IP addresses on nodes [$MASTER_TOBIND_FLANNEL]: " NODE_TOBIND_EXTERNAL_IPS
    if [ -z "$NODE_TOBIND_EXTERNAL_IPS" ]; then
        NODE_TOBIND_EXTERNAL_IPS=$MASTER_TOBIND_FLANNEL
    fi
fi

# Just a workaround for compatibility
NODE_TOBIND_FLANNEL=$MASTER_TOBIND_FLANNEL

HAS_CEPH=no

if [ "$ISAMAZON" = true ];then
    AVAILABILITY_ZONE=$(curl -s connect-timeout 1 http://169.254.169.254/latest/meta-data/placement/availability-zone)
    REGION=$(echo $AVAILABILITY_ZONE|sed 's/\([0-9][0-9]*\)[a-z]*$/\1/')
    if [ -z "$AWS_ACCESS_KEY_ID" ];then
        read -p "Enter your AWS ACCESS KEY ID: " AWS_ACCESS_KEY_ID
    fi
    if [ -z "$AWS_SECRET_ACCESS_KEY" ];then
        read -p "Enter your AWS SECRET ACCESS KEY: " AWS_SECRET_ACCESS_KEY
    fi
    if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ];then
        log_it echo "Either AWS ACCESS KEY ID or AWS SECRET ACCESS KEY missing. Exit"
        exit 1
    fi
else
    while true;do
        read -p "Do you have ceph (yes/no)? [no]: " HAS_CEPH
        if [ -z "$HAS_CEPH" ];then
            HAS_CEPH=no
            break
        fi
        if [ "$HAS_CEPH" = yes ];then
            break
        fi
        if [ "$HAS_CEPH" = no ];then
            break
        fi
    done
fi


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


#1 Add kubernetes repo
cat > /etc/yum.repos.d/kube-cloudlinux.repo << EOF
[kube]
name=kube
baseurl=http://repo.cloudlinux.com/kubernetes/x86_64/
enabled=0
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF


#1.1 Add kubernetes testing repo
cat > /etc/yum.repos.d/kube-cloudlinux-testing.repo << EOF
[kube-testing]
name=kube-testing
baseurl=http://repo.cloudlinux.com/kubernetes-testing/x86_64/
enabled=0
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF


#2 Import some keys
do_and_log rpm --import http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
do_and_log rpm --import https://dl.fedoraproject.org/pub/epel/RPM-GPG-KEY-EPEL-7
yum_wrapper -y install epel-release


CLUSTER_NETWORK=$(get_network $MASTER_IP)
if [ $? -ne 0 ];then
    log_it echo "Error during get cluster network via $MASTER_IP"
    echo $EXIT_MESSAGE
    exit 1
fi
log_it echo "CLUSTER_NETWORK has been determined as $CLUSTER_NETWORK"


log_it rpm -q firewalld && firewall-cmd --state
if [ $? -ne 0 ];then
    log_it echo 'Firewalld is not running. Skip adding any new rules.'
else
    log_it echo 'Adding Firewalld rules...'
    # nginx
    do_and_log firewall-cmd --permanent --zone=public --add-port=80/tcp
    do_and_log firewall-cmd --permanent --zone=public --add-port=443/tcp

    # ntp
    do_and_log firewall-cmd --permanent --zone=public --add-port=123/udp

    # this ports should be seen only from inside the cluster:
    log_it echo 'Adding cluster-only visible ports...'
    # kube-apiserver insecure ro
    do_and_log firewall-cmd --permanent --zone=public --add-rich-rule="rule family="ipv4" source address=$CLUSTER_NETWORK port port="7080" protocol="tcp" accept"
    # influxdb
    do_and_log firewall-cmd --permanent --zone=public --add-rich-rule="rule family="ipv4" source address=$CLUSTER_NETWORK port port="8086" protocol="tcp" accept"
    # cluster dns
    do_and_log firewall-cmd --permanent --zone=public --add-rich-rule="rule family="ipv4" source address=$CLUSTER_NETWORK port port="53" protocol="tcp" accept"
    do_and_log firewall-cmd --permanent --zone=public --add-rich-rule="rule family="ipv4" source address=$CLUSTER_NETWORK port port="53" protocol="udp" accept"

    # kube-apiserver secure
    do_and_log firewall-cmd --permanent --zone=public --add-port=6443/tcp
    # etcd secure
    do_and_log firewall-cmd --permanent --zone=public --add-port=2379/tcp

    # open ports for cpanel flannel and kube-proxy
    do_and_log firewall-cmd --permanent --zone=public --add-port=8123/tcp
    do_and_log firewall-cmd --permanent --zone=public --add-port=8118/tcp

    log_it echo 'Reload firewall...'
    do_and_log firewall-cmd --reload
fi



# 3 Install ntp, we need correct time for node logs
# for now, etcd-ca and bridge-utils needed during deploy only
yum_wrapper install -y ntp etcd-ca bridge-utils
do_and_log systemctl daemon-reload
log_it ntpd -gq
do_and_log systemctl restart ntpd
do_and_log systemctl enable ntpd
do_and_log ntpq -p



#4. Install kuberdock
PACKAGE=$(ls -1 |awk '/kuberdock.*\.rpm/ {print $1; exit}')
if [ ! -z $PACKAGE ];then
    log_it echo 'WARNING: Installation from local package. Using repository is strongly recommended.'
    log_it echo 'To do this just move kuberdock package file to any other dir from deploy script.'
    yum_wrapper -y install $PACKAGE
else
    yum_wrapper -y install kuberdock
fi

#4.1 Fix package path bug
mkdir /var/run/kubernetes || /bin/true
do_and_log chown kube:kube /var/run/kubernetes


#4.2 SELinux rules
# After kuberdock, we need installed semanage
SESTATUS=$(sestatus|awk '/SELinux\sstatus/ {print $3}')
if [ "$SESTATUS" != disabled ];then
    log_it echo 'Adding SELinux rule for http on port 9200'
    do_and_log semanage port -a -t http_port_t -p tcp 9200
fi



#5 Write settings that hoster enter above (only after yum kuberdock.rpm)
echo "MASTER_IP=$MASTER_IP" >> $KUBERDOCK_MAIN_CONFIG
echo "MASTER_TOBIND_FLANNEL=$MASTER_TOBIND_FLANNEL" >> $KUBERDOCK_MAIN_CONFIG
echo "NODE_TOBIND_EXTERNAL_IPS=$NODE_TOBIND_EXTERNAL_IPS" >> $KUBERDOCK_MAIN_CONFIG
echo "NODE_TOBIND_FLANNEL=$NODE_TOBIND_FLANNEL" >> $KUBERDOCK_MAIN_CONFIG



#6 Setting up etcd
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

cat > $KUBERNETES_CONF_DIR/configfile_for_nodes << EOF
apiVersion: v1
kind: Config
users:
- name: kubelet
  user:
    token: $kubelet_token
clusters:
- name: local
  cluster:
     server: https://$MASTER_IP:6443
     insecure-skip-tls-verify: true
contexts:
- context:
    cluster: local
    user: kubelet
  name: onlycontext
current-context: onlycontext
EOF

# To send it to nodes we need to read it
chown $WEBAPP_USER $KUBERNETES_CONF_DIR/configfile_for_nodes
chmod 600 $KUBERNETES_CONF_DIR/configfile_for_nodes



#9. Configure kubernetes
log_it echo "Configure kubernetes"
sed -i "/^KUBE_API_ARGS/ {s|\"\"|\"--token_auth_file=$KNOWN_TOKENS_FILE --bind-address=$MASTER_IP\"|}" $KUBERNETES_CONF_DIR/apiserver
sed -i "/^KUBE_ADMISSION_CONTROL/ {s|--admission_control=NamespaceLifecycle,NamespaceExists,LimitRanger,SecurityContextDeny,ServiceAccount,ResourceQuota|--admission_control=NamespaceLifecycle,NamespaceExists,SecurityContextDeny|}" $KUBERNETES_CONF_DIR/apiserver



#10. Create and populate DB
log_it echo 'Create and populate DB'
cp /usr/lib/systemd/system/postgresql.service /etc/systemd/system/postgresql.service
sed -i "/^ExecStart=/ {s/-t 300/-t 900/}" /etc/systemd/system/postgresql.service
sed -i "/^TimeoutSec=/ {s/300/900/}" /etc/systemd/system/postgresql.service
sed -i "/^After=/ {s/After=network.target/After=network.target\nBefore=emperor.uwsgi.service/}" /etc/systemd/system/postgresql.service
do_and_log systemctl enable postgresql
log_it postgresql-setup initdb  # may fail, if postgres data dir is not empty (it's ok)
do_and_log systemctl restart postgresql
do_and_log python $KUBERDOCK_DIR/postgresql_setup.py
do_and_log systemctl restart postgresql
cd $KUBERDOCK_DIR
ADMIN_PASSWORD="CHANGE_ME"
ADMIN_PASSWORD=$(tr -dc 'A-Za-z0-9-_*' < /dev/urandom | head -c10)
do_and_log python manage.py createdb $ADMIN_PASSWORD



#11. Start services
do_and_log systemctl enable redis
do_and_log systemctl restart redis



#12 Flannel
log_it echo "Setuping flannel config to etcd..."

# This must be same as cluster network (ex. Portal_net):
CONF_FLANNEL_NET=10.254.0.0/16
CONF_FLANNEL_SUBNET_LEN=24

if [ "$ISAMAZON" = true ];then
    # host-gw don't work on AWS so we use aws-vpc
    etcdctl mk /kuberdock/network/config "{\"Network\":\"$CONF_FLANNEL_NET\", \"SubnetLen\": $CONF_FLANNEL_SUBNET_LEN, \"Backend\": {\"Type\": \"aws-vpc\", \"RouteTableID\": \"$ROUTE_TABLE_ID\"}}" 2> /dev/null
else
    etcdctl mk /kuberdock/network/config "{\"Network\":\"$CONF_FLANNEL_NET\", \"SubnetLen\": $CONF_FLANNEL_SUBNET_LEN, \"Backend\": {\"Type\": \"$CONF_FLANNEL_BACKEND\"}}" 2> /dev/null
fi
do_and_log etcdctl get /kuberdock/network/config



#13 Setuping Flannel on master ==========================================
log_it echo "Configuring Flannel..."
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

cp /usr/lib/systemd/system/flanneld.service /etc/systemd/system/flanneld.service
sed -i "/^\[Service\]/a Restart=always\nRestartSec=10" /etc/systemd/system/flanneld.service


log_it echo "Starting flannel..."
do_and_log systemctl enable flanneld
do_and_log systemctl restart flanneld

log_it echo "Adding bridge to flannel network..."
do_and_log source /run/flannel/subnet.env

# with host-gw backend we don't have to change MTU (bridge.mtu)
# If we have working NetworkManager we can just
#nmcli -n c delete kuberdock-flannel-br0 &> /dev/null
#nmcli -n connection add type bridge ifname br0 con-name kuberdock-flannel-br0 ip4 $FLANNEL_SUBNET


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


# 17. Adding amazon and ceph config data
if [ "$ISAMAZON" = true ];then
cat > $KUBERDOCK_DIR/kubedock/amazon_settings.py << EOF
AWS=True
REGION="$REGION"
AVAILABILITY_ZONE="$AVAILABILITY_ZONE"
AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY"
EOF
fi

if [ "$HAS_CEPH" = yes ];then
cat > $KUBERDOCK_DIR/kubedock/ceph_settings.py << EOF
CEPH=True
EOF
fi

# 18. Create root ssh keys if missing and copy'em  to WEBAPP_USER homedir
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
echo "login: admin"
echo "password: $ADMIN_PASSWORD"

}


############
# Clean up #
############


do_cleanup()
{

    log_it echo "Cleaning up..."

    log_it echo "Stop and disable services..."
    for i in nginx emperor.uwsgi flanneld redis postgresql influxdb etcd \
             kube-apiserver kube-controller-manager kube-scheduler;do
        log_it systemctl disable $i
    done
    for i in nginx emperor.uwsgi kube-apiserver kube-controller-manager kube-scheduler;do
        log_it systemctl stop $i
    done

    log_it echo "Cleaning up etcd..."
    log_it etcdctl rm --recursive /registry
    log_it etcdctl rm --recursive /kuberdock
    log_it echo "Cleaning up redis..."
    log_it redis-cli flushall
    log_it echo "Cleaning up influxdb..."
    curl -X DELETE 'http://localhost:8086/db/cadvisor?u=root&p=root'
    for i in flanneld redis influxdb etcd;do
        log_it systemctl stop $i
    done

    log_it echo "Trying to remove postgres role and database..."
    su -c 'dropdb kuberdock && dropuser kuberdock' - postgres
    if [ $? -ne 0 ];then
        log_it echo "Couldn't delete role and database!"

        while true;do
            read -p "Remove the whole postgres data dir (it will erase all data stored in postgres) (yes/no)? [yes]: " REMOVE_DIR
            if [ "$REMOVE_DIR" = yes ] || [ -z "$REMOVE_DIR" ];then
                log_it systemctl stop postgresql
                log_it rm -rf /var/lib/pgsql
                break
            elif [ "$REMOVE_DIR" = no ];then
                break
            fi
        done
    fi

    log_it echo 'Delete SELinux rule for http on port 9200'
    log_it semanage port --delete -p tcp 9200

    # Firewall
    if rpm -q firewalld > /dev/null && firewall-cmd --state > /dev/null;then
        log_it echo 'Clear old firewall rules...'
        log_it firewall-cmd --permanent --zone=public --remove-port=80/tcp
        log_it firewall-cmd --permanent --zone=public --remove-port=443/tcp
        # ntp
        log_it firewall-cmd --permanent --zone=public --remove-port=123/udp

        log_it echo 'Remove cluster-only visible ports...'
        re='rule family="ipv4" source address=".+" port port="((7080|8086|53)" protocol="tcp|53" protocol="udp)" accept'
        firewall-cmd --permanent --zone=public --list-rich-rules | while read i;do
            if [[ $i =~ $re ]];then
                log_it firewall-cmd --permanent --zone=public --remove-rich-rule="$i"
            fi
        done

        # kube-apiserver secure
        log_it firewall-cmd --permanent --zone=public --remove-port=6443/tcp
        # etcd secure
        log_it firewall-cmd --permanent --zone=public --remove-port=2379/tcp
        # close ports for cpanel flannel and kube-proxy
        log_it firewall-cmd --permanent --zone=public --remove-port=8123/tcp
        log_it firewall-cmd --permanent --zone=public --remove-port=8118/tcp

        log_it echo 'Reload firewall...'
        log_it firewall-cmd --reload
    else
        log_it echo 'Firewall is not running. Skip removing any old roles'
    fi

    log_it echo "Remove packages..."
    log_it yum -y remove kuberdock ntp etcd-ca bridge-utils
    log_it yum -y autoremove

    log_it echo "Remove old repos..."
    log_it rm -f /etc/yum.repos.d/kube-cloudlinux.repo \
                 /etc/yum.repos.d/kube-cloudlinux-testing.repo

    log_it echo "Remove dirs..."
    for i in /var/run/kubernetes /etc/kubernetes /var/run/flannel ~/.etcd-ca \
             /var/opt/kuberdock /etc/sysconfig/kuberdock /etc/pki/etcd; do
        rm -rf $i
    done

}


#########
# Start #
#########


if [ "$CLEANUP" = yes ];then
    do_cleanup
else
    do_deploy
fi
