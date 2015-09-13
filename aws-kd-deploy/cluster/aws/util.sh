#!/bin/bash

# Copyright 2014 The Kubernetes Authors All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# A library of helper functions and constant for the local config.

# Use the config file specified in $KUBE_CONFIG_FILE, or default to
# config-default.sh.
KUBE_ROOT=$(dirname "${BASH_SOURCE}")/../..
source "${KUBE_ROOT}/cluster/aws/${KUBE_CONFIG_FILE-"config-default.sh"}"
# source "${KUBE_ROOT}/cluster/common.sh"

#case "${KUBE_OS_DISTRIBUTION}" in
#  ubuntu|coreos)
#    echo "Starting cluster using os distro: ${KUBE_OS_DISTRIBUTION}" >&2
#    source "${KUBE_ROOT}/cluster/aws/${KUBE_OS_DISTRIBUTION}/util.sh"
#    ;;
#  *)
#    echo "Cannot start cluster using os distro: ${KUBE_OS_DISTRIBUTION}" >&2
#    exit 2
#    ;;
#esac

# This removes the final character in bash (somehow)
AWS_REGION=${ZONE%?}

export AWS_DEFAULT_REGION=${AWS_REGION}
AWS_CMD="aws --output json ec2"
AWS_ELB_CMD="aws --output json elb"

INTERNAL_IP_BASE=172.20.0
MASTER_IP_SUFFIX=.9
MASTER_INTERNAL_IP=${INTERNAL_IP_BASE}${MASTER_IP_SUFFIX}

function json_val {
    python -c 'import json,sys;obj=json.load(sys.stdin);print obj'$1''
}

# TODO (ayurchuk) Refactor the get_* functions to use filters
# TODO (bburns) Parameterize this for multiple cluster per project

function get_vpc_id {
  $AWS_CMD --output text describe-vpcs \
           --filters Name=tag:Name,Values=kubernetes-vpc \
                     Name=tag:KubernetesCluster,Values=${CLUSTER_ID} \
           --query Vpcs[].VpcId
}

function get_subnet_id {
  python -c "import json,sys; lst = [str(subnet['SubnetId']) for subnet in json.load(sys.stdin)['Subnets'] if subnet['VpcId'] == '$1' and subnet['AvailabilityZone'] == '$2']; print ''.join(lst)"
}

function get_cidr {
  python -c "import json,sys; lst = [str(subnet['CidrBlock']) for subnet in json.load(sys.stdin)['Subnets'] if subnet['VpcId'] == '$1' and subnet['AvailabilityZone'] == '$2']; print ''.join(lst)"
}

function get_igw_id {
  python -c "import json,sys; lst = [str(igw['InternetGatewayId']) for igw in json.load(sys.stdin)['InternetGateways'] for attachment in igw['Attachments'] if attachment['VpcId'] == '$1']; print ''.join(lst)"
}

function get_route_table_id {
  python -c "import json,sys; lst = [str(route_table['RouteTableId']) for route_table in json.load(sys.stdin)['RouteTables'] if route_table['VpcId'] == '$1']; print ''.join(lst)"
}

function get_elbs_in_vpc {
 # ELB doesn't seem to be on the same platform as the rest of AWS; doesn't support filtering
  $AWS_ELB_CMD describe-load-balancers | \
    python -c "import json,sys; lst = [str(lb['LoadBalancerName']) for lb in json.load(sys.stdin)['LoadBalancerDescriptions'] if lb['VPCId'] == '$1']; print '\n'.join(lst)"
}

function expect_instance_states {
  python -c "import json,sys; lst = [str(instance['InstanceId']) for reservation in json.load(sys.stdin)['Reservations'] for instance in reservation['Instances'] if instance['State']['Name'] != '$1']; print ' '.join(lst)"
}

function get_instance_public_ip {
  local tagName=$1
  $AWS_CMD --output text describe-instances \
    --filters Name=tag:Name,Values=${tagName} \
              Name=instance-state-name,Values=running \
              Name=tag:KubernetesCluster,Values=${CLUSTER_ID} \
    --query Reservations[].Instances[].NetworkInterfaces[0].Association.PublicIp
}

function get_instance_private_ip {
  local tagName=$1
  $AWS_CMD --output text describe-instances \
    --filters Name=tag:Name,Values=${tagName} \
              Name=instance-state-name,Values=running \
              Name=tag:KubernetesCluster,Values=${CLUSTER_ID} \
    --query Reservations[].Instances[].NetworkInterfaces[0].PrivateIpAddress
}

function detect-master () {
  KUBE_MASTER=${MASTER_NAME}
  if [[ -z "${KUBE_MASTER_IP-}" ]]; then
    KUBE_MASTER_IP=$(get_instance_public_ip $MASTER_NAME)
  fi
  if [[ -z "${KUBE_MASTER_IP-}" ]]; then
    echo "Could not detect Kubernetes master node.  Make sure you've launched a cluster with 'kube-up.sh'"
    exit 1
  fi
  echo "Using master: $KUBE_MASTER (external IP: $KUBE_MASTER_IP)"
}

function detect-nodes () {
  KUBE_NODE_IP_ADDRESSES=()
  for (( i=0; i<${#NODE_NAMES[@]}; i++)); do
    local node_ip
    if [[ "${ENABLE_NODE_PUBLIC_IP}" == "true" ]]; then
      node_ip=$(get_instance_public_ip ${NODE_NAMES[$i]})
    else
      node_ip=$(get_instance_private_ip ${NODE_NAMES[$i]})
    fi
    echo "Found ${NODE_NAMES[$i]} at ${node_ip}"
    KUBE_NODE_IP_ADDRESSES+=("${node_ip}")
  done
  if [[ -z "$KUBE_NODE_IP_ADDRESSES" ]]; then
    echo "Could not detect Kubernetes node nodes.  Make sure you've launched a cluster with 'kube-up.sh'"
    exit 1
  fi
}

# Detects the AMI to use (considering the region)
#
# Vars set:
#   AWS_IMAGE
function detect-image () {
  # This is the centos 7 image for <region>, amd64, hvm:ebs-ssd
  # This will need to be updated from time to time as amis are deprecated
  if [[ -z "${AWS_IMAGE-}" ]]; then
    case "${AWS_REGION}" in
      ap-northeast-1)
        AWS_IMAGE=ami-89634988
        ;;

      ap-southeast-1)
        AWS_IMAGE=ami-aea582fc
        ;;

      eu-west-1)
        AWS_IMAGE=ami-e4ff5c93
        ;;

      sa-east-1)
        AWS_IMAGE=ami-bf9520a2
        ;;

      us-east-1)
        AWS_IMAGE=ami-96a818fe
        ;;

      us-west-1)
        AWS_IMAGE=ami-6bcfc42e
        ;;

      ap-southeast-2)
        AWS_IMAGE=ami-cd4e3ff7
        ;;

      us-west-2)
        AWS_IMAGE=ami-c7d092f7
        ;;

      *)
        echo "Please specify AWS_IMAGE directly (region not recognized)"
        exit 1
    esac
  fi
}

# Verify prereqs
function verify-prereqs {
  if [[ "$(which aws)" == "" ]]; then
    echo "Can't find aws in PATH, please fix and retry."
    exit 1
  fi
}


# Create a temp dir that'll be deleted at the end of this bash session.
#
# Vars set:
#   KUBE_TEMP
function ensure-temp-dir {
  if [[ -z ${KUBE_TEMP-} ]]; then
    KUBE_TEMP=$(mktemp -d -t kubernetes.XXXXXX)
    trap 'rm -rf "${KUBE_TEMP}"' EXIT
  fi
}

# Verify and find the various tar files that we are going to use on the server.
#
# Vars set:
#   SERVER_BINARY_TAR
#   SALT_TAR
function find-release-tars {
  SERVER_BINARY_TAR="${KUBE_ROOT}/server/kubernetes-server-linux-amd64.tar.gz"
  if [[ ! -f "$SERVER_BINARY_TAR" ]]; then
    SERVER_BINARY_TAR="${KUBE_ROOT}/_output/release-tars/kubernetes-server-linux-amd64.tar.gz"
  fi
  if [[ ! -f "$SERVER_BINARY_TAR" ]]; then
    echo "!!! Cannot find kubernetes-server-linux-amd64.tar.gz"
    exit 1
  fi

  SALT_TAR="${KUBE_ROOT}/server/kubernetes-salt.tar.gz"
  if [[ ! -f "$SALT_TAR" ]]; then
    SALT_TAR="${KUBE_ROOT}/_output/release-tars/kubernetes-salt.tar.gz"
  fi
  if [[ ! -f "$SALT_TAR" ]]; then
    echo "!!! Cannot find kubernetes-salt.tar.gz"
    exit 1
  fi
}


# Ensure that we have a password created for validating to the master.  Will
# read from kubeconfig for the current context if available.
#
# Assumed vars
#   KUBE_ROOT
#
# Vars set:
#   KUBE_USER
#   KUBE_PASSWORD
function get-password {
  get-kubeconfig-basicauth
  if [[ -z "${KUBE_USER}" || -z "${KUBE_PASSWORD}" ]]; then
    KUBE_USER=admin
    KUBE_PASSWORD=$(python -c 'import string,random; print "".join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(16))')
  fi
}

# Adds a tag to an AWS resource
# usage: add-tag <resource-id> <tag-name> <tag-value>
function add-tag {
  echo "Adding tag to ${1}: ${2}=${3}"

  # We need to retry in case the resource isn't yet fully created
  sleep 3
  n=0
  until [ $n -ge 5 ]; do
    $AWS_CMD create-tags --resources ${1} --tags Key=${2},Value=${3} > $LOG && return
    n=$[$n+1]
    sleep 15
  done

  echo "Unable to add tag to AWS resource"
  exit 1
}

# Creates the IAM profile, based on configuration files in templates/iam
function create-iam-profile {
  local key=$1

  local conf_dir=file://${KUBE_ROOT}/cluster/aws/templates/iam

  echo "Creating IAM role: ${key}"
  aws iam create-role --role-name ${key} --assume-role-policy-document ${conf_dir}/${key}-role.json > $LOG

  echo "Creating IAM role-policy: ${key}"
  aws iam put-role-policy --role-name ${key} --policy-name ${key} --policy-document ${conf_dir}/${key}-policy.json > $LOG

  echo "Creating IAM instance-policy: ${key}"
  aws iam create-instance-profile --instance-profile-name ${key} > $LOG

  echo "Adding IAM role to instance-policy: ${key}"
  aws iam add-role-to-instance-profile --instance-profile-name ${key} --role-name ${key} > $LOG
}

# Creates the IAM roles (if they do not already exist)
function ensure-iam-profiles {
  aws iam get-instance-profile --instance-profile-name ${IAM_PROFILE_MASTER} || {
    echo "Creating master IAM profile: ${IAM_PROFILE_MASTER}"
    create-iam-profile ${IAM_PROFILE_MASTER}
  }
  aws iam get-instance-profile --instance-profile-name ${IAM_PROFILE_NODE} || {
    echo "Creating node IAM profile: ${IAM_PROFILE_NODE}"
    create-iam-profile ${IAM_PROFILE_NODE}
  }
}

# Wait for instance to be in running state
function wait-for-instance-running {
  instance_id=$1
  while true; do
    instance_state=$($AWS_CMD describe-instances --instance-ids ${instance_id} | expect_instance_states running)
    if [[ "$instance_state" == "" ]]; then
      break
    else
      echo "Waiting for instance ${instance_id} to spawn"
      echo "Sleeping for 3 seconds..."
      sleep 3
    fi
  done
}

# Allocates new Elastic IP from Amazon
# Output: allocated IP address
function allocate-elastic-ip {
  $AWS_CMD allocate-address --domain vpc --output text | cut -f3
}

function assign-ip-to-instance {
  local ip_address=$1
  local instance_id=$2
  local fallback_ip=$3

  local elastic_ip_allocation_id=$($AWS_CMD describe-addresses --public-ips $ip_address --output text | cut -f2)
  local association_result=$($AWS_CMD associate-address --instance-id ${master_instance_id} --allocation-id ${elastic_ip_allocation_id} > /dev/null && echo "success" || echo "failure")

  if [[ $association_result = "success" ]]; then
    echo "${ip_address}"
  else
    echo "${fallback_ip}"
  fi
}

# If MASTER_RESERVED_IP looks like IP address, will try to assign it to master instance
# If MASTER_RESERVED_IP is "auto", will allocate new elastic ip and assign that
# If none of the above or something fails, will output originally assigne IP
# Output: assigned IP address
function assign-elastic-ip {
  local assigned_public_ip=$1
  local master_instance_id=$2

  # Check that MASTER_RESERVED_IP looks like an IPv4 address
  if [[ "${MASTER_RESERVED_IP}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    assign-ip-to-instance "${MASTER_RESERVED_IP}" "${master_instance_id}" "${assigned_public_ip}"
  elif [[ "${MASTER_RESERVED_IP}" = "auto" ]]; then
    assign-ip-to-instance $(allocate-elastic-ip) "${master_instance_id}" "${assigned_public_ip}"
  else
    echo "${assigned_public_ip}"
  fi
}


function kube-up {

  # check if aws credentials are set up

  if [ -z ${AWS_ACCESS_KEY_ID-} ] || [ -z ${AWS_SECRET_ACCESS_KEY-} ] ; then
  echo "Please export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY variables and re-run this script"
  exit 1
  fi


  get-tokens

  detect-image
  detect-node-image

  ensure-temp-dir

  ensure-iam-profiles


  # get-password


  if [[ ! -f "$AWS_SSH_KEY" ]]; then
    ssh-keygen -f "$AWS_SSH_KEY" -N ''
  fi

  $AWS_CMD import-key-pair --key-name kubernetes --public-key-material "file://$AWS_SSH_KEY.pub" > $LOG 2>&1 || true

  VPC_ID=$(get_vpc_id)

  if [[ -z "$VPC_ID" ]]; then
	  echo "Creating vpc."
	  VPC_ID=$($AWS_CMD create-vpc --cidr-block $INTERNAL_IP_BASE.0/16 | json_val '["Vpc"]["VpcId"]')
	  $AWS_CMD modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-support '{"Value": true}' > $LOG
	  $AWS_CMD modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-hostnames '{"Value": true}' > $LOG
	  add-tag $VPC_ID Name kubernetes-vpc
	  add-tag $VPC_ID KubernetesCluster ${CLUSTER_ID}
  fi

  echo "Using VPC $VPC_ID"

  SUBNET_ID=$($AWS_CMD describe-subnets | get_subnet_id $VPC_ID $ZONE)
  if [[ -z "$SUBNET_ID" ]]; then
    echo "Creating subnet."
    SUBNET_ID=$($AWS_CMD create-subnet --cidr-block $INTERNAL_IP_BASE.0/24 --vpc-id $VPC_ID --availability-zone ${ZONE} | json_val '["Subnet"]["SubnetId"]')
  else
    EXISTING_CIDR=$($AWS_CMD describe-subnets | get_cidr $VPC_ID $ZONE)
    echo "Using existing CIDR $EXISTING_CIDR"
    INTERNAL_IP_BASE=${EXISTING_CIDR%.*}
    MASTER_INTERNAL_IP=${INTERNAL_IP_BASE}${MASTER_IP_SUFFIX}
  fi

  echo "Using subnet $SUBNET_ID"

  IGW_ID=$($AWS_CMD describe-internet-gateways | get_igw_id $VPC_ID)
  if [[ -z "$IGW_ID" ]]; then
	  echo "Creating Internet Gateway."
	  IGW_ID=$($AWS_CMD create-internet-gateway | json_val '["InternetGateway"]["InternetGatewayId"]')
	  $AWS_CMD attach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID > $LOG
  fi

  echo "Using Internet Gateway $IGW_ID"

  echo "Associating route table."
  ROUTE_TABLE_ID=$($AWS_CMD describe-route-tables --filters Name=vpc-id,Values=$VPC_ID | json_val '["RouteTables"][0]["RouteTableId"]')
  $AWS_CMD associate-route-table --route-table-id $ROUTE_TABLE_ID --subnet-id $SUBNET_ID > $LOG || true
  echo "Configuring route table."
  $AWS_CMD describe-route-tables --filters Name=vpc-id,Values=$VPC_ID > $LOG || true
  echo "Adding route to route table."
  $AWS_CMD create-route --route-table-id $ROUTE_TABLE_ID --destination-cidr-block 0.0.0.0/0 --gateway-id $IGW_ID > $LOG || true

  echo "Using Route Table $ROUTE_TABLE_ID"

  SEC_GROUP_ID=$($AWS_CMD --output text describe-security-groups \
                          --filters Name=vpc-id,Values=$VPC_ID \
                                    Name=group-name,Values=kubernetes-sec-group \
                          --query SecurityGroups[].GroupId \
                    | tr "\t" "\n")

  if [[ -z "$SEC_GROUP_ID" ]]; then
	  echo "Creating security group."
	  SEC_GROUP_ID=$($AWS_CMD create-security-group --group-name kubernetes-sec-group --description kubernetes-sec-group --vpc-id $VPC_ID | json_val '["GroupId"]')
	  $AWS_CMD authorize-security-group-ingress --group-id $SEC_GROUP_ID --protocol -1 --port all --cidr 0.0.0.0/0 > $LOG
  fi
  (
    # We pipe this to the ami as a startup script in the user-data field.  Requires a compatible ami
    echo "#! /bin/bash"
    echo "# /usr/bin/yum -y update"
    echo "readonly AWS_ACCESS_KEY_ID='${AWS_ACCESS_KEY_ID}'"
    echo "readonly AWS_SECRET_ACCESS_KEY='${AWS_SECRET_ACCESS_KEY}'"
  ) > "${KUBE_TEMP}/master-start.sh"

  echo "Starting Master"
  master_id=$($AWS_CMD run-instances \
    --image-id $AWS_IMAGE \
    --iam-instance-profile Name=$IAM_PROFILE_MASTER \
    --instance-type $MASTER_SIZE \
    --subnet-id $SUBNET_ID \
    --private-ip-address $MASTER_INTERNAL_IP \
    --key-name kubernetes \
    --security-group-ids $SEC_GROUP_ID \
    --associate-public-ip-address \
    --user-data file://${KUBE_TEMP}/master-start.sh | json_val '["Instances"][0]["InstanceId"]')
  add-tag $master_id Name $MASTER_NAME
  add-tag $master_id Role $MASTER_TAG
  add-tag $master_id KubernetesCluster ${CLUSTER_ID}

  echo "Waiting for master to be ready"

  local attempt=0

   while true; do
    echo -n Attempt "$(($attempt+1))" to check for master node
    local ip=$(get_instance_public_ip $MASTER_NAME)
    if [[ -z "${ip}" ]]; then
      if (( attempt > 30 )); then
        echo
        echo -e "${color_red}master failed to start. Your cluster is unlikely" >&2
        echo "to work correctly. Please run ./cluster/kube-down.sh and re-create the" >&2
        echo -e "cluster. (sorry!)${color_norm}" >&2
        exit 1
      fi
    else
      KUBE_MASTER=${MASTER_NAME}
      KUBE_MASTER_IP=$(assign-elastic-ip $ip $master_id)
      echo -e " ${color_green}[master running @${KUBE_MASTER_IP}]${color_norm}"

      # We are not able to add a route to the instance until that instance is in "running" state.
      wait-for-instance-running $master_id
      sleep 10
      $AWS_CMD create-route --route-table-id $ROUTE_TABLE_ID --destination-cidr-block ${MASTER_IP_RANGE} --instance-id $master_id > $LOG

      break
    fi
    echo -e " ${color_yellow}[master not working yet]${color_norm}"
    attempt=$(($attempt+1))
    sleep 10
  done

  NODE_IDS=()
  for (( i=0; i<${#NODE_NAMES[@]}; i++)); do
    echo "Starting Node (${NODE_NAMES[$i]})"
    generate-node-user-data $i > "${KUBE_TEMP}/node-user-data-${i}"

    local public_ip_option
    if [[ "${ENABLE_NODE_PUBLIC_IP}" == "true" ]]; then
      public_ip_option="--associate-public-ip-address"
    else
      public_ip_option="--no-associate-public-ip-address"
    fi

    node_id=$($AWS_CMD run-instances \
      --image-id $KUBE_NODE_IMAGE \
      --iam-instance-profile Name=$IAM_PROFILE_NODE \
      --instance-type $NODE_SIZE \
      --subnet-id $SUBNET_ID \
      --private-ip-address $INTERNAL_IP_BASE.1${i} \
      --key-name kubernetes \
      --security-group-ids $SEC_GROUP_ID \
      ${public_ip_option} \
      --user-data "file://${KUBE_TEMP}/node-user-data-${i}" | json_val '["Instances"][0]["InstanceId"]')

    add-tag $node_id Name ${NODE_NAMES[$i]}
    add-tag $node_id Role $NODE_TAG
    add-tag $node_id KubernetesCluster ${CLUSTER_ID}

    NODE_IDS[$i]=$node_id
  done

  # Add routes to nodes
  for (( i=0; i<${#NODE_NAMES[@]}; i++)); do
    # We are not able to add a route to the instance until that instance is in "running" state.
    # This is quite an ugly solution to this problem. In Bash 4 we could use assoc. arrays to do this for
    # all instances at once but we can't be sure we are running Bash 4.
    node_id=${NODE_IDS[$i]}
    wait-for-instance-running $node_id
    echo "Node ${NODE_NAMES[$i]} running"
    sleep 10
    $AWS_CMD modify-instance-attribute --instance-id $node_id --source-dest-check '{"Value": false}' > $LOG
    $AWS_CMD create-route --route-table-id $ROUTE_TABLE_ID --destination-cidr-block ${NODE_IP_RANGES[$i]} --instance-id $node_id > $LOG
  done

  FAIL=0
  for job in `jobs -p`; do
    wait $job || let "FAIL+=1"
  done
  if (( $FAIL != 0 )); then
    echo "${FAIL} commands failed.  Exiting."
    exit 2
  fi


    ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" -tt "${EC2_USER}@${KUBE_MASTER_IP}" "stty raw -echo; sudo yum -y update | cat" < <(cat) 2>"$LOG"
    ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" -tt "${EC2_USER}@${KUBE_MASTER_IP}" "stty raw -echo; sudo yum -y install wget | cat" < <(cat) 2>"$LOG"
    ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" -tt "${EC2_USER}@${KUBE_MASTER_IP}" "stty raw -echo; wget ${DEPLOY_SH} | cat" < <(cat) 2>"$LOG"

    ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" -tt "${EC2_USER}@${KUBE_MASTER_IP}" "sudo ROUTE_TABLE_ID=${ROUTE_TABLE_ID} AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} bash -l deploy.sh | cat" < <(cat) 2>"$LOG"

    ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" -tt "${EC2_USER}@${KUBE_MASTER_IP}" mkdir /home/${EC2_USER}/kuberdock-files  2>"$LOG"
    ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" -tt "${EC2_USER}@${KUBE_MASTER_IP}" cp /var/opt/kuberdock/{node_install.sh,pd.sh} /etc/pki/etcd/ca.crt /etc/pki/etcd/etcd-client.crt /etc/pki/etcd/etcd-client.key /home/${EC2_USER}/kuberdock-files 2>"$LOG"
    ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" -tt "${EC2_USER}@${KUBE_MASTER_IP}" "sudo cp /var/lib/nginx/.ssh/id_rsa.pub /home/${EC2_USER}/kuberdock-files" 2>"$LOG"
    ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" -tt "${EC2_USER}@${KUBE_MASTER_IP}" "sudo chown ${EC2_USER} /home/${EC2_USER}/kuberdock-files/*" < <(cat) 2>"$LOG"

    scp -q -r -i "${AWS_SSH_KEY}"  ${EC2_USER}@${KUBE_MASTER_IP}:/home/${EC2_USER}/kuberdock-files ${KUBE_ROOT}

    CUR_MASTER_KUBERNETES=$(ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" "${EC2_USER}@${KUBE_MASTER_IP}" rpm -q kubernetes-master --qf "%{version}-%{release}")

  echo "Kubernetes cluster created."

    detect-master > $LOG
    detect-nodes > $LOG

  # Basic sanity checking
  local rc # Capture return code without exiting because of errexit bash option
  for (( i=0; i<${#NODE_NAMES[@]}; i++)); do
  NODE_HOSTNAME=$(ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" "${EC2_USER}@${KUBE_NODE_IP_ADDRESSES[$i]}" hostname -f)
	echo "Configuring node ${NODE_HOSTNAME}"
	scp -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" -q -r ${KUBE_ROOT}/kuberdock-files ${EC2_USER}@${KUBE_NODE_IP_ADDRESSES[$i]}:/home/${EC2_USER}/
	ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" -tt "${EC2_USER}@${KUBE_NODE_IP_ADDRESSES[$i]}" "sudo cp /home/${EC2_USER}/kuberdock-files/* /" < <(cat) 2>"$LOG"
	ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" -tt "${EC2_USER}@${KUBE_NODE_IP_ADDRESSES[$i]}" "sudo mkdir -p /var/lib/kuberdock/scripts" < <(cat) 2>"$LOG"
	ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" -tt "${EC2_USER}@${KUBE_NODE_IP_ADDRESSES[$i]}" "sudo cp /id_rsa.pub /root/.ssh/authorized_keys" < <(cat) 2>"$LOG"
	echo "Adding node"
	ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" -tt "${EC2_USER}@${KUBE_MASTER_IP}" "python /var/opt/kuberdock/manage.py add_node --hostname=${NODE_HOSTNAME} --kube-type=0 --do-deploy" < <(cat) 2>"$LOG"

  done

  rm -rf ${KUBE_ROOT}/kuberdock-files

  echo
  echo -e "Kuberdock cluster is running.  The master is running at:"
  echo
  echo -e "https://${KUBE_MASTER_IP}"
  echo
  echo -e "User name: admin"
  ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" "${EC2_USER}@${KUBE_MASTER_IP}" grep password /var/log/kuberdock_master_deploy.log

}

function kube-down {
  local vpc_id=$(get_vpc_id)
  if [[ -n "${vpc_id}" ]]; then
    local elb_ids=$(get_elbs_in_vpc ${vpc_id})
    if [[ -n "${elb_ids}" ]]; then
      echo "Deleting ELBs in: ${vpc_id}"
      for elb_id in ${elb_ids}; do
        $AWS_ELB_CMD delete-load-balancer --load-balancer-name=${elb_id}
      done

      echo "Waiting for ELBs to be deleted"
      while true; do
        elb_ids=$(get_elbs_in_vpc ${vpc_id})
        if [[ -z "$elb_ids"  ]]; then
          echo "All ELBs deleted"
          break
        else
          echo "ELBs not yet deleted: $elb_ids"
          echo "Sleeping for 3 seconds..."
          sleep 3
        fi
      done
    fi

    echo "Deleting instances in VPC: ${vpc_id}"
    instance_ids=$($AWS_CMD --output text describe-instances \
                            --filters Name=vpc-id,Values=${vpc_id} \
                                      Name=tag:KubernetesCluster,Values=${CLUSTER_ID} \
                            --query Reservations[].Instances[].InstanceId)
    if [[ -n "${instance_ids}" ]]; then
      $AWS_CMD terminate-instances --instance-ids ${instance_ids} > $LOG
      echo "Waiting for instances to be deleted"
      while true; do
        local instance_states=$($AWS_CMD describe-instances --instance-ids ${instance_ids} | expect_instance_states terminated)
        if [[ -z "${instance_states}" ]]; then
          echo "All instances deleted"
          break
        else
          echo "Instances not yet deleted: ${instance_states}"
          echo "Sleeping for 3 seconds..."
          sleep 3
        fi
      done
    fi

    echo "Deleting VPC: ${vpc_id}"
    default_sg_id=$($AWS_CMD --output text describe-security-groups \
                             --filters Name=vpc-id,Values=${vpc_id} Name=group-name,Values=default \
                             --query SecurityGroups[].GroupId \
                    | tr "\t" "\n")
    sg_ids=$($AWS_CMD --output text describe-security-groups \
                      --filters Name=vpc-id,Values=${vpc_id} \
                      --query SecurityGroups[].GroupId \
             | tr "\t" "\n")
    for sg_id in ${sg_ids}; do
      # EC2 doesn't let us delete the default security group
      if [[ "${sg_id}" != "${default_sg_id}" ]]; then
        $AWS_CMD delete-security-group --group-id ${sg_id} > $LOG
      fi
    done

    subnet_ids=$($AWS_CMD --output text describe-subnets \
                          --filters Name=vpc-id,Values=${vpc_id} \
                          --query Subnets[].SubnetId \
             | tr "\t" "\n")
    for subnet_id in ${subnet_ids}; do
      $AWS_CMD delete-subnet --subnet-id ${subnet_id} > $LOG
    done

    igw_ids=$($AWS_CMD --output text describe-internet-gateways \
                       --filters Name=attachment.vpc-id,Values=${vpc_id} \
                       --query InternetGateways[].InternetGatewayId \
             | tr "\t" "\n")
    for igw_id in ${igw_ids}; do
      $AWS_CMD detach-internet-gateway --internet-gateway-id $igw_id --vpc-id $vpc_id > $LOG
      $AWS_CMD delete-internet-gateway --internet-gateway-id $igw_id > $LOG
    done

    route_table_ids=$($AWS_CMD --output text describe-route-tables \
                               --filters Name=vpc-id,Values=$vpc_id \
                                         Name=route.destination-cidr-block,Values=0.0.0.0/0 \
                               --query RouteTables[].RouteTableId \
                      | tr "\t" "\n")
    for route_table_id in ${route_table_ids}; do
      $AWS_CMD delete-route --route-table-id $route_table_id --destination-cidr-block 0.0.0.0/0 > $LOG
    done

    $AWS_CMD delete-vpc --vpc-id $vpc_id > $LOG
  fi
}

# Update a kubernetes cluster with latest source
function kube-push {
  detect-master

  # Make sure we have the tar files staged on Google Storage
  find-release-tars
  upload-server-tars

  (
    echo "#! /bin/bash"
    echo "mkdir -p /var/cache/kubernetes-install"
    echo "cd /var/cache/kubernetes-install"
    echo "readonly SERVER_BINARY_TAR_URL='${SERVER_BINARY_TAR_URL}'"
    echo "readonly SALT_TAR_URL='${SALT_TAR_URL}'"
    grep -v "^#" "${KUBE_ROOT}/cluster/aws/templates/common.sh"
    grep -v "^#" "${KUBE_ROOT}/cluster/aws/templates/download-release.sh"
    echo "echo Executing configuration"
    echo "sudo salt '*' mine.update"
    echo "sudo salt --force-color '*' state.highstate"
  ) | ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" ${EC2_USER}@${KUBE_MASTER_IP} sudo bash

  get-password

  echo
  echo "Kubernetes cluster is running.  The master is running at:"
  echo
  echo "  https://${KUBE_MASTER_IP}"
  echo

}

# -----------------------------------------------------------------------------
# Cluster specific test helpers used from hack/e2e-test.sh

# Execute prior to running tests to build a release if required for env.
#
# Assumed Vars:
#   KUBE_ROOT
function test-build-release {
  # Make a release
  "${KUBE_ROOT}/build/release.sh"
}

# Execute prior to running tests to initialize required structure. This is
# called from hack/e2e.go only when running -up (it is run after kube-up).
#
# Assumed vars:
#   Variables from config.sh
function test-setup {
  echo "test-setup complete"
}

# Execute after running tests to perform any required clean-up. This is called
# from hack/e2e.go
function test-teardown {
  echo "Shutting down test cluster."
  "${KUBE_ROOT}/cluster/kube-down.sh"
}


# SSH to a node by name ($1) and run a command ($2).
function ssh-to-node {
  local node="$1"
  local cmd="$2"

  local ip=$(get_instance_public_ip ${node})
  if [[ -z "$ip" ]]; then
    echo "Could not detect IP for ${node}."
    exit 1
  fi

  for try in $(seq 1 5); do
    if ssh -oLogLevel=quiet -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" ${EC2_USER}@${ip} "${cmd}"; then
      break
    fi
  done
}

# Restart the kube-proxy on a node ($1)
function restart-kube-proxy {
  ssh-to-node "$1" "sudo /etc/init.d/kube-proxy restart"
}

# Restart the kube-apiserver on a node ($1)
function restart-apiserver {
  ssh-to-node "$1" "sudo /etc/init.d/kube-apiserver restart"
}

# Perform preparations required to run e2e tests
function prepare-e2e() {
  # (AWS runs detect-project, I don't think we need to anything)
  # Note: we can't print anything here, or else the test tools will break with the extra output
  return
}

function get-tokens() {
  KUBELET_TOKEN=$(dd if=/dev/urandom bs=128 count=1 2>/dev/null | base64 | tr -d "=+/" | dd bs=32 count=1 2>/dev/null)
  KUBE_PROXY_TOKEN=$(dd if=/dev/urandom bs=128 count=1 2>/dev/null | base64 | tr -d "=+/" | dd bs=32 count=1 2>/dev/null)
}
#!/bin/bash

function detect-node-image() {
  if [[ -z "${KUBE_NODE_IMAGE=-}" ]]; then
    detect-image
    KUBE_NODE_IMAGE=$AWS_IMAGE
  fi
}

function generate-node-user-data {
  i=$1
  # We pipe this to the ami as a startup script in the user-data field.  Requires a compatible ami
  echo "#! /bin/bash"
  echo "SALT_MASTER='${MASTER_INTERNAL_IP}'"
  echo "NODE_IP_RANGE='${NODE_IP_RANGES[$i]}'"
  echo "DOCKER_OPTS='${EXTRA_DOCKER_OPTS:-}'"
}

function check-node() {
  local node_name=$1
  local node_ip=$2

  local output=$(ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" ${EC2_USER}@$node_ip sudo docker ps -a 2>/dev/null)
  if [[ -z "${output}" ]]; then
    ssh -oStrictHostKeyChecking=no -i "${AWS_SSH_KEY}" ${EC2_USER}@$node_ip sudo service docker start > $LOG 2>&1
    echo "not working yet"
  else
    echo "working"
  fi
}
