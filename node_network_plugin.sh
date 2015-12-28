#!/bin/bash

ACTION=$1

# At this moment this is also kuberdock-pod-uid
NAMESPACE=$2
KUBERNETES_POD_ID=$3
DOCKER_PAUSE_ID=$4

source /etc/kubernetes/kubelet
source /etc/sysconfig/flanneld

if [ "$0" != "-bash" ]
then
  pushd $(dirname $0) > /dev/null
  PLUGIN_DIR=$(pwd -P)
  popd > /dev/null
else
  PLUGIN_DIR="."
fi

API_SERVER=$(cut -d '=' -f 2 <<< $KUBELET_API_SERVER)
TOKEN=$(grep token /etc/kubernetes/configfile | grep -oP '[a-zA-Z0-9]+$')
# TODO must be taken from some node global.env for all settings
IFACE=$(cut -d '=' -f 2 <<< $FLANNEL_OPTIONS)
NODE_IP=$(ip -o ad | grep " $IFACE " | head -1 | awk '{print $4}' | cut -d/ -f1)
DATA_DIR="$PLUGIN_DIR/data/$NAMESPACE"
DATA_INFO="$DATA_DIR/$KUBERNETES_POD_ID"
LOG_FILE="$PLUGIN_DIR/kuberdock.log"
LOG_ENABLED="1"


function rule_reject_pod_local_input {
  iptables -w -$1 KUBERDOCK -t filter -i docker0 -o docker0 -d $2 -m set ! --match-set $3 src -j REJECT
}


function rule_reject_pod_local_output {
  iptables -w -$1 KUBERDOCK -t filter -i docker0 -o docker0 -s $2 -m set ! --match-set $3 dst -j REJECT
}


function rule_reject_pod_output {
  iptables -w -$1 KUBERDOCK -t filter -i docker0 ! -o docker0 -s $2 -m set ! --match-set $3 dst -m conntrack ! --ctstate RELATED,ESTABLISHED -j REJECT
}


function rule_reject_service {
  iptables -w -$1 KUBERDOCK -t nat -s $2 -m set ! --match-set $3 dst -j ACCEPT
}


function get_setname {
  echo "kuberdock_user_$1"
}


# TODO comment all input '$1' params
function add_rules {
  set=$(get_setname $2)
  ipset create $set hash:ip  # workaround for non-existent ip set
  if ! rule_reject_pod_local_input C $1 $set
  then
    rule_reject_pod_local_input A $1 $set
  fi
  if ! rule_reject_pod_local_output C $1 $set
  then
    rule_reject_pod_local_output A $1 $set
  fi
  if ! rule_reject_pod_output C $1 $set
  then
    rule_reject_pod_output A $1 $set
  fi
  if ! rule_reject_service C $1 $set
  then
    rule_reject_service A $1 $set
  fi
}


function del_rules {
  set=$(get_setname $2)
  rule_reject_pod_local_input D $1 $set
  rule_reject_pod_local_output D $1 $set
  rule_reject_pod_output D $1 $set
  rule_reject_service D $1 $set
}


function etcd_ {
  args="${FLANNEL_ETCD}/v2/keys${FLANNEL_ETCD_KEY}users/"
  if [ ! -z "$2" ]
  then
    args+="$2/"
  fi
  if [ ! -z "$3" ]
  then
    args+="$3/"
  fi
  if [ ! -z "$4" ]
  then
    args[1]="-d value=$4"
  fi
  curl -sS --cacert "$ETCD_CAFILE" --cert "$ETCD_CERTFILE" --key "$ETCD_KEYFILE" \
    -X "$1" ${args[@]}
}


function log {
  if [ "$LOG_ENABLED" == "1" ];then
    if [ $(wc -l < "$LOG_FILE") -ge 100 ];then    # limit log to 100 lines
      tail -n 100 "$LOG_FILE" > "$LOG_FILE.tmp"
      mv "$LOG_FILE.tmp" "$LOG_FILE"
    fi
    echo "$(date -uIns) $@" >> "$LOG_FILE"
  fi
}


function get_pod_spec {
  curl -f -sS -k "$API_SERVER/api/v1/namespaces/$NAMESPACE/pods/$KUBERNETES_POD_ID" --header "Authorization: Bearer $TOKEN"
}


function iptables_ {
  action=$1
  shift 1
  if ! iptables -w -C ${@}
    then
      iptables -w ${action} ${@}
    fi
}


function teardown_pod {
    log "Teardown Pod $POD_IP of user $USER_ID; PUBLCI_IP: \"$POD_PUBLIC_IP\""
    del_rules "$POD_IP" "$USER_ID"

    if [ "$POD_PUBLIC_IP" != "" ];then
      /usr/bin/env python2 "$PLUGIN_DIR/kuberdock.py" teardown $POD_PUBLIC_IP $POD_IP $IFACE $NAMESPACE $DATA_INFO-spec
    fi

    etcd_ DELETE "$USER_ID" "$POD_IP"
    rm -rf "$DATA_INFO"
    rm -rf "$DATA_INFO-spec"
    if [ ! $(ls "$DATA_DIR") ];then   # is empty
      rm -rf "$DATA_DIR"
    fi
}


function add_resolve {
  for resolve in $2
  do
    curl -sS --cacert "$ETCD_CAFILE" --cert "$ETCD_CERTFILE" --key "$ETCD_KEYFILE" \
      -X PUT "https://10.254.0.10:2379/v2/keys/skydns/kuberdock/svc/$1/$resolve" \
      -d value="{\"host\":\"127.0.0.1\",\"priority\":10,\"weight\":10,\"ttl\":30,\"targetstrip\":0}"
  done
}


case "$ACTION" in
  "init")
    rm -f "$LOG_FILE"
    iptables -w -N KUBERDOCK -t filter
    iptables -w -N KUBERDOCK -t nat
    iptables -w -N KUBERDOCK-PUBLIC-IP -t nat
    iptables_ -I FORWARD -t filter -j KUBERDOCK
    iptables_ -I PREROUTING -t nat -j KUBERDOCK
    iptables_ -I PREROUTING -t nat -j KUBERDOCK-PUBLIC-IP
    /usr/bin/env python2 "$PLUGIN_DIR/kuberdock.py" init
    iptables_ -I KUBERDOCK -t filter -i docker0 ! -o docker0 -m set ! --match-set kuberdock_cluster dst -j ACCEPT
    iptables_ -I KUBERDOCK -t nat -m set ! --match-set kuberdock_cluster dst -j ACCEPT
    ;;
  "setup")

    # Workaround 1
    # TODO what if api-server is down ?
    POD_SPEC=$(get_pod_spec)
    # Protection from fast start/stop pod; Must be first check
    if [ "$POD_SPEC" == "" ];then
      log "Empty spec case. Skip setup"
      exit
    fi

    # Workaround 2
    if [ -d "$DATA_DIR" ];then  # Protection from absent teardown
      log "Forced teardown"
      OLD_POD="$(ls -1 $DATA_DIR | head -1)"
      source "$DATA_DIR/$OLD_POD"
      teardown_pod
      rm -rf "$DATA_DIR/$OLD_POD"
    fi

    POD_IP=$(docker inspect --format="{{.NetworkSettings.IPAddress}}" "$DOCKER_PAUSE_ID")
    SERVICE_IP=$(iptables -w -L -t nat | grep "$NAMESPACE" | head -1 | awk '{print $5}')
    USER_ID=$(echo "$POD_SPEC" | grep kuberdock-user-uid | awk '{gsub(/,$/,""); print $2}' | tr -d \")
    POD_PUBLIC_IP=$(echo "$POD_SPEC" | grep kuberdock-public-ip | awk '{gsub(/,$/,""); print $2}' | tr -d \")
    RESOLVE=$(echo "$POD_SPEC" | grep kuberdock_resolve | awk '{gsub(/,$/,""); for(i=2; i<=NF; ++i) print $i}' | tr -d \" | xargs echo)

    log "Setup Pod $POD_IP (Service $SERVICE_IP) of user $USER_ID; PUBLIC_IP: \"$POD_PUBLIC_IP\"; resolve: \"$RESOLVE\""

    mkdir -p "$DATA_DIR"
    echo "POD_IP=$POD_IP" > "$DATA_INFO"
    echo "USER_ID=$USER_ID" >> "$DATA_INFO"
    echo "$POD_SPEC" > "$DATA_INFO-spec"

    if [ "$POD_PUBLIC_IP" != "" ];then
      echo "POD_PUBLIC_IP=$POD_PUBLIC_IP" >> "$DATA_INFO"
      /usr/bin/env python2 "$PLUGIN_DIR/kuberdock.py" setup $POD_PUBLIC_IP $POD_IP $IFACE $NAMESPACE $DATA_INFO-spec
    fi

    etcd_ PUT "$USER_ID" "$POD_IP" "{\"node\":\"$NODE_IP\",\"service\":\"$SERVICE_IP\"}"
    add_rules "$POD_IP" "$USER_ID"

    if [ ! -z "$RESOLVE" ]
    then
      add_resolve "$NAMESPACE" "$RESOLVE"
    fi

    # Workaround 3. Recheck that pod still exists.
    # TODO what if api-server is down ?
    POD_SPEC=$(get_pod_spec)
    if [ "$POD_SPEC" == "" ];then
      log "Pod already not exists. Make teardown"
      teardown_pod
      exit
    fi

    ;;
  "teardown")
    if [ -f "$DATA_INFO" ];then
      source "$DATA_INFO"
      teardown_pod
    else
      log "Teardown called for not existed pod. Skip"
    fi
    ;;
esac
