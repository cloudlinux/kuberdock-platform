#!/bin/bash

KUBERDOCK_DIR=/var/opt/kuberdock
KUBERDOCK_LIB_DIR=/var/lib/kuberdock
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

RELEASE="CentOS Linux release 7.2"
ARCH="x86_64"
MIN_RAM_KB=1880344
MIN_DISK_SIZE=10

check_release()
{
    cat /etc/redhat-release | grep "$RELEASE" > /dev/null
    if [ $? -ne 0 ] || [ `uname -m` != $ARCH ];then
        ERRORS="$ERRORS Inappropriate OS version\n"
    fi
}

check_mem(){
    MEM=$(vmstat -s | head -n 1 | awk '{print $1}')
    if [[ $MEM -lt $MIN_RAM_KB ]]; then
        ERRORS="$ERRORS Master RAM space is insufficient\n"
    fi
}

check_disk(){
    DISK_SIZE=$(df --output=avail -BG / | tail -n +2)
    if [ ${DISK_SIZE%?} -lt $MIN_DISK_SIZE ]; then
        ERRORS="$ERRORS Master free disk space is insufficient\n"
    fi
}

check_release
check_mem
check_disk

if [[ $ERRORS ]]; then
    printf "Following noncompliances of KD cluster requirements have been detected:\n"
    printf "$ERRORS"
    printf "For details refer Requirements section of KuberDock Documentation, http://docs.kuberdock.com/index.html?requirements.htm\n"
    exit 3
fi

# IMPORTANT: each package must be installed with separate command because of
# yum incorrect error handling!


# Parse args


CONF_FLANNEL_BACKEND="vxlan"
VNI="1"
while [[ $# > 0 ]];do
    key="$1"
    case $key in
        -c|--cleanup)
        CLEANUP=yes
        ;;
        -t|--testing)
        WITH_TESTING=yes
        ;;
        -n|--pd-namespace)
        PD_CUSTOM_NAMESPACE="$2"
        shift
        ;;
        # ======== CEPH options ==============
        # Use this CEPH user to access CEPH cluster
        # The user must have rwx access to CEPH pool (it is equal to master IP
        # or --pd-namespace value if the last was specified)
        --ceph-user)
        CEPH_CLIENT_USER="$2"
        shift
        ;;
        # Use this CEPH config file for CEPH client on nodes
        --ceph-config)
        CEPH_CONFIG_PATH="$2"
        shift
        ;;
        # CEPH user keyring path
        --ceph-user-keyring)
        CEPH_KEYRING_PATH="$2"
        shift
        ;;
        # ======== End of CEPH options ==============
        -u|--udp-backend)
        CONF_FLANNEL_BACKEND='udp'
        ;;
        -g|--hostgw-backend)
        CONF_FLANNEL_BACKEND='host-gw'
        ;;
        --vni)
        VNI="$2";   # vxlan network id. Defaults to 1
        shift
        ;;
        *)
        echo "Unknown option: $key"
        exit 1
        ;;
    esac
    shift # past argument or value
done

HAS_CEPH=no
# Check CEPH options if any is specified
if [ ! -z "$CEPH_CONFIG_PATH" ] || [ ! -z "$CEPH_KEYRING_PATH" ] || [ ! -z "$CEPH_CLIENT_USER" ]; then

    MANDATORY_CEPH_OPTIONS="--ceph-config --ceph-user-keyring --ceph-user"
    # Check that all CEPH configuration options was specified
    if [ -z "$CEPH_CONFIG_PATH" ] || [ -z "$CEPH_KEYRING_PATH" ] || [ -z "$CEPH_CLIENT_USER" ]; then
        echo "There must be specified all options for CEPH ($MANDATORY_CEPH_OPTIONS) or none of them"
        exit 1
    fi

    for file in "$CEPH_KEYRING_PATH" "$CEPH_CONFIG_PATH"; do
        if [ ! -e "$file" ]; then
            echo "File not found: $file"
            exit 1
        fi
    done

    HAS_CEPH=yes
fi



# SOME HELPERS

install_repos()
{
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
}

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
    if [ -f /sys/hypervisor/uuid ] && [ `head -c 3 /sys/hypervisor/uuid` == ec2 ];then
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

#AWS stuff
function get_vpc_id {
    python -c "import json,sys; print json.load(sys.stdin)['Reservations'][0]['Instances'][0].get('VpcId', '')"
}

function get_subnet_id {
    python -c "import json,sys; print json.load(sys.stdin)['Reservations'][0]['Instances'][0].get('SubnetId', '')"
}

function get_route_table_id {
  python -c "import json,sys; lst = [str(route_table['RouteTableId']) for route_table in json.load(sys.stdin)['RouteTables'] if route_table['VpcId'] == '$1' and route_table['Associations'][0].get('SubnetId') == '$2']; print ''.join(lst)"
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

#if [ "$ISAMAZON" = true ] && [ -z "$ROUTE_TABLE_ID" ];then
#    echo "ROUTE_TABLE_ID as envvar is expected for AWS setup"
#    exit 1
#fi

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

# Do some preliminaries for aws/non-aws setups
if [ -z "$PD_CUSTOM_NAMESPACE" ]; then
  PD_NAMESPACE="$MASTER_IP"
else
  PD_NAMESPACE="$PD_CUSTOM_NAMESPACE"
fi


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

    if [ -z "$ROUTE_TABLE_ID" ];then
        install_repos
        yum_wrapper install aws-cli -y
        INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
        INSTANCE_DATA=$(aws ec2 describe-instances --region=$REGION --instance-id $INSTANCE_ID)
        VPC_ID=$(echo "$INSTANCE_DATA"|get_vpc_id)
        SUBNET_ID=$(echo "$INSTANCE_DATA"|get_subnet_id)
        ROUTE_TABLES=$(aws ec2 describe-route-tables --region=$REGION)
        ROUTE_TABLE_ID=$(echo "$ROUTE_TABLES"|get_route_table_id $VPC_ID $SUBNET_ID)
    fi

else
    if [ "$HAS_CEPH" = yes ]; then

        CEPH_CONF_DIR=$KUBERDOCK_LIB_DIR/conf
        [ -d $CEPH_CONF_DIR ] || mkdir -p $CEPH_CONF_DIR
        cp "$CEPH_CONFIG_PATH" $CEPH_CONF_DIR/ceph.conf || exit 1
        cp "$CEPH_KEYRING_PATH" $CEPH_CONF_DIR || exit 1

        CEPH_KEYRING_FILENAME=$(basename "$CEPH_KEYRING_PATH")

        MONITORS=$(grep mon_host $CEPH_CONF_DIR/ceph.conf | cut -d ' ' -f 3)
        KEYRING_PATH=/etc/ceph/$CEPH_KEYRING_FILENAME
    fi
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


# AC-3318 Remove chrony which prevents ntpd service to start 
# after boot
yum erase -y chrony

# 3 Install ntp, we need correct time for node logs
# for now, etcd-ca and bridge-utils needed during deploy only
install_repos
yum_wrapper install -y ntp
yum_wrapper install -y etcd-ca
yum_wrapper install -y bridge-utils
log_it ntpd -gq
log_it echo "Enabling restart for ntpd.service"
do_and_log mkdir -p /etc/systemd/system/ntpd.service.d
do_and_log echo -e "[Service]
Restart=always
RestartSec=1s" > /etc/systemd/system/ntpd.service.d/restart.conf
do_and_log systemctl daemon-reload
do_and_log systemctl restart ntpd
do_and_log systemctl reenable ntpd
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
# After kuberdock, because we need installed semanage package to do check
SESTATUS=$(sestatus|awk '/SELinux\sstatus/ {print $3}')
if [ "$SESTATUS" != disabled ];then
    log_it echo 'Adding SELinux rule for http on port 9200'
    do_and_log semanage port -a -t http_port_t -p tcp 9200
fi

#4.3 nginx config fix
cp $KUBERDOCK_DIR/conf/nginx.conf /etc/nginx/nginx.conf


#5 Write settings that hoster enter above (only after yum kuberdock.rpm)
echo "MASTER_IP=$MASTER_IP" >> $KUBERDOCK_MAIN_CONFIG
echo "MASTER_TOBIND_FLANNEL=$MASTER_TOBIND_FLANNEL" >> $KUBERDOCK_MAIN_CONFIG
echo "NODE_TOBIND_EXTERNAL_IPS=$NODE_TOBIND_EXTERNAL_IPS" >> $KUBERDOCK_MAIN_CONFIG
echo "NODE_TOBIND_FLANNEL=$NODE_TOBIND_FLANNEL" >> $KUBERDOCK_MAIN_CONFIG
echo "PD_NAMESPACE=$PD_NAMESPACE" >> $KUBERDOCK_MAIN_CONFIG



#6 Setting up etcd
log_it echo 'Generating etcd-ca certificates...'
do_and_log mkdir /etc/pki/etcd
etcd-ca --depot-path /root/.etcd-ca init --passphrase ""
etcd-ca --depot-path /root/.etcd-ca export --insecure --passphrase "" | tar -xf -
do_and_log mv ca.crt /etc/pki/etcd/
do_and_log rm -f ca.key.insecure

# first instance of etcd cluster
etcd1=$(uname -n)
etcd-ca --depot-path /root/.etcd-ca new-cert --ip "127.0.0.1,$MASTER_IP" --passphrase "" $etcd1
etcd-ca --depot-path /root/.etcd-ca sign --passphrase "" $etcd1
etcd-ca --depot-path /root/.etcd-ca export $etcd1 --insecure --passphrase "" | tar -xf -
do_and_log mv $etcd1.crt /etc/pki/etcd/
do_and_log mv $etcd1.key.insecure /etc/pki/etcd/$etcd1.key

# generate dns-pod's certificate
etcd-ca --depot-path /root/.etcd-ca new-cert --ip "10.254.0.10" --passphrase "" etcd-dns
etcd-ca --depot-path /root/.etcd-ca sign --passphrase "" etcd-dns
etcd-ca --depot-path /root/.etcd-ca export etcd-dns --insecure --passphrase "" | tar -xf -
do_and_log mv etcd-dns.crt /etc/pki/etcd/
do_and_log mv etcd-dns.key.insecure /etc/pki/etcd/etcd-dns.key

# generate client's certificate
etcd-ca --depot-path /root/.etcd-ca new-cert --passphrase "" etcd-client
etcd-ca --depot-path /root/.etcd-ca sign --passphrase "" etcd-client
etcd-ca --depot-path /root/.etcd-ca export etcd-client --insecure --passphrase "" | tar -xf -
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
do_and_log systemctl reenable etcd
do_and_log systemctl restart etcd


# KuberDock k8s to etcd middleware
cat > /etc/systemd/system/kuberdock-k8s2etcd.service << EOF
[Unit]
Description=KuberDock kubernetes to etcd events middleware
Before=kube-apiserver.service

[Service]
ExecStart=/usr/bin/env python2 /var/opt/kuberdock/k8s2etcd.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

do_and_log systemctl reenable kuberdock-k8s2etcd
do_and_log systemctl restart kuberdock-k8s2etcd


# Systemd to sysvinit backwards compatibility has been broken
# after updating to centos 7.2.
# so we need to create an influxdb unit-file at the moment
cat > /etc/systemd/system/influxdb.service << EOF
[Unit]
Description=InfluxDB Server
After=network.target

[Service]
ExecStart=/usr/bin/influxdb -pidfile /opt/influxdb/shared/influxdb.pid -config /opt/influxdb/shared/config.toml

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
# Start early or curl connection refused
do_and_log systemctl reenable influxdb
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
if [ "$ISAMAZON" = true ];then
sed -i "/^KUBE_API_ARGS/ {s|\"\"|\"--cloud-provider=aws --token_auth_file=$KNOWN_TOKENS_FILE --bind-address=$MASTER_IP  --watch-cache=false\"|}" $KUBERNETES_CONF_DIR/apiserver
sed -i "/^KUBE_CONTROLLER_MANAGER_ARGS/ {s|\"\"|\"--cloud-provider=aws\"|}" $KUBERNETES_CONF_DIR/controller-manager
else
sed -i "/^KUBE_API_ARGS/ {s|\"\"|\"--token_auth_file=$KNOWN_TOKENS_FILE --bind-address=$MASTER_IP  --watch-cache=false\"|}" $KUBERNETES_CONF_DIR/apiserver
fi
sed -i "/^KUBE_ADMISSION_CONTROL/ {s|--admission_control=NamespaceLifecycle,NamespaceExists,LimitRanger,SecurityContextDeny,ServiceAccount,ResourceQuota|--admission_control=NamespaceLifecycle,NamespaceExists,SecurityContextDeny|}" $KUBERNETES_CONF_DIR/apiserver


#10. Create and populate DB
log_it echo 'Create and populate DB'
cp /usr/lib/systemd/system/postgresql.service /etc/systemd/system/postgresql.service
sed -i "/^ExecStart=/ {s/-t 300/-t 900/}" /etc/systemd/system/postgresql.service
sed -i "/^TimeoutSec=/ {s/300/900/}" /etc/systemd/system/postgresql.service
sed -i "/^After=/ {s/After=network.target/After=network.target\nBefore=emperor.uwsgi.service/}" /etc/systemd/system/postgresql.service
do_and_log systemctl reenable postgresql
export PGSETUP_INITDB_OPTIONS="--encoding UTF8" # fix for non-UTF8 locales
log_it postgresql-setup initdb  # may fail, if postgres data dir is not empty (it's ok)
do_and_log systemctl restart postgresql
do_and_log python $KUBERDOCK_DIR/postgresql_setup.py
do_and_log systemctl restart postgresql
cd $KUBERDOCK_DIR
ADMIN_PASSWORD="CHANGE_ME"
ADMIN_PASSWORD=$(tr -dc 'A-Za-z0-9_' < /dev/urandom | head -c20)
do_and_log python manage.py createdb $ADMIN_PASSWORD
do_and_log python manage.py auth-key 1> /dev/null


#11. Start services
do_and_log systemctl reenable redis
do_and_log systemctl restart redis



#12 Flannel
log_it echo "Setuping flannel config to etcd..."

# This must be same as cluster network (ex. Portal_net):
CONF_FLANNEL_NET=10.254.0.0/16
CONF_FLANNEL_SUBNET_LEN=24

if [ "$ISAMAZON" = true ];then
    # host-gw don't work on AWS so we use aws-vpc or other specified by user
    if [ -z "$ROUTE_TABLE_ID" ];then
        if [ "$CONF_FLANNEL_BACKEND" == 'vxlan' ];then
            log_it echo "WARNING: Flanneld vxlan backend with VNI=$VNI will be used on amazon instead of recommended aws-vpc..."
            etcdctl mk /kuberdock/network/config "{\"Network\":\"$CONF_FLANNEL_NET\", \"SubnetLen\": $CONF_FLANNEL_SUBNET_LEN, \"Backend\": {\"Type\": \"vxlan\", \"VNI\": $VNI}}" 2> /dev/null
        else    # just udp backend left for amazon
            log_it echo "WARNING: Flanneld UDP backend will be used on amazon instead of recommended aws-vpc..."
            etcdctl mk /kuberdock/network/config "{\"Network\":\"$CONF_FLANNEL_NET\", \"SubnetLen\": $CONF_FLANNEL_SUBNET_LEN, \"Backend\": {\"Type\": \"udp\"}}" 2> /dev/null
        fi
    else
        etcdctl mk /kuberdock/network/config "{\"Network\":\"$CONF_FLANNEL_NET\", \"SubnetLen\": $CONF_FLANNEL_SUBNET_LEN, \"Backend\": {\"Type\": \"aws-vpc\", \"RouteTableID\": \"$ROUTE_TABLE_ID\"}}" 2> /dev/null
    fi
else
    if [ "$CONF_FLANNEL_BACKEND" == 'vxlan' ];then
        etcdctl mk /kuberdock/network/config "{\"Network\":\"$CONF_FLANNEL_NET\", \"SubnetLen\": $CONF_FLANNEL_SUBNET_LEN, \"Backend\": {\"Type\": \"vxlan\", \"VNI\": $VNI}}" 2> /dev/null
    else    # host-gw or udp backends case
        etcdctl mk /kuberdock/network/config "{\"Network\":\"$CONF_FLANNEL_NET\", \"SubnetLen\": $CONF_FLANNEL_SUBNET_LEN, \"Backend\": {\"Type\": \"$CONF_FLANNEL_BACKEND\"}}" 2> /dev/null
    fi
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
do_and_log systemctl reenable flanneld
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



do_and_log systemctl reenable dnsmasq
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
# Need to add After=etcd.service, because kube-apiserver start faster then etcd on machine boot
cat > /etc/systemd/system/kube-apiserver.service << EOF
[Unit]
Description=Kubernetes API Server
Documentation=https://github.com/GoogleCloudPlatform/kubernetes
After=etcd.service

[Service]
EnvironmentFile=-/etc/kubernetes/config
EnvironmentFile=-/etc/kubernetes/apiserver
User=kube
ExecStart=/usr/bin/kube-apiserver \
	    \$KUBE_LOGTOSTDERR \
	    \$KUBE_LOG_LEVEL \
	    \$KUBE_ETCD_SERVERS \
	    \$KUBE_API_ADDRESS \
	    \$KUBE_API_PORT \
	    \$KUBELET_PORT \
	    \$KUBE_ALLOW_PRIV \
	    \$KUBE_SERVICE_ADDRESSES \
	    \$KUBE_ADMISSION_CONTROL \
	    \$KUBE_API_ARGS
Restart=on-failure
Type=notify
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
cat > /etc/systemd/system/kube-controller-manager.service << EOF
[Unit]
Description=Kubernetes Controller Manager
Documentation=https://github.com/GoogleCloudPlatform/kubernetes
After=network.target

[Service]
EnvironmentFile=-/etc/kubernetes/config
EnvironmentFile=-/etc/kubernetes/controller-manager
User=kube
ExecStart=/usr/bin/kube-controller-manager \
            \$KUBE_LOGTOSTDERR \
            \$KUBE_LOG_LEVEL \
            \$KUBE_MASTER \
            \$KUBE_CONTROLLER_MANAGER_ARGS
Restart=on-failure
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload

log_it echo "Starting kubernetes..."
for i in kube-apiserver kube-controller-manager kube-scheduler;
    do do_and_log systemctl reenable $i;done
for i in kube-apiserver kube-controller-manager kube-scheduler;
    do do_and_log systemctl restart $i;done



#16. Adding amazon and ceph config data
if [ "$ISAMAZON" = true ];then
cat > $KUBERDOCK_DIR/kubedock/amazon_settings.py << EOF
AWS=True
REGION="$REGION"
AVAILABILITY_ZONE="$AVAILABILITY_ZONE"
AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY"
EOF
fi

if [ -z "$CEPH_CLIENT_USER" ]; then
  CEPH_CLIENT_USER=admin
fi

if [ "$HAS_CEPH" = yes ];then
cat > $KUBERDOCK_DIR/kubedock/ceph_settings.py << EOF
CEPH=True
MONITORS='$MONITORS'
CEPH_KEYRING_PATH='$KEYRING_PATH'
CEPH_CLIENT_USER='$CEPH_CLIENT_USER'
EOF

fi

# 17. Starting web-interface
#
# WARNING! uWSGI restart should be done after writing all custom settings (CEPH, Amazon, etc)
#
log_it echo "Starting kuberdock web-interface..."
do_and_log systemctl reenable emperor.uwsgi
do_and_log systemctl restart emperor.uwsgi

do_and_log systemctl reenable nginx
do_and_log systemctl restart nginx


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
    for i in nginx emperor.uwsgi flanneld redis postgresql influxdb kuberdock-k8s2etcd etcd \
             kube-apiserver kube-controller-manager kube-scheduler;do
        log_it systemctl disable $i
    done
    for i in nginx emperor.uwsgi kube-apiserver kube-controller-manager kuberdock-k8s2etcd kube-scheduler;do
        log_it systemctl stop $i
    done

    log_it echo -e "Deleting custom kuberdock-k8s2etcd.service..."
    log_it rm /etc/systemd/system/kuberdock-k8s2etcd.service
    log_it systemctl daemon-reload

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

    # '\n' because curl is a previous command
    log_it echo -e "\nDeleting custom influxdb.service..."
    log_it rm /etc/systemd/system/influxdb.service
    log_it systemctl daemon-reload

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
    for i in /var/run/kubernetes /etc/kubernetes /var/run/flannel /root/.etcd-ca \
             /var/opt/kuberdock /var/lib/kuberdock /etc/sysconfig/kuberdock /etc/pki/etcd \
             /etc/etcd/etcd.conf /var/lib/etcd; do
        rm -rf $i
    done

}

#####################
# Fail log delivery #
#####################

SENTRY_SETTINGS_URL="http://repo.cloudlinux.com/kuberdock/settings.json"
SENTRY_SETTINGS=$(curl -s $SENTRY_SETTINGS_URL)
SENTRY_DSN=$(echo $SENTRY_SETTINGS | sed -E 's/^.*"https:\/\/(.*):(.*)@(.*)\/(.*)".*/\1,\2,\3,\4/')
SENTRYVERSION=7

SENTRYKEY=$(echo $SENTRY_DSN | cut -f1 -d,)
SENTRYSECRET=$(echo $SENTRY_DSN | cut -f2 -d,)
SENTRYURL=$(echo $SENTRY_DSN | cut -f3 -d,)
SENTRYPROJECTID=$(echo $SENTRY_DSN | cut -f4 -d,)

ERRORLOGFILE=error.log

DATA_TEMPLATE='{'\
'\"project\": \"$SENTRYPROJECTID\", '\
'\"logger\": \"bash\", '\
'\"platform\": \"other\", '\
'\"message\": \"Deploy error\", '\
'\"event_id\": \"$eventid\", '\
'\"level\": \"error\", '\
'\"extra\":{\"fullLog\":\"$logs\"}, '\
'\"tags\":{\"uname\":\"$uname\", \"owner\":\"$KD_OWNER_EMAIL\"}}'


sentryWrapper() {
   cmnd="$@"
   $cmnd 2>&1 | tee $ERRORLOGFILE ; ( exit ${PIPESTATUS} )
   ERROR_CODE=$?
   if [ ${ERROR_CODE} != 0 ] ;then
     eventid=$(cat /proc/sys/kernel/random/uuid | tr -d "-")
     printf "We have a problem during deployment of KuberDock master on your server. Let us help you to fix a problem. We have collected all information we need into $ERRORLOGFILE. \n"

     if [ -z ${KD_OWNER_EMAIL} ]; then
         read -p "Do you agree to send it to our support team? If so, just specify an email and we contact you back: " -r KD_OWNER_EMAIL
     fi
     echo
     if [ ! -z ${KD_OWNER_EMAIL} ] ;then
         logs=$(while read line; do echo -n "${line}\\n"; done < $ERRORLOGFILE)
         uname=$(uname -a)
         data=$(eval echo $DATA_TEMPLATE)
         echo
         curl -s -H "Content-Type: application/json" -X POST --data "$data" "$SENTRYURL/api/$SENTRYPROJECTID/store/"\
"?sentry_version=$SENTRYVERSION&sentry_client=test&sentry_key=$SENTRYKEY&sentry_secret=$SENTRYSECRET" > /dev/null && echo "Information about your problem has been sent to our support team."
     fi
     echo "Done."
     exit ${ERROR_CODE}
   fi
}



#########
# Start #
#########

if [ "$CLEANUP" = yes ];then
    sentryWrapper do_cleanup
else
    sentryWrapper do_deploy
fi
