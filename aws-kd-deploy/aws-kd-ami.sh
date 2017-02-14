#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail


KUBERDOCK_DIR=kuberdock-files
KUBE_ROOT=$(dirname "${BASH_SOURCE}")

if [ -f "${KUBE_ROOT}/cluster/env.sh" ]; then
    source "${KUBE_ROOT}/cluster/env.sh"
fi

# AWS_CMD, AWS_SSH_KEY, AWS_SSH_KEY_NAME, SUBNET_CIDR, ssh-key-setup
source "${KUBE_ROOT}/cluster/aws/util.sh"

AMI_BASE_IMAGE=${AMI_BASE_IMAGE:-ami-66728470}
AMI_INSTANCE_TYPE=${AMI_INSTANCE_TYPE:-t2.micro}
AMI_PREFIX=${AMI_PREFIX:-kuberdock}
AMI_CLUSTER_NAME=${AMI_PREFIX}-ami
AMI_VERSION=${AMI_VERSION:-}
AWS_ACCOUNT_ID=${AMI_AWS_ACCOUNT_ID:-256284446245}
AWS_AVAILABILITY_ZONE=${AMI_AWS_AVAILABILITY_ZONE:-us-east-1b}
AWS_DEFAULT_REGION=${AWS_AVAILABILITY_ZONE%?}


DO_CLEANUP=
DO_DEPLOY="yes"
DO_HELP=
DO_IMAGE="yes"
DO_INFO=
DO_LIST=
DO_RELEASE=
DO_SETUP="yes"
FORCED_VERSION=
REGIONS="-"
SKIP_CLEANUP=
WITH_TESTING=${AMI_WITH_TESTING:-}


ami_name()      { echo "${AMI_PREFIX}-${1}-$(ami_version)"  ;}
aws_cmd()       { ${AWS_CMD} "${@}"                         ;}
aws_filter()    { echo "Name=${1},Values=${2}"              ;}
check()         { [ -n "${1:-}" ]                           ;}
check_echo()    { [ -n "${1:-}" ] && echo "${@}"            ;}
hash_file()     { md5sum "${1}" | cut -d " " -f 1           ;}

do_cleanup()    { check     "${DO_CLEANUP}"                 ;}
do_deploy()     { check     "${DO_DEPLOY}"                  ;}
do_help()       { check     "${DO_HELP}"                    ;}
do_image()      { check     "${DO_IMAGE}"                   ;}
do_info()       { check     "${DO_INFO}"                    ;}
do_list()       { check     "${DO_LIST}"                    ;}
do_release()    { check     "${DO_RELEASE}"                 ;}
do_setup()      { check     "${DO_SETUP}"                   ;}


ami_hash()
{
    local data=
    local files="
        aws-kd-deploy/aws-kd-ami.sh \
        deploy.sh \
        kuberdock.spec \
        node_install.sh \
        node_install_ami.sh \
        node_install_common.sh \
        node_prepare_ami.sh \
        "

    check_echo "${AMI_HASH:-}" && return

    pushd "${KUBE_ROOT}"/.. >> /dev/null
    AMI_HASH=$(cat ${files} | md5sum | cut -c-8)
    popd >> /dev/null

    echo "${AMI_HASH}"
}


ami_regions()
{
    if [ "${REGIONS}" = "*" ]; then
        echo \
            us-east-1 \
            us-east-2 \
            us-west-1 \
            us-west-2 \
            ca-central-1 \
            ap-south-1 \
            ap-northeast-2 \
            ap-southeast-1 \
            ap-southeast-2 \
            ap-northeast-1 \
            eu-central-1 \
            eu-west-1 \
            eu-west-2 \
            sa-east-1 \
            ;
        return
    fi

    echo "${REGIONS}" | tr ',' '\n'| sed "s/^-$/${AWS_DEFAULT_REGION}/" | sort -u | tr '\n' ' '
}


ami_version()
{
    check_echo "${FORCED_VERSION}" && return
    do_release || { check_echo "${AMI_VERSION}" && return ;}

    if do_release; then
        kd_version
    else
        ami_hash
    fi
}


aws_filter_version()
{
    aws_filter tag:KuberDockAmiVersion "$(ami_version)"
}


k8s_node_version()
{
    local version

    check_echo "${K8S_NODE_VERSION:-}" && return
    version=$(grep "Requires: kubernetes-node" "${KUBE_ROOT}"/../kuberdock.spec | cut -d ' ' -f 4 | cut -d ':' -f 2)
    K8S_NODE_VERSION=kubernetes-node-${version}

    echo "${K8S_NODE_VERSION}"
}


kd_version()
{
    local version

    check_echo "${KD_VERSION:-}" && return
    version=$(git tag -l --points-at HEAD | awk -F 'kuberdock@' '{print $2}')
    if ! check "${version}"; then
        >&2 echo "ERROR: there is no tag on the current commit"
        return 1
    fi
    KD_VERSION=${version}

    echo "${KD_VERSION}"
}


print_help()
{
    for help_line in "${@}"; do
        echo "${help_line}" | sed -e 's/^[[:space:]]*//' -e 's/^:/ /'
    done
}


scp_wrapper()
{
    scp -i "${AWS_SSH_KEY}" -o StrictHostKeyChecking=no -q "${@:3}" "${SSH_USER}@${1}:${2}"
}


ssh_wrapper()
{
    echo "ssh ${1}: ${*:2}"
    # "${@:2}" should be expanded on client side
    # shellcheck disable=SC2029
    ssh -i "${AWS_SSH_KEY}" -o StrictHostKeyChecking=no -q "${SSH_USER}@${1}" "${@:2}"
}


copy_image()
{
    local image_id
    local source_image_id
    local source_region

    source_image_id=$(get_image "${1}")

    if [ "${AWS_DEFAULT_REGION}" = "${2}" ]; then
        echo "${source_image_id}"
        return
    fi

    source_region=${AWS_DEFAULT_REGION}
    local AWS_DEFAULT_REGION=${2}

    image_id=$(get_image "${1}")
    if ! check "${image_id}"; then
        image_id=$(aws_cmd copy-image \
            --name "$(ami_name "${1}")" \
            --source-region "${source_region}" \
            --source-image-id "${source_image_id}")
        aws_cmd wait image-exists --image-ids "${image_id}"
        create_tags "${image_id}" "$(ami_name "${1}")"
        create_role_tag "${image_id}" "${1}"
    fi
    echo "${image_id}"
}


create_image()
{
    local image_id

    image_id=$(aws_cmd create-image \
        --instance-id "${instance_id}" \
        --name "$(ami_name "${1}")" \
        --query 'ImageId')
    aws_cmd wait image-exists --image-ids "${image_id}"
    create_tags "${image_id}" "$(ami_name "${1}")"
    create_role_tag "${image_id}" "${1}"

    echo "${image_id}"
}


create_internet_gateway()
{
    local internet_gateway_id

    internet_gateway_id=$(aws_cmd create-internet-gateway \
        --query 'InternetGateway.InternetGatewayId')
    wait_internet_gateway "${internet_gateway_id}"
    create_tags "${internet_gateway_id}" "${AMI_CLUSTER_NAME}"
    aws_cmd attach-internet-gateway \
        --internet-gateway-id "${internet_gateway_id}" \
        --vpc-id "${1}" >> /dev/null

    echo "${internet_gateway_id}"
}


create_role_tag()
{
    aws_cmd create-tags --resources "${1}" --tags Key=KuberDockClusterRole,Value="${2}"
}


create_route_table()
{
    local route_table_id

    route_table_id=$(aws_cmd create-route-table \
        --vpc-id "${1}" \
        --query 'RouteTable.RouteTableId')
    wait_route_table "${route_table_id}"
    create_tags "${route_table_id}" "${AMI_CLUSTER_NAME}"
    aws_cmd associate-route-table \
        --route-table-id "${route_table_id}" \
        --subnet-id "${2}" >> /dev/null
    aws_cmd create-route \
        --route-table-id "${route_table_id}" \
        --destination-cidr-block 0.0.0.0/0 \
        --gateway-id "${3}" >> /dev/null

    echo "${route_table_id}"
}


create_security_group()
{
    local security_group_id

    security_group_id=$(aws_cmd create-security-group \
        --group-name "${AMI_CLUSTER_NAME}" \
        --description "${AMI_CLUSTER_NAME}" \
        --vpc-id "${1}" \
        --query 'GroupId')
    wait_security_group "${security_group_id}"
    create_tags "${security_group_id}" "${AMI_CLUSTER_NAME}"
    aws_cmd authorize-security-group-ingress \
        --group-id "${security_group_id}" \
        --protocol tcp \
        --port 22 \
        --cidr 0.0.0.0/0 >> /dev/null

    echo "${security_group_id}"
}


create_subnet()
{
    local subnet_id

    subnet_id=$(aws_cmd create-subnet \
        --cidr-block "${SUBNET_CIDR}" \
        --vpc-id "${1}" \
        --availability-zone "${AWS_AVAILABILITY_ZONE}" \
        --query 'Subnet.SubnetId')
    aws_cmd wait subnet-available --subnet-ids "${subnet_id}"
    create_tags "${subnet_id}" "${AMI_CLUSTER_NAME}"

    echo "${subnet_id}"
}


create_tags()
{
    aws_cmd create-tags \
        --resources "${1}" \
        --tags \
            Key=Name,Value="${2}" \
            Key=KuberDockAmiVersion,Value="$(ami_version)"
}


create_vpc()
{
    local vpc_id

    vpc_id=$(aws_cmd create-vpc \
        --cidr-block "${VPC_CIDR}" \
        --query 'Vpc.VpcId')
    aws_cmd wait vpc-exists --vpc-ids "${vpc_id}"
    create_tags "${vpc_id}" "${AMI_CLUSTER_NAME}"

    echo "${vpc_id}"
}


delete_image()
{
    local snapshot_id

    for image_id in $(get_image "${1}"); do
        image_is_public "${image_id}" && continue
        snapshot_id=$(get_image_snapshot "${image_id}")
        echo "Deregister AMI:             ${image_id}"
        aws_cmd deregister-image --image-id "${image_id}"
        echo "Delete Snapshot:            ${snapshot_id}"
        aws_cmd delete-snapshot --snapshot-id "${snapshot_id}"
    done
}



delete_internet_gateway()
{
    local vpc_ids

    for internet_gateway_id in $(get_internet_gateway); do
        vpc_ids=$(aws_cmd describe-internet-gateways \
            --internet-gateway-ids "${internet_gateway_id}" \
            --query 'InternetGateways[].Attachments[].VpcId')
        for vpc_id in ${vpc_ids}; do
            aws_cmd detach-internet-gateway \
                --internet-gateway-id "${internet_gateway_id}" \
                --vpc-id "${vpc_id}"
        done
        echo "Delete Internet Gateway:    ${internet_gateway_id}"
        aws_cmd delete-internet-gateway --internet-gateway-id "${internet_gateway_id}"
    done
}


delete_route_table()
{
    for route_table_id in $(get_route_table); do
        echo "Delete Route Table:         ${route_table_id}"
        aws_cmd delete-route \
            --route-table-id "${route_table_id}" \
            --destination-cidr-block 0.0.0.0/0
        aws_cmd delete-route-table --route-table-id "${route_table_id}"
    done
}


delete_security_group()
{
    for security_group_id in $(get_security_group); do
        echo "Delete Security Group:      ${security_group_id}"
        aws_cmd delete-security-group --group-id "${security_group_id}"
    done
}


delete_subnet()
{
    for subnet_id in $(get_subnet); do
        echo "Delete Subnet:              ${subnet_id}"
        aws_cmd delete-subnet --subnet-id "${subnet_id}"
    done
}


delete_vpc()
{
    for vpc_id in $(get_vpc); do
        echo "Delete VPC:                 ${vpc_id}"
        aws_cmd delete-vpc --vpc-id "${vpc_id}"
    done
}


get_image()
{
    check_echo "$(aws_cmd describe-images \
        --filters \
            "$(aws_filter owner-id "${AWS_ACCOUNT_ID}")" \
            "$(aws_filter tag:KuberDockClusterRole "${1}")" \
            "$(aws_filter_version)" \
        --query 'Images[].ImageId')"
}


get_image_snapshot()
{
    root_device=$(aws_cmd describe-images \
        --image-ids "${1}" \
        --query 'Images[].RootDeviceName')
    check_echo "$(aws_cmd describe-images \
        --image-ids "${1}" \
        --query 'Images[].BlockDeviceMappings[?DeviceName==`'"${root_device}"'`].Ebs[].SnapshotId')"
}


get_instance()
{
    check_echo "$(aws_cmd describe-instances \
        --filters \
            "$(aws_filter tag:KuberDockClusterRole "${1}")" \
            "$(aws_filter_version)" \
        --query 'Reservations[].Instances[].InstanceId')"
}


get_live_instance()
{
    aws_cmd describe-instances \
        --filters \
            "$(aws_filter instance-state-name pending,rebooting,running,stopped,stopping)" \
            "$(aws_filter tag:KuberDockClusterRole "${1}")" \
            "$(aws_filter_version)" \
        --query 'Reservations[].Instances[].InstanceId'
}


get_internet_gateway()
{
    check_echo "$(aws_cmd describe-internet-gateways \
        --filters "$(aws_filter_version)" \
        --query 'InternetGateways[].InternetGatewayId')"
}


get_route_table()
{
    check_echo "$(aws_cmd describe-route-tables \
        --filters "$(aws_filter_version)" \
        --query 'RouteTables[].RouteTableId')"
}


get_public_ip()
{
    aws_cmd describe-instances \
        --instance-ids "${1}" \
        --query 'Reservations[].Instances[].PublicIpAddress'
}


get_security_group()
{
    check_echo "$(aws_cmd describe-security-groups \
        --filters "$(aws_filter_version)" \
       --query 'SecurityGroups[].GroupId')"
}


get_subnet()
{
    check_echo "$(aws_cmd describe-subnets \
        --filters "$(aws_filter_version)" \
        --query 'Subnets[].SubnetId')"
}


get_vpc()
{
    check_echo "$(aws_cmd describe-vpcs \
        --filters "$(aws_filter_version)" \
        --query 'Vpcs[].VpcId')"
}


image_is_public()
{
    check "$(aws_cmd describe-images \
        --filters \
            "$(aws_filter is-public true)" \
            "$(aws_filter_version)" \
        --image-ids "${1}" \
        --query 'Images[].ImageId')"
}


run_instance()
{
    local block_device_mappings
    local instance_id
    local root_device

    root_device=$(aws_cmd describe-images \
        --image-ids "${AMI_BASE_IMAGE}" \
        --query 'Images[].RootDeviceName')
    block_device_mappings='[{"DeviceName":"'${root_device}'","Ebs":{"DeleteOnTermination":true}}]'
    instance_id=$(aws_cmd run-instances \
        --image-id "${AMI_BASE_IMAGE}" \
        --instance-type "${AMI_INSTANCE_TYPE}" \
        --subnet-id "${2}" \
        --key-name "${AWS_SSH_KEY_NAME}" \
        --security-group-ids "${3}" \
        --associate-public-ip-address \
        --block-device-mappings "${block_device_mappings}" \
        --query 'Instances[].InstanceId')
    create_tags "${instance_id}" "$(ami_name "${1}")"
    create_role_tag "${instance_id}" "${1}"

    echo "${instance_id}"
}


tag_snapshot()
{
    local snapshot_id

    aws_cmd wait image-available --image-ids "${2}"
    snapshot_id=$(get_image_snapshot "${2}")
    create_tags "${snapshot_id}" "$(ami_name "${1}")"
    create_role_tag "${snapshot_id}" "${1}"

    echo "${snapshot_id}"
}


terminate_instance()
{
    local instance_id

    instance_id=$(get_live_instance "${1}")
    if check "${instance_id}"; then
        echo "Terminate Instance:         ${instance_id}"
        aws_cmd terminate-instances --instance-ids "${instance_id}" >> /dev/null
        aws_cmd delete-tags --resources "${instance_id}"
        if check "${2:-}"; then
            aws_cmd wait instance-terminated --instance-ids "${instance_id}"
        fi
    fi
}


wait_accessible()
{
    for _ in $(seq 40); do
        ssh_wrapper "${1}" -o BatchMode=yes -o ConnectTimeout=1 true >> /dev/null && break
        sleep 15
    done
}


wait_image()
{
    for _ in $(seq 40); do
        get_image "${1}" >> /dev/null && break
        sleep 15
    done
}


wait_internet_gateway()
{
    for _ in $(seq 40); do
        check "$(aws_cmd describe-internet-gateways \
            --internet-gateway-ids "${@}" 2> /dev/null)" && break
        sleep 15
    done
}


wait_route_table()
{
    for _ in $(seq 40); do
        check "$(aws_cmd describe-route-tables \
            --route-table-ids "${@}" 2> /dev/null)" && break
        sleep 15
    done
}


wait_security_group()
{
    for _ in $(seq 40); do
        check "$(aws_cmd describe-security-groups \
            --group-ids "${@}" 2> /dev/null)" && break
        sleep 15
    done
}


ami_cleanup()
{
    echo "* Cleanup *"

    delete_image node
    terminate_instance node wait
    delete_security_group
    delete_subnet
    delete_internet_gateway
    delete_route_table
    delete_vpc
}


ami_deploy_node_copy_files()
{
    ssh_wrapper "${1}" rm -fr "${KUBERDOCK_DIR}"
    ssh_wrapper "${1}" mkdir -p "${KUBERDOCK_DIR}"/node_storage_manage

    pushd "${KUBE_ROOT}"/.. >> /dev/null

    scp_wrapper "${1}" "${KUBERDOCK_DIR}" \
        backup_node.py \
        backup_node_merge.py \
        fslimit.py \
        kubelet_args.py \
        node_install.sh \
        node_install_ami.sh \
        node_install_common.sh \
        node_prepare_ami.sh \
        pd.sh \
        node_scripts/kd-docker-exec.sh \
        node_scripts/kd-ssh-gc \
        node_scripts/kd-ssh-user.sh \
        node_scripts/kd-ssh-user-update.sh

    scp_wrapper "${1}" "${KUBERDOCK_DIR}"/node_storage_manage \
        node_storage_manage/__init__.py \
        node_storage_manage/aws.py \
        node_storage_manage/common.py \
        node_storage_manage/manage.py \
        node_storage_manage/node_lvm_manage.py \
        node_storage_manage/node_zfs_manage.py

    popd >> /dev/null

    ssh_wrapper "${1}" -t sudo mv -f "${KUBERDOCK_DIR}"/backup_node.py /usr/bin/kd-backup-node
    ssh_wrapper "${1}" -t sudo mv -f "${KUBERDOCK_DIR}"/backup_node_merge.py /usr/bin/kd-backup-node-merge
    ssh_wrapper "${1}" -t sudo mv -f "${KUBERDOCK_DIR}"/* /
    ssh_wrapper "${1}" rm -fr "${KUBERDOCK_DIR}"
}


ami_deploy_node_prepare_ami()
{
    node_k8s=$(k8s_node_version)
    ssh_wrapper "${1}" -t "cd / && sudo AMI=True AWS=True NODE_KUBERNETES=${node_k8s} WITH_TESTING=${WITH_TESTING} ZFS=yes bash node_install.sh"
    ssh_wrapper "${1}" -t "cd / && sudo bash node_prepare_ami.sh"
}


ami_deploy_node()
{
    echo "* Deploy Node *"

    local node_instance_id
    local node_public_ip

    node_instance_id=$(get_instance node)
    aws_cmd wait instance-running --instance-ids "${node_instance_id}"

    node_public_ip=$(get_public_ip "${node_instance_id}")
    wait_accessible "${node_public_ip}"

    ami_deploy_node_copy_files "${node_public_ip}"
    ami_deploy_node_prepare_ami "${node_public_ip}"
}


ami_help()
{
    print_help "\
    bash ${BASH_SOURCE} [-h|--help] [-i|--info] [-l|--list] [-f|--force-version] [-r|--regions REGIONS] [-t|--with-testing] [-c|--cleanup] [--release] [--skip-setup] [--skip-deploy] [--skip-ami] [--skip-cleanup] [--use-ami AMI_ID]
    : -h|--help             : print this help
    : -i|--info             : print some info
    : -l|--list             : list available AMIs
    : -f|--force-version    : force AMI version
    : -r|--regions REGIONS  : comma-separated list of regions to use with
    :                       :   -l|--list or --release
    :                       :   default is '-' -- current region configured
    :                       :   to operate in
    : -t|--with-testing     : deploy with kube-testing repo
    : -c|--cleanup          : do cleanup
    : --release             : make release AMI
    : --skip-setup          : skip setup
    : --skip-deploy         : skip deploy
    : --skip-ami            : skip AMI creation
    : --skip-cleanup        : skip cleanup (skipped by default if --release
    :                       :   is not specified)
    : --use-ami AMI_ID      : use specified AMI to run instance
    "
}


ami_image()
{
    echo "* Create AMI *"

    delete_image "${1}"

    local image_id
    local instance_id
    local snapshot_id

    instance_id=$(get_instance "${1}")
    if check "${instance_id}"; then
        aws_cmd wait instance-running --instance-ids "${instance_id}"
        image_id=$(get_image "${1}" || create_image "${1}")
        echo "AMI:                        ${image_id}"
        snapshot_id=$(tag_snapshot "${1}" "${image_id}")
        echo "Snapshot:                   ${snapshot_id}"
    fi
}


ami_info() {
    local image_id
    local internet_gateway_id
    local node_instance_id
    local node_public_ip
    local route_table_id
    local security_group_id
    local snapshot_id
    local subnet_id
    local vpc_id

    echo "AMI Version:                $(ami_version)"
    echo "AWS Region:                 ${AWS_DEFAULT_REGION}"
    echo "AWS Availability Zone:      ${AWS_AVAILABILITY_ZONE}"
    echo "Base AMI:                   ${AMI_BASE_IMAGE}"
    vpc_id=$(get_vpc) && \
        echo "VPC:                        ${vpc_id}"
    subnet_id=$(get_subnet) && \
        echo "Subnet:                     ${subnet_id}"
    internet_gateway_id=$(get_internet_gateway) && \
        echo "Internet Gateway:           ${internet_gateway_id}"
    route_table_id=$(get_route_table) && \
        echo "Route Table:                ${route_table_id}"
    security_group_id=$(get_security_group) && \
        echo "Security Group:             ${security_group_id}"
    node_instance_id=$(get_instance node) && \
        echo "Node Instance:              ${node_instance_id}"
    if check "${node_instance_id}"; then
        node_public_ip=$(get_public_ip "${node_instance_id}") && \
            echo "Node Public IP:             ${node_public_ip}"
    fi
    image_id=$(get_image node) && \
        echo "Node AMI:                   ${image_id}"
    if check "${image_id}"; then
        snapshot_id=$(get_image_snapshot "${image_id}") && \
            echo "Node Snapshot:              ${snapshot_id}"
    fi
}


ami_list()
{
    for region in $(ami_regions); do
        echo "${region}:"
        check_echo "$(AWS_DEFAULT_REGION=${region} aws_cmd describe-images \
            --filters \
                "$(aws_filter owner-id "${AWS_ACCOUNT_ID}")" \
                "$(aws_filter tag-key KuberDockAmiVersion)" \
            --query 'Images[].[Name,ImageId,BlockDeviceMappings[0].Ebs.SnapshotId,Public]')" \
            || echo "- no AMIs -"
    done
}


ami_release()
{
    echo "* Release *"

    local node_image_id
    local node_snapshot_id

    wait_image node

    for region in $(ami_regions); do
        echo "${region}:"
        node_image_id=$(copy_image node "${region}")
        echo "Node AMI:                   ${node_image_id}"
        node_snapshot_id=$(AWS_DEFAULT_REGION=${region} tag_snapshot node "${node_image_id}")
        echo "Node Snapshot:              ${node_snapshot_id}"
        AWS_DEFAULT_REGION=${region} aws_cmd modify-image-attribute \
            --image-id "${node_image_id}" \
            --launch-permission '{"Add":[{"Group":"all"}]}'
    done
}


ami_setup()
{
    echo "* Setup *"

    local internet_gateway_id
    local node_instance_id
    local node_public_ip
    local route_table_id
    local security_group_id
    local subnet_id
    local vpc_id

    terminate_instance node

    ssh-key-setup >> /dev/null

    vpc_id=$(get_vpc || create_vpc)
    echo "VPC:                        ${vpc_id}"

    subnet_id=$(get_subnet || create_subnet "${vpc_id}")
    echo "Subnet:                     ${subnet_id}"

    internet_gateway_id=$(get_internet_gateway || create_internet_gateway "${vpc_id}")
    echo "Internet Gateway:           ${internet_gateway_id}"

    route_table_id=$(get_route_table || create_route_table "${vpc_id}" "${subnet_id}" "${internet_gateway_id}")
    echo "Route Table:                ${route_table_id}"

    security_group_id=$(get_security_group || create_security_group "${vpc_id}")
    echo "Security Group:             ${security_group_id}"

    node_instance_id=$(run_instance node "${subnet_id}" "${security_group_id}")
    echo "Node Instance:              ${node_instance_id}"

    node_public_ip=$(get_public_ip "${node_instance_id}")
    echo "Node Public IP:             ${node_public_ip}"
}


while [ $# -gt 0 ]; do
    key=${1}
    case ${key} in
        -c|--cleanup)
            DO_CLEANUP=yes
            DO_DEPLOY=
            DO_IMAGE=
            DO_SETUP=
            ;;
        -f|--force-version)
            FORCED_VERSION=${2}
            shift
            ;;
        -h|--help)
            DO_HELP=yes
            ;;
        -i|--info)
            DO_INFO=yes
            ;;
        -l|--list)
            DO_LIST=yes
            ;;
        -r|--regions)
            REGIONS=${2}
            shift
            ;;
        -t|--with-testing)
            WITH_TESTING=yes
        ;;
        --release)
            check "${SKIP_CLEANUP}" || DO_CLEANUP=yes
            DO_RELEASE=yes
            WITH_TESTING=${WITH_TESTING:-}
        ;;
        --skip-cleanup)
            DO_CLEANUP=
            SKIP_CLEANUP=yes
        ;;
        --skip-deploy)
            DO_DEPLOY=
        ;;
        --skip-ami)
            DO_IMAGE=
        ;;
        --skip-setup)
            DO_SETUP=
        ;;
        --use-ami)
            AMI_BASE_IMAGE=${2}
            shift
            ;;
        *)
            ami_help
            exit 1
        ;;
    esac
    shift
done


do_release && ami_version >> /dev/null

do_help && { ami_help; exit; }
do_info && { ami_info; exit; }
do_list && { ami_list; exit; }
do_setup && ami_setup
do_deploy && ami_deploy_node
do_image && ami_image node
do_release && ami_release
do_cleanup && ami_cleanup
