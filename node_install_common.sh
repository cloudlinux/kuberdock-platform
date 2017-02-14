#!/usr/bin/env bash
# ========================= DEFINED VARS ===============================
export AWS=${AWS}
export KUBERNETES_CONF_DIR='/etc/kubernetes'
export EXIT_MESSAGE="Installation error."
export KUBE_REPO='/etc/yum.repos.d/kube-cloudlinux.repo'
export KUBE_TEST_REPO='/etc/yum.repos.d/kube-cloudlinux-testing.repo'
export PLUGIN_DIR_BASE='/usr/libexec/kubernetes'
export KD_WATCHER_SERVICE='/etc/systemd/system/kuberdock-watcher.service'
export KD_KERNEL_VARS='/etc/sysctl.d/75-kuberdock.conf'
export KD_RSYSLOG_CONF='/etc/rsyslog.d/kuberdock.conf'
export KD_ELASTIC_LOGS='/var/lib/elasticsearch'
export FSTAB_BACKUP="/var/lib/kuberdock/backups/fstab.pre-swapoff"
export CEPH_VERSION=hammer
export CEPH_BASE='/etc/yum.repos.d/ceph-base'
export CEPH_REPO='/etc/yum.repos.d/ceph.repo'

export KD_SSH_GC_PATH="/var/lib/kuberdock/scripts/kd-ssh-gc"
export KD_SSH_GC_LOCK="/var/run/kuberdock-ssh-gc.lock"
export KD_SSH_GC_CMD="flock -n ${KD_SSH_GC_LOCK} -c '${KD_SSH_GC_PATH}; rm ${KD_SSH_GC_LOCK}'"
export KD_SSH_GC_CRON="@hourly  ${KD_SSH_GC_CMD} > /dev/null 2>&1"

export ZFS_MODULES_LOAD_CONF="/etc/modules-load.d/kuberdock-zfs.conf"
export ZFS_POOLS_LOAD_CONF="/etc/modprobe.d/kuberdock-zfs.conf"

export NODE_STORAGE_MANAGE_DIR=node_storage_manage
# ======================= // DEFINED VARS ===============================


check_status()
{
    local temp=$?
    if [ "${temp}" -ne 0 ];then
        echo "${EXIT_MESSAGE}"
        exit "${temp}"
    fi
}


configure_ntpd()
{
    local ntp_config="/etc/ntp.conf"

    # Backup ntp.conf before any modifications
    backup_ntp_config="${ntp_config}.kd.backup.$(date --iso-8601=ns --utc)"
    echo "Save current ${ntp_config} to ${backup_ntp_config}"
    cp "${ntp_config}" "${backup_ntp_config}"

    sed -i "/^server /d; /^tinker /d" "${ntp_config}"
    # NTP on master server should work at least a few minutes before ntp
    # clients start trusting him. Thus we postpone the sync with it
    echo "server ${MASTER_IP} iburst minpoll 3 maxpoll 4" >> "${ntp_config}"
    echo "tinker panic 0" >> "${ntp_config}"
}


kuberdock_json()
{
if [ "${FIXED_IP_POOLS}" = True ]; then
    fixed_ippools="yes"
else
    fixed_ippools="no"
fi
cat << EOF > "/var/lib/kuberdock/kuberdock.json"
{"fixed_ip_pools": "${fixed_ippools}",
"master": "${MASTER_IP}",
"node": "${NODENAME}",
"network_interface": "${PUBLIC_INTERFACE}",
"token": "${TOKEN}"}
EOF
}


configure_kubelet()
{
echo "Configuring kubernetes..."
sed -i "/^KUBE_MASTER/ {s|http://127.0.0.1:8080|https://${MASTER_IP}:6443|}" "${KUBERNETES_CONF_DIR}"/config
sed -i '/^KUBELET_HOSTNAME/s/^/#/' "${KUBERNETES_CONF_DIR}"/kubelet

# Kubelet's 10255 port (built-in cadvisor) should be accessible from master,
# because heapster.service use it to gather data for our "usage statistics"
# feature. Master-only access is ensured by our cluster-wide firewall
sed -i "/^KUBELET_ADDRESS/ {s|127.0.0.1|0.0.0.0|}" "${KUBERNETES_CONF_DIR}"/kubelet
check_status

sed -i "/^KUBELET_API_SERVER/ {s|http://127.0.0.1:8080|https://${MASTER_IP}:6443|}" "${KUBERNETES_CONF_DIR}"/kubelet
if [ "${AWS}" = True ];then
    sed -i '/^KUBELET_ARGS/ {s|""|"--cloud-provider=aws --kubeconfig=/etc/kubernetes/configfile --cluster_dns=10.254.0.10 --cluster_domain=kuberdock --register-node=false --network-plugin=kuberdock --maximum-dead-containers=1 --maximum-dead-containers-per-container=1 --minimum-container-ttl-duration=10s --cpu-cfs-quota=true --cpu-multiplier='"${CPU_MULTIPLIER}"' --memory-multiplier='"${MEMORY_MULTIPLIER}"' --node-ip='"${NODE_IP}"'"|}' "${KUBERNETES_CONF_DIR}"/kubelet
else
    sed -i '/^KUBELET_ARGS/ {s|""|"--kubeconfig=/etc/kubernetes/configfile --cluster_dns=10.254.0.10 --cluster_domain=kuberdock --register-node=false --network-plugin=kuberdock --maximum-dead-containers=1 --maximum-dead-containers-per-container=1 --minimum-container-ttl-duration=10s --cpu-cfs-quota=true --cpu-multiplier='"${CPU_MULTIPLIER}"' --memory-multiplier='"${MEMORY_MULTIPLIER}"' --node-ip='"${NODE_IP}"'"|}' "${KUBERNETES_CONF_DIR}"/kubelet
fi
sed -i '/^KUBE_PROXY_ARGS/ {s|""|"--kubeconfig=/etc/kubernetes/configfile --proxy-mode iptables"|}' "$KUBERNETES_CONF_DIR"/proxy
check_status
}


configure_cni()
{
{
echo
echo "# Calico etcd authority"
echo ETCD_AUTHORITY="${MASTER_IP}:2379"
echo ETCD_SCHEME="https"
echo ETCD_CA_CERT_FILE="/etc/pki/etcd/ca.crt"
echo ETCD_CERT_FILE="/etc/pki/etcd/etcd-client.crt"
echo ETCD_KEY_FILE="/etc/pki/etcd/etcd-client.key"
} >> "${KUBERNETES_CONF_DIR}"/config

K8S_TOKEN=$(grep token /etc/kubernetes/configfile | grep -oP '[a-zA-Z0-9]+$')

mkdir -p /etc/cni/net.d
cat > /etc/cni/net.d/10-calico.conf << EOF
{
    "name": "calico-k8s-network",
    "type": "calico",
    "log_level": "info",
    "ipam": {
        "type": "calico-ipam"
    },
    "policy": {
        "type": "k8s",
        "k8s_api_root": "https://${MASTER_IP}:6443/api/v1/",
        "k8s_auth_token": "${K8S_TOKEN}"
    }
}
EOF
}


configure_rsyslog()
{
echo "Reconfiguring rsyslog..."
cat > "${KD_RSYSLOG_CONF}" << EOF
\$LocalHostName ${NODENAME}
\$template LongTagForwardFormat,"<%PRI%>%TIMESTAMP:::date-rfc3339% %HOSTNAME% %syslogtag%%msg:::sp-if-no-1st-sp%%msg%"
*.* @${LOG_POD_IP}:5140;LongTagForwardFormat
EOF
}


set_timezone()
{
echo Set time zone to "${TZ}"
timedatectl set-timezone "${TZ}"
}


start_calico_node()
{
echo "Starting Calico node..."
ETCD_AUTHORITY="${MASTER_IP}:2379" ETCD_SCHEME=https ETCD_CA_CERT_FILE=/etc/pki/etcd/ca.crt ETCD_CERT_FILE=/etc/pki/etcd/etcd-client.crt ETCD_KEY_FILE=/etc/pki/etcd/etcd-client.key HOSTNAME="${NODENAME}" /opt/bin/calicoctl node --ip="${NODE_IP}" --node-image="${CALICO_NODE_IMAGE}"
check_status
}
