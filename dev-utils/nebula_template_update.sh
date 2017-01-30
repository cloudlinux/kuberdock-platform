#!/usr/bin/env bash
#
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.
#
set -e

# This is a docker-based version of nebula_template_update.py

IMG=lobur/nebula_template_update:v1

if [ ! -d "dev-utils" ]
then
    echo "Must be run from AppCloud dir, like:"
    echo "./dev-utils/nebula_template_update.sh <id>"
fi

pass_env+="
KD_ONE_URL
KD_ONE_USERNAME
KD_ONE_PASSWORD
"

py_get_env_args="import sys, os;
print '\n'.join(['%s=%s' % (k,os.environ.get(k)) for k in sys.argv[1:] if os.environ.get(k)])"
env_cluster_settings=$(python -c "$py_get_env_args" $pass_env)

SSH_KEY=${KD_ONE_PRIVATE_KEY:-"$HOME/.ssh/id_rsa"}
vol_ssh_key="-v $SSH_KEY:/root/id_rsa"
env_ssh_key="KD_ONE_PRIVATE_KEY=/root/id_rsa"

docker_env=dev-utils/.docker.nebula_template_update.env
echo "$env_cluster_settings" > $docker_env
echo "$env_ssh_key" >> $docker_env

docker run --rm \
    $vol_ssh_key \
    -v $PWD/dev-utils/nebula_template_update.py:/nebula_template_update.py:ro \
    --env-file $docker_env \
    $IMG python /nebula_template_update.py $@
