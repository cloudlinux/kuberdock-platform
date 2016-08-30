#!/usr/bin/env bash
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
