#!/usr/bin/env bash

source "$(dirname "${BASH_SOURCE}")/node_install_common.sh"

set_timezone
configure_ntpd
configure_rsyslog
configure_cni
configure_kubelet
kuberdock_json

for service in ntpd rsyslog kubelet kube-proxy
do
    systemctl restart ${service}
done

start_calico_node

rm -f /node_install_ami.sh
rm -f /node_install_common.sh
