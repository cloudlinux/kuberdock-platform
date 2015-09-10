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

# Prepopulate the name of the Master
mkdir -p /etc/salt/node.d
echo "master: $SALT_MASTER" > /etc/salt/node.d/master.conf

cat <<EOF >/etc/salt/node.d/grains.conf
grains:
  roles:
    - kubernetes-master
  cloud: aws
  cbr-cidr: "${MASTER_IP_RANGE}"
EOF

if [[ -n "${DOCKER_OPTS}" ]]; then
  cat <<EOF >>/etc/salt/node.d/grains.conf
  docker_opts: '$(echo "$DOCKER_OPTS" | sed -e "s/'/''/g")'
EOF
fi

if [[ -n "${DOCKER_ROOT}" ]]; then
  cat <<EOF >>/etc/salt/node.d/grains.conf
  docker_root: '$(echo "$DOCKER_ROOT" | sed -e "s/'/''/g")'
EOF
fi

# Auto accept all keys from nodes that try to join
mkdir -p /etc/salt/master.d
cat <<EOF >/etc/salt/master.d/auto-accept.conf
auto_accept: True
EOF

cat <<EOF >/etc/salt/master.d/reactor.conf
# React to new nodes starting by running highstate on them.
reactor:
  - 'salt/node/*/start':
    - /srv/reactor/highstate-new.sls
EOF

install-salt master

service salt-master start
service salt-node start
