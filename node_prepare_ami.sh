#!/usr/bin/env bash

for image in \
        gcr.io/google_containers/etcd-amd64:2.2.1 \
        gcr.io/google_containers/exechealthz:1.0 \
        gcr.io/google_containers/skydns:2015-10-13-8c72f8c \
        gcr.io/google_containers/pause:2.0 \
        jetstack/kube-lego:0.1.3 \
        kuberdock/calico-node:0.22.0-kd2 \
        kuberdock/defaultbackend:0.0.1 \
        kuberdock/elasticsearch:2.2 \
        kuberdock/fluentd:1.8 \
        kuberdock/k8s-policy-agent:v0.1.4-kd2 \
        kuberdock/kube2sky:1.2 \
        kuberdock/nginx-ingress-controller:0.2.0 \
        ; do
    docker pull ${image}
done

systemctl disable rsyslog
systemctl stop rsyslog

rm -f /node_install.sh

yum clean packages
