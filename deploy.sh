#!/bin/bash

KUBERDOCK_DIR=/var/opt/kuberdock
KUBERDOCK_LIB_DIR=/var/lib/kuberdock
KUBERNETES_CONF_DIR=/etc/kubernetes
KUBERDOCK_MAIN_CONFIG=/etc/sysconfig/kuberdock/kuberdock.conf
KNOWN_TOKENS_FILE="$KUBERNETES_CONF_DIR/known_tokens.csv"
WEBAPP_USER=nginx
DEPLOY_LOG_FILE=/var/log/kuberdock_master_deploy.log
EXIT_MESSAGE="Installation error. Install log saved to $DEPLOY_LOG_FILE"
NGINX_SHARED_ETCD="/etc/nginx/conf.d/shared-etcd.conf"

# Just to ensure HOSTNAME is not empty. Anyway it should be set to valid value
# but we do not know here what value is valid.
HOSTNAME=${HOSTNAME:-$(uname -n)}


ELASTICSEARCH_PORT=9200
CADVISOR_PORT=4194

# Back up old logs
if [ -f $DEPLOY_LOG_FILE ]; then
    TIMESTAMP=$(stat --format=%Y $DEPLOY_LOG_FILE)
    DATE_TIME=$(date -d @$TIMESTAMP +'%Y%m%d%H%M%S')
    DEPLOY_LOG_FILE_NAME=$(stat --format=%n $DEPLOY_LOG_FILE | cut -f1 -d'.')
    DEPLOY_LOG_FILE_SUFFIX=$(stat --format=%n $DEPLOY_LOG_FILE | cut -f2 -d'.')
    OLD_LOG=$DEPLOY_LOG_FILE_NAME$DATE_TIME.$DEPLOY_LOG_FILE_SUFFIX
    mv $DEPLOY_LOG_FILE $OLD_LOG
fi
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

DATA_TEMPLATE='{'\
'\"project\": \"$SENTRYPROJECTID\", '\
'\"logger\": \"bash\", '\
'\"platform\": \"other\", '\
'\"message\": \"Deploy error\", '\
'\"event_id\": \"$eventid\", '\
'\"level\": \"error\", '\
'\"extra\":{\"fullLog\":\"$logs\"}, '\
'\"tags\":{\"uname\":\"$uname\", \"owner\":\"$KD_OWNER_EMAIL\"},'\
' \"release\":\"$release\", \"server_name\":\"$hostname\($ip_address\)\"}'

KEY_BITS="${KEY_BITS:-4096}"


isRpmFileNotSigned(){
    package="$@"
    sig=$(rpm -Kv "$package" | grep Signature)
    if [ -z "$sig" ]; then
        return 0
    else
        return 1
    fi
}

isInstalledRpmNotSigned(){
    installed=$(rpm -qi kuberdock | grep Signature | awk -F ": " '{print $2}')
    if [ "$installed" == "(none)" ];then
        return 0
    else
        return 1
    fi
}

sentryWrapper() {
     if [ "$SENTRY_ENABLE" == "n" ];then
        return 0
     fi

     if [ "$SENTRY_ENABLE" != "y" ];then
         # AC-3591 Do not send anything if package not signed
         package=$(ls -1 | awk '/^kuberdock.*\.rpm$/ {print $1; exit}')
         if [ ! -z "$package" ];then
             if isRpmFileNotSigned "$package"; then
                 return 0
             fi
         else
             if isInstalledRpmNotSigned; then
                 return 0
             fi
         fi
    fi

     eventid=$(cat /proc/sys/kernel/random/uuid | tr -d "-")
     printf "We have a problem during deployment of KuberDock master on your server. Let us help you to fix a problem. We have collected all information we need into $DEPLOY_LOG_FILE. \n"

     if [ -z ${KD_OWNER_EMAIL} ]; then
         read -p "Do you agree to send it to our support team? If so, just specify an email and we contact you back: " -r KD_OWNER_EMAIL
     fi
     echo
     if [ ! -z ${KD_OWNER_EMAIL} ] ;then
         logs=$(while read line; do echo -n "${line}\\n"; done < $DEPLOY_LOG_FILE)
         logs=$(echo "$logs" | tr -d '"')
         uname=$(uname -a)
         hostname=$(cat /etc/hostname)
         ip_address=$(ip route get 8.8.8.8 | awk 'NR==1 {print $NF}')
         release=$(rpm -q --queryformat "%{VERSION}-%{RELEASE}" kuberdock)
         data=$(eval echo "$DATA_TEMPLATE")
         echo
         curl -s -H --fail "Content-Type: application/json" -X POST --data "$data" "$SENTRYURL/api/$SENTRYPROJECTID/store/"\
"?sentry_version=$SENTRYVERSION&sentry_client=test&sentry_key=$SENTRYKEY&sentry_secret=$SENTRYSECRET" > /dev/null

         RETURN_CODE=$?
         if [ ${RETURN_CODE} != 0 ] ;then
            echo "We could not automatically send logs. Please contact support."
         else
            echo "Information about your problem has been sent to our support team."
         fi
     fi
     echo "Done."
}


catchFailure() {
   cmnd="$@"
   $cmnd
   catchExit
}

catchExit(){
   ERROR_CODE=$?
   if [ ${ERROR_CODE} != 0 ] ;then
       sentryWrapper
   fi
}

waitAndCatchFailure() {
    local COUNT="$1"
    shift 1
    local DELAY="$1"
    shift 1
    until [ "$COUNT" -lt 0 ]; do
        "$@" && return
        sleep "$DELAY"
        let COUNT-=1
    done
    sentryWrapper
}

etcdctl_wpr() {
    etcdctl --timeout 30s --total-timeout 30s "$@"
}

#####################

if [ $USER != "root" ]; then
    echo "Superuser privileges required" | tee -a $DEPLOY_LOG_FILE
    exit 1
fi

trap catchExit EXIT

RELEASE="CentOS Linux release 7.2"
ARCH="x86_64"
MIN_RAM_KB=1572864
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


VNI="1"
while [[ $# -gt 0 ]];do
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
        --fixed-ip-pools)
        FIXED_IP_POOLS=true
        ;;
        --vni)
        VNI="$2";   # vxlan network id. Defaults to 1
        shift
        ;;
        --zfs)
        ZFS=yes
        ;;
        --pod-ip-network)
        CALICO_NETWORK="$2"
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
      echo "$EXIT_MESSAGE"
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
      echo "$EXIT_MESSAGE"
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

function create_k8s_certs {
  local -r primary_cn="${1}"
  local -r certs_dir="${2}"

  K8S_TEMP="/tmp/k8s/"
  rm -rf ${K8S_TEMP}
  mkdir ${K8S_TEMP}

  sans="IP:${primary_cn},IP:10.254.0.1,DNS:kubernetes,DNS:kubernetes.default,DNS:kubernetes.default.svc,DNS:$(hostname)"

  local -r cert_create_debug_output=$(mktemp "${K8S_TEMP}/cert_create_debug_output.XXX")
  (set -x
    cd "${K8S_TEMP}"
    catchFailure curl -L -O --connect-timeout 20 --retry 6 --retry-delay 2 https://storage.googleapis.com/kubernetes-release/easy-rsa/easy-rsa.tar.gz
    tar xzf easy-rsa.tar.gz
    cd easy-rsa-master/easyrsa3
    ./easyrsa --keysize="$KEY_BITS" init-pki
    ./easyrsa --keysize="$KEY_BITS" --batch "--req-cn=${primary_cn}@$(date +%s)" build-ca nopass
    ./easyrsa --keysize="$KEY_BITS" --subject-alt-name="${sans}" build-server-full "$(hostname)" nopass
    ) &>${cert_create_debug_output} || {
        cat "${cert_create_debug_output}" >&2
        echo "=== Failed to generate certificates: Aborting ===" >&2
        exit 2
    }
    TMP_CERT_DIR="${K8S_TEMP}/easy-rsa-master/easyrsa3"
    mkdir -p ${certs_dir}
    mv ${TMP_CERT_DIR}/pki/ca.crt ${certs_dir}/
    mv ${TMP_CERT_DIR}/pki/issued/* ${certs_dir}/
    mv ${TMP_CERT_DIR}/pki/private/* ${certs_dir}/
    chown -R kube:kube ${certs_dir}
    chmod -R 0440 ${certs_dir}/*
}

setup_ntpd ()
{
    # AC-3318 Remove chrony which prevents ntpd service to start after boot
    yum erase -y chrony
    yum install -y ntp

    _sync_time() {
        grep '^server' /etc/ntp.conf | awk '{print $2}' | xargs ntpdate -u
    }

    for _retry in $(seq 3); do
        echo "Attempt $_retry to run ntpdate -u ..." && \
        _sync_time && break || sleep 30;
    done

    _sync_time
    if [ $? -ne 0 ];then
        echo "ERROR: ntpdate exit with error. Maybe some problems with ntpd settings and manual changes are needed"
        exit 1
    fi

    # To prevent ntpd from exit on large time offsets
    sed -i "/^tinker /d" /etc/ntp.conf
    echo "tinker panic 0" >> /etc/ntp.conf

    log_it echo "Enabling restart for ntpd.service"
    do_and_log mkdir -p /etc/systemd/system/ntpd.service.d
    do_and_log echo -e "[Service]
    Restart=always
    RestartSec=1s" > /etc/systemd/system/ntpd.service.d/restart.conf
    do_and_log systemctl daemon-reload
    do_and_log systemctl restart ntpd
    do_and_log systemctl reenable ntpd
    do_and_log ntpq -p
    if [ $? -ne 0 ];then
        echo "WARNING: ntpq -p exit with error. Maybe some problems with ntpd settings and manual changes needed"
    fi
}

SERVICE_NETWORK="10.254.0.0/16"

##########
# Deploy #
##########


do_deploy()
{

check_amazon

NETS=`ip -o -4 addr | grep -vP '\slo\s' | awk '{print $4}'`
CALICO_NETWORK=`python - << EOF
from itertools import chain
import socket
import sys
base_net = '10.0.0.0/8'
def overlaps(net1, net2):
    nets = []
    for net in (net1, net2):
        netstr, bits = net.split('/')
        ipaddr = int(''.join([ '%02x' % int(x) for x in netstr.split('.') ]), 16)
        first = ipaddr & ( 0xffffffff ^ (1 << (32 - int(bits)))-1)
        last = ipaddr | (1 << (32 - int(bits)))-1
        nets.append((first, last))
    return ((nets[1][0] <= nets[0][0] <= nets[1][1] or
            nets[1][0] <= nets[0][1] <= nets[1][1]) or
            (nets[0][0] <= nets[1][0] <= nets[0][1] or
             nets[0][0] <= nets[1][1] <= nets[0][1]))

calico_network = """$CALICO_NETWORK"""
service_network = """$SERVICE_NETWORK"""
nets = """$NETS"""
nets = nets.splitlines()
filtered = [ip_net for ip_net in nets if overlaps(ip_net, base_net)]
filtered.append(service_network)
def get_calico_network():
    # just create sequence 127,126,128,125,129,124,130,123,131,122,132...
    addrs = list(chain(*zip(range(127, 255), reversed(range(0, 127)))))
    for addr in addrs:
        net = '10.{}.0.0/16'.format(addr)
        if not any(overlaps(host_net, net) for host_net in filtered):
            return str(net)

if calico_network:
    ip, bits = calico_network.split('/')
    try:
        socket.inet_pton(socket.AF_INET, ip)
    except:
        print "Pod network validation error. Network must be in format: '10.0.0.0/16'"
        sys.exit(1)
    if overlaps(calico_network, service_network):
        print "Pod network can't overlaps with service network"
        sys.exit(1)
    elif any(overlaps(calico_network, net) for net in filtered):
        print "Pod network overlaps with some of already existing network"
        sys.exit(1)
    print calico_network
else:
    calico_network = get_calico_network()
    if calico_network:
        print calico_network
    else:
        print "Can't find suitable network for pods"
        sys.exit(1)
EOF`

if [ $? -ne 0 ];then
    log_it echo $CALICO_NETWORK
    exit 1
fi


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

echo "MASTER_IP has been set to $MASTER_IP" >> $DEPLOY_LOG_FILE

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
  if [ "$ISAMAZON" = true ] && [ ! -z "$KUBE_AWS_INSTANCE_PREFIX" ]; then
    # For AWS installation may be defined KUBE_AWS_INSTANCE_PREFIX variable,
    # which will be used to prefix node names. We will use it also to prefix
    # EBS volume names.
    PD_NAMESPACE="$KUBE_AWS_INSTANCE_PREFIX"
  fi
else
  PD_NAMESPACE="$PD_CUSTOM_NAMESPACE"
fi

# Should be done at the very beginning to ensure yum https works correctly
setup_ntpd
install_repos

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

    if [ -z "$AWS_EBS_DEFAULT_SIZE" ];then
        read -p "Enter your AWS EBS DEFAULT SIZE in GB [20]: " AWS_EBS_DEFAULT_SIZE
    fi
    if [ -z "$AWS_EBS_DEFAULT_SIZE" ];then
        AWS_EBS_DEFAULT_SIZE=20
    fi

    if [ -z "$ROUTE_TABLE_ID" ];then
        yum_wrapper install awscli -y   # only after epel is installed
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
    echo "$EXIT_MESSAGE"
    exit 1
fi
log_it echo "CLUSTER_NETWORK has been determined as $CLUSTER_NETWORK"

rpm -q firewalld
if [ $? == 0 ];then
    echo "Stop firewalld. Dynamic Iptables rules will be used instead."
    systemctl stop firewalld
    systemctl mask firewalld
fi


#4. Install kuberdock
PACKAGE=$(ls -1 |awk '/^kuberdock.*\.rpm$/ {print $1; exit}')
if [ ! -z $PACKAGE ];then
    log_it echo 'WARNING: Installation from local package. Using repository is strongly recommended.'
    log_it echo 'To do this just move kuberdock package file to any other dir from deploy script.'
    yum_wrapper -y install $PACKAGE
else
    yum_wrapper -y install kuberdock
fi

if [ "$HAS_CEPH" = yes ]; then
    # Ensure nginx user has access to ceph config.
    # Do it after kuberdock because we need existing nginx user
    # (nginx installed)
    chown -R $WEBAPP_USER $CEPH_CONF_DIR
fi

# TODO AC-4871: move to kube-proxy dependencies
yum_wrapper -y install conntrack-tools

#4.1 Fix package path bug
mkdir /var/run/kubernetes || /bin/true
do_and_log chown kube:kube /var/run/kubernetes


#4.2 SELinux rules
# After kuberdock, because we need installed semanage package to do check
SESTATUS=$(sestatus|awk '/SELinux\sstatus/ {print $3}')
if [ "$SESTATUS" != disabled ];then
    log_it echo "Adding SELinux rule for http on port $ELASTICSEARCH_PORT"
    do_and_log semanage port -a -t http_port_t -p tcp $ELASTICSEARCH_PORT
fi

#4.3 nginx config fix
cp $KUBERDOCK_DIR/conf/nginx.conf /etc/nginx/nginx.conf

#4.4 populate nginx configs from templates
sed "s/@MASTER_IP@/$MASTER_IP/g" "$KUBERDOCK_DIR/conf/shared-etcd.conf.template" > "$NGINX_SHARED_ETCD"
chown "$WEBAPP_USER" "$NGINX_SHARED_ETCD"

#5 Write settings that hoster enter above (only after yum kuberdock.rpm)
echo "MASTER_IP = $MASTER_IP" >> $KUBERDOCK_MAIN_CONFIG
echo "MASTER_TOBIND_FLANNEL = $MASTER_TOBIND_FLANNEL" >> $KUBERDOCK_MAIN_CONFIG
echo "NODE_TOBIND_EXTERNAL_IPS = $NODE_TOBIND_EXTERNAL_IPS" >> $KUBERDOCK_MAIN_CONFIG
echo "PD_NAMESPACE = $PD_NAMESPACE" >> $KUBERDOCK_MAIN_CONFIG
echo "CALICO_NETWORK = $CALICO_NETWORK" >> $KUBERDOCK_MAIN_CONFIG
if [ "$ZFS" = yes ]; then
    echo "ZFS = yes" >> $KUBERDOCK_MAIN_CONFIG
fi

# for now, etcd-ca and bridge-utils needed during deploy only
yum_wrapper install -y etcd-ca
yum_wrapper install -y bridge-utils

#6 Setting up etcd
log_it echo 'Generating etcd-ca certificates...'
do_and_log mkdir /etc/pki/etcd
etcd-ca --depot-path /root/.etcd-ca init --passphrase "" --key-bits "$KEY_BITS"
etcd-ca --depot-path /root/.etcd-ca export --insecure --passphrase "" | tar -xf -
do_and_log mv ca.crt /etc/pki/etcd/
do_and_log rm -f ca.key.insecure

# first instance of etcd cluster
etcd1=$(uname -n)
etcd-ca --depot-path /root/.etcd-ca new-cert --ip "$MASTER_IP,127.0.0.1" --passphrase "" --key-bits "$KEY_BITS" $etcd1
#                                        this order ^^^^^^^^^^^^^^ is matter for calico, because calico see only first IP
etcd-ca --depot-path /root/.etcd-ca sign --passphrase "" $etcd1
etcd-ca --depot-path /root/.etcd-ca export $etcd1 --insecure --passphrase "" | tar -xf -
do_and_log mv $etcd1.crt /etc/pki/etcd/
do_and_log mv $etcd1.key.insecure /etc/pki/etcd/$etcd1.key

# generate dns-pod's certificate
etcd-ca --depot-path /root/.etcd-ca new-cert --ip "10.254.0.10" --passphrase "" --key-bits "$KEY_BITS" etcd-dns
etcd-ca --depot-path /root/.etcd-ca sign --passphrase "" etcd-dns
etcd-ca --depot-path /root/.etcd-ca export etcd-dns --insecure --passphrase "" | tar -xf -
do_and_log mv etcd-dns.crt /etc/pki/etcd/
do_and_log mv etcd-dns.key.insecure /etc/pki/etcd/etcd-dns.key

# generate client's certificate
etcd-ca --depot-path /root/.etcd-ca new-cert --passphrase ""  --key-bits "$KEY_BITS" etcd-client
etcd-ca --depot-path /root/.etcd-ca sign --passphrase "" etcd-client
etcd-ca --depot-path /root/.etcd-ca export etcd-client --insecure --passphrase "" | tar -xf -
do_and_log mv etcd-client.crt /etc/pki/etcd/
do_and_log mv etcd-client.key.insecure /etc/pki/etcd/etcd-client.key


cat > /etc/systemd/system/etcd.service << EOF
[Unit]
Description=Etcd Server
After=network.target

[Service]
Type=notify
WorkingDirectory=/var/lib/etcd/
EnvironmentFile=-/etc/etcd/etcd.conf
User=etcd
BlockIOWeight=1000
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
# AC-4634 we have to be sure that etcd will process requests even under heavy
# IO during deploy, so we increase election timeout from default 1000ms to much
# higher value. Max value is 50s https://coreos.com/etcd/docs/latest/tuning.html
# There is no downside for us with big values while etcd cluster consists from
# only one local node. When we want to join more etcd instances we have to set
# correct value AFTER deploy and during new etcd instances provision.
# Also, we set higher disk IO priority to etcd via systemd unit and use
# increased request timeouts for etcdctl with a special wrapper
ETCD_ELECTION_TIMEOUT="20000"
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
# Our nginx will proxy 8123 to 127.0.0.1:4001 for authorized hosts
# see "shared-etcd.conf" file
ETCD_ADVERTISE_CLIENT_URLS="https://$MASTER_IP:2379,http://127.0.0.1:4001"
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


#7 Start as early as possible, because Flannel/Calico need it
systemctl daemon-reload
log_it echo 'Starting etcd...'
do_and_log systemctl reenable etcd
log_it systemctl restart etcd
waitAndCatchFailure 3 10 etcdctl cluster-health > /dev/null


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

# change influxdb listening interface
sed -i 's/\":8086\"/\"127\.0\.0\.1:8086\"/' /etc/influxdb/influxdb.conf

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
log_it echo "Configuring kubernetes"
# ServiceAccount signing key
KUBERNETES_CERTS_DIR=/etc/kubernetes/certs/
create_k8s_certs $MASTER_IP $KUBERNETES_CERTS_DIR
K8S_TLS_CERT=$KUBERNETES_CERTS_DIR/$HOSTNAME.crt
K8S_TLS_PRIVATE_KEY=$KUBERNETES_CERTS_DIR/$HOSTNAME.key
K8S_CA_CERT=$KUBERNETES_CERTS_DIR/ca.crt

if [ "$ISAMAZON" = true ];then
    CLOUD_PROVIDER_OPT="--cloud-provider=aws"
else
    CLOUD_PROVIDER_OPT=""
fi

sed -i "/^KUBE_API_ARGS/ {s|\"\"|\"--token-auth-file=$KNOWN_TOKENS_FILE --bind-address=$MASTER_IP --watch-cache=false --tls-cert-file=$K8S_TLS_CERT --tls-private-key-file=$K8S_TLS_PRIVATE_KEY --client-ca-file=$K8S_CA_CERT --service-account-key-file=$K8S_TLS_CERT $CLOUD_PROVIDER_OPT \"|}" $KUBERNETES_CONF_DIR/apiserver
sed -i "/^KUBE_CONTROLLER_MANAGER_ARGS/ {s|\"\"|\"--service-account-private-key-file=$K8S_TLS_PRIVATE_KEY --root-ca-file=$K8S_CA_CERT $CLOUD_PROVIDER_OPT \"|}" $KUBERNETES_CONF_DIR/controller-manager
sed -i "/^KUBE_ADMISSION_CONTROL/ {s|--admission-control=NamespaceLifecycle,NamespaceExists,LimitRanger,SecurityContextDeny,ServiceAccount,ResourceQuota|--admission-control=NamespaceLifecycle,NamespaceExists,ServiceAccount|}" $KUBERNETES_CONF_DIR/apiserver

# enable third-party extensions for k8s
sed -i "/^KUBE_API_ARGS/ {s|\"$| --runtime-config=extensions/v1beta1=true,extensions/v1beta1/thirdpartyresources=true\"|}" $KUBERNETES_CONF_DIR/apiserver

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
if [ "$ISAMAZON" = true ];then
    do_and_log python manage.py createdb $ADMIN_PASSWORD --aws
else
    do_and_log python manage.py createdb $ADMIN_PASSWORD
fi
do_and_log python manage.py auth-key 1> /dev/null


#11. Start services
do_and_log systemctl reenable redis
do_and_log systemctl restart redis



log_it echo "Setuping Calico..."
do_and_log curl https://github.com/projectcalico/calico-containers/releases/download/v0.22.0/calicoctl --create-dirs --location --output /opt/bin/calicoctl --silent --show-error
do_and_log chmod +x /opt/bin/calicoctl
do_and_log curl https://github.com/projectcalico/k8s-policy/releases/download/v0.1.4/policy --create-dirs --location --output /opt/bin/policy --silent --show-error
do_and_log chmod +x /opt/bin/policy
ETCD_AUTHORITY=127.0.0.1:4001 do_and_log /opt/bin/calicoctl pool add "$CALICO_NETWORK" --ipip --nat-outgoing

do_and_log systemctl disable docker-storage-setup
do_and_log systemctl mask docker-storage-setup
mkdir /etc/systemd/system/docker.service.d/
echo -e "[Service]\nTimeoutStartSec=10min" > /etc/systemd/system/docker.service.d/10-increase_start_timeout.conf
sed -i 's/^DOCKER_STORAGE_OPTIONS=/DOCKER_STORAGE_OPTIONS="--storage-driver=overlay"/' /etc/sysconfig/docker-storage
systemctl daemon-reload
do_and_log systemctl reenable docker
log_it systemctl restart docker
do_and_log systemctl reenable kube-proxy
log_it systemctl restart kube-proxy
waitAndCatchFailure 3 10 docker info > /dev/null


# Separate pull command helps to prevent timeout bugs in calicoctl (AC-4679)
# during deploy process under heavy IO (slow dev clusters).
# If it's not enough we could add few retries with sleep here
CALICO_NODE_IMAGE="kuberdock/calico-node:0.22.0-kd1"
log_it echo "Pulling Calico node image..."
docker pull "$CALICO_NODE_IMAGE" > /dev/null
time sync
#sleep 10   # even harder workaround
log_it echo "Starting Calico node..."
ETCD_AUTHORITY=127.0.0.1:4001 do_and_log /opt/bin/calicoctl node --ip="$MASTER_IP" --node-image="$CALICO_NODE_IMAGE"


#14 Create k8s database
# Only after influxdb is fully loaded
influx -execute "create user root with password 'root' with all privileges"
influx -execute "create database k8s"
if [ $? -ne 0 ];then
    log_it echo "Error create k8s database"
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

if [ "$FIXED_IP_POOLS" = true ]; then
    sed -i 's/^KUBE_SCHEDULER_ARGS.*/KUBE_SCHEDULER_ARGS="--enable-fixed-ip-pools=true"/' $KUBERNETES_CONF_DIR/scheduler
    echo "FIXED_IP_POOLS=yes" >> $KUBERDOCK_MAIN_CONFIG
else
    echo "FIXED_IP_POOLS=no" >> $KUBERDOCK_MAIN_CONFIG
fi

log_it echo "Starting kubernetes..."
for i in kube-apiserver kube-controller-manager kube-scheduler heapster;
    do do_and_log systemctl reenable $i;done
for i in kube-apiserver kube-controller-manager kube-scheduler heapster;
    do do_and_log systemctl restart $i;done

#15a. Enable Network Policy
log_it echo "Creating Network Policy..."
cat << EOF | do_and_log kubectl create -f -
kind: ThirdPartyResource
apiVersion: extensions/v1beta1
metadata:
  name: network-policy.net.alpha.kubernetes.io
description: "Specification for a network isolation policy"
versions:
- name: v1alpha1
EOF

KD_NODES_FAILSAFE_POLICY_ORDER=0
KD_HOSTS_POLICY_ORDER=5
KD_NODES_POLICY_ORDER=10
KD_SERVICE_POLICY_ORDER=20

# This rule is needed for remote hosts tier (kuberdock-hosts). It will allow
# next tiers processing if some rhosts policy is in this tier.
# Remote hosts policies use selector 'all()'.
RULE_NEXT_TIER='{"id": "next-tier", "order": 9999, "inbound_rules": [{"action": "next-tier"}], "outbound_rules": [{"action": "next-tier"}], "selector": "all()"}'

check_json()
{
  echo "$1" | python -m json.tool   # for self-validation and debug
  if [[ $? -ne 0 ]];then
      log_it echo "Invalid json in rule"
      exit 42
  fi
}

check_json "$RULE_NEXT_TIER"


# etcdctl is not tolerant to etcd temporary unavailibility so we use wrapper
# with increased timeouts from 2s to 30s
do_and_log etcdctl_wpr set /calico/v1/policy/tier/kuberdock-service/metadata '{"order": '$KD_SERVICE_POLICY_ORDER'}'
do_and_log etcdctl_wpr mkdir /calico/v1/policy/tier/kuberdock-service/policy
do_and_log etcdctl_wpr set /calico/v1/policy/tier/kuberdock-service/policy/next-tier "$RULE_NEXT_TIER"
do_and_log etcdctl_wpr set /calico/v1/policy/tier/kuberdock-hosts/metadata '{"order": '$KD_HOSTS_POLICY_ORDER'}'
do_and_log etcdctl_wpr mkdir /calico/v1/policy/tier/kuberdock-hosts/policy
do_and_log etcdctl_wpr set /calico/v1/policy/tier/kuberdock-hosts/policy/next-tier "$RULE_NEXT_TIER"

# Calico tiered policy to allow some traffic on nodes:
# * elasticsearch (tcp 9200) from master
# * cadvisor (tcp 4194) from master
# * all outbound traffic from nodes
#
# We will add endpoints for all nodes ('host endpoints', see
# http://docs.projectcalico.org/en/latest/etcd-data-model.html#endpoint-data).
# This will close all traffic to and from nodes, so we should explicitly allow
# what we need. Also we create failsafe rules as recommended in
# http://docs.projectcalico.org/en/latest/bare-metal.html#failsafe-rules
# Role name for KD host endpoint
KD_HOST_ROLE=kdnode
# Role name for kuberdock master host
KD_MASTER_ROLE=kdmaster

MASTER_TUNNEL_IP=$(etcdctl get /calico/v1/host/$HOSTNAME/config/IpInIpTunnelAddr)


# This next tier policy is needed for traffic that will come from pods
# and is not match any deny rules. Those deny rule will be created for each
# node when node is added.
KD_NODES_NEXT_TIER_FOR_PODS='{
    "id": "kd-nodes-dont-drop-pods-traffic",
    "selector": "has(kuberdock-pod-uid)",
    "order": 50,
    "inbound_rules": [{"action": "next-tier"}],
    "outbound_rules": [{"action": "next-tier"}]
}'

KD_NODES_POLICY='{
    "id": "kd-nodes-public",
    "selector": "role==\"'$KD_HOST_ROLE'\"",
    "order": 100,
    "inbound_rules": [
        {
            "src_net": "'"$MASTER_IP"'/32",
            "action": "allow"
        },
        {
            "src_net": "'"$MASTER_TUNNEL_IP"'/32",
            "action": "allow"
        },
        {
            "protocol": "tcp",
            "dst_ports": [22],
            "action": "allow"
        }
    ],
    "outbound_rules": [{"action": "allow"}]
}'

check_json "$KD_NODES_POLICY"
do_and_log etcdctl_wpr set /calico/v1/policy/tier/kuberdock-nodes/metadata '{"order": '$KD_NODES_POLICY_ORDER'}'
do_and_log etcdctl_wpr set /calico/v1/policy/tier/kuberdock-nodes/policy/kuberdock-nodes "$KD_NODES_POLICY"

check_json "$KD_NODES_NEXT_TIER_FOR_PODS"
do_and_log etcdctl_wpr set /calico/v1/policy/tier/kuberdock-nodes/policy/pods-next-tier "$KD_NODES_NEXT_TIER_FOR_PODS"

# Master host isolation
# 22 - ssh
# 80, 443 - KD API & web server
# 6443 - kube-api server secure
# 2379 - etcd secure
# 8123, 8118 open ports for cpanel flannel (??) and kube-proxy
MASTER_PUBLIC_TCP_PORTS='[22, 80, 443, 6443, 2379, 8123, 8118]'

# 123 - ntp
MASTER_PUBLIC_UDP_PORTS='[123]'

KD_MASTER_POLICY='{
    "id": "kdmaster-public",
    "selector": "role==\"'$KD_MASTER_ROLE'\"",
    "order": 200,
    "inbound_rules": [
        {
            "protocol": "tcp",
            "dst_ports": '"$MASTER_PUBLIC_TCP_PORTS"',
            "action": "allow"
        },
        {
            "protocol": "udp",
            "dst_ports": '"$MASTER_PUBLIC_UDP_PORTS"',
            "action": "allow"
        },
        {
            "action": "next-tier"
        }
    ],
    "outbound_rules": [{"action": "allow"}]
}'
check_json "$KD_MASTER_POLICY"
do_and_log etcdctl_wpr set /calico/v1/policy/tier/kuberdock-nodes/policy/kuberdock-master "$KD_MASTER_POLICY"


# Here we allow all traffic from master to calico subnet. It is a
# workaround and it must be rewritten to specify more secure policy
# for access from master to some services.
KD_NODES_FAILSAFE_POLICY='{
    "id": "failsafe-all",
    "selector": "all()",
    "order": 100,

    "inbound_rules": [
        {"protocol": "icmp", "action": "allow"},
        {
            "dst_net": "'$CALICO_NETWORK'",
            "src_net": "'$MASTER_TUNNEL_IP'/32",
            "action": "allow"
        },
        {"action": "next-tier"}
    ],
    "outbound_rules": [
        {
            "protocol": "tcp",
            "dst_ports": [2379],
            "dst_net": "'$MASTER_IP'/32",
            "action": "allow"
        },
        {
            "src_net": "'$MASTER_TUNNEL_IP'/32",
            "action": "allow"
        },
        {"protocol": "udp", "dst_ports": [67], "action": "allow"},
        {"action": "next-tier"}
    ]
}'
check_json "$KD_NODES_FAILSAFE_POLICY"
do_and_log etcdctl_wpr set /calico/v1/policy/tier/failsafe/metadata '{"order": '$KD_NODES_FAILSAFE_POLICY_ORDER'}'
do_and_log etcdctl_wpr set /calico/v1/policy/tier/failsafe/policy/failsafe "$KD_NODES_FAILSAFE_POLICY"

# Add master as calico host endpoint
MASTER_HOST_ENDPOINT='{
    "expected_ipv4_addrs": ["'$MASTER_IP'"],
    "labels": {"role": "'$KD_MASTER_ROLE'"},
    "profile_ids": []
}'
check_json "$MASTER_HOST_ENDPOINT"
do_and_log etcdctl_wpr set /calico/v1/host/$HOSTNAME/endpoint/$HOSTNAME "$MASTER_HOST_ENDPOINT"

#16. Adding amazon and ceph config data
if [ "$ISAMAZON" = true ];then
cat >> $KUBERDOCK_MAIN_CONFIG << EOF
AWS = yes
REGION = $REGION
AVAILABILITY_ZONE = $AVAILABILITY_ZONE
AWS_ACCESS_KEY_ID = $AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY = $AWS_SECRET_ACCESS_KEY
AWS_EBS_DEFAULT_SIZE = $AWS_EBS_DEFAULT_SIZE
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

if [ "$WITH_TESTING" = yes ]; then
    echo "WITH_TESTING = yes" >> $KUBERDOCK_MAIN_CONFIG
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

# 19. Generate random secret key
SEC_KEY=$(cat /dev/urandom | base64 | tr -d "=+/" | dd bs=32 count=1 2> /dev/null)
echo "SECRET_KEY=$SEC_KEY" >> $KUBERDOCK_MAIN_CONFIG

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
    for i in nginx emperor.uwsgi redis postgresql influxdb kuberdock-k8s2etcd etcd \
             kube-apiserver kube-controller-manager kube-scheduler heapster docker;do
        log_it systemctl disable $i
    done
    for i in nginx emperor.uwsgi kube-apiserver kube-controller-manager kuberdock-k8s2etcd kube-scheduler \
             heapster;do
        log_it systemctl stop $i
    done

    log_it echo -e "Deleting custom kuberdock-k8s2etcd.service..."
    log_it rm /etc/systemd/system/kuberdock-k8s2etcd.service
    log_it systemctl daemon-reload

    log_it echo "Cleaning up etcd..."
    log_it etcdctl rm --recursive /registry
    log_it etcdctl rm --recursive /kuberdock
    log_it etcdctl rm --recursive /calico
    log_it echo "Cleaning up redis..."
    log_it redis-cli flushall
    log_it echo "Cleaning up influxdb..."
    influx -execute "drop database k8s"
    for i in redis influxdb etcd docker;do
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
                log_it rm -rf /var/lib/pgsql/*
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
    log_it yum -y remove kuberdock ntp etcd-ca bridge-utils docker
    log_it yum -y autoremove

    log_it echo "Remove old repos..."
    log_it rm -f /etc/yum.repos.d/kube-cloudlinux.repo \
                 /etc/yum.repos.d/kube-cloudlinux-testing.repo

    log_it echo "Remove dirs..."
    for i in /var/run/kubernetes /etc/kubernetes /etc/pki/kube-apiserver/ /root/.etcd-ca \
             /var/opt/kuberdock /var/lib/kuberdock /etc/sysconfig/kuberdock /etc/pki/etcd \
             /etc/etcd/etcd.conf /var/lib/etcd /var/lib/docker \
             /var/log/calico /var/run/calico /opt/bin/calicoctl /opt/bin/policy \
             "$NGINX_SHARED_ETCD"; do
        rm -rf $i
    done

}



#########
# Start #
#########

if [ "$CLEANUP" = yes ];then
    catchFailure do_cleanup
else
    catchFailure do_deploy
fi
