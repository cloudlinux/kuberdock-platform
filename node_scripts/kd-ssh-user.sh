#!/usr/bin/env bash

# Copyright CloudLinux Zug GmbH 2016, All Rights Reserved
# Author: Igor Seletskiy
# E-Mail: i@cloudinux.com

# We mount statically linked scp & sftp-server into the container
# as hidden volume. Also, this prevents potential quota issues

args="$SSH_ORIGINAL_COMMAND"
# Substituting so we use our statically binding tools on a container

if [ ! -z "$args" ]; then
  args="${args/#\/usr\/libexec\/openssh\/sftp-server//.kdtools/sftp-server}"
  args="${args/#scp//.kdtools/scp}"
fi

if [ -z "$SSH_TTY" ]; then
# we need interactive even if there is no terminal to get input from ssh connection
# this can be anything from echo "HI"|ssh container@server "cat >> 22"
# it is also needed for sftp and scp
# There is problems with that, as it requires user to press extra ENTER
# to get back to shell after things like: ssh container@server ls
# though things like echo |ssh container@server ls work just fine
# also scp container@server:file . blocks/waits after copying. Requires CTRL-^C to exit
# The other direction/sftp works just fine.
# note that the same behavior with ssh root@host docker exec -i container ls
# So the issue seems to be in either docker exec -i, or in pipes/terminals
# Might be related: http://stackoverflow.com/questions/911168/how-to-detect-if-my-shell-script-is-running-through-a-pipe
# See 3rd response
  EXEC_OPT='-i'
else
# if there is TTY, connect to it
  EXEC_OPT='-ti'
fi

# TODO
  # We have some problems with various combinations of "sudo" with/without "exec"
  # and with/without "-i" EXEC_OPT. Some cases started to work, some stops.
  # Some problems solves with "ssh -t"

KD_DOCKER='/var/lib/kuberdock/scripts/kd-docker-exec.sh'
if [ -z "$args" ]; then
  exec sudo "$KD_DOCKER" $EXEC_OPT $USER /bin/bash
else
  exec sudo "$KD_DOCKER" $EXEC_OPT $USER /bin/bash -c "$args"
fi
exit -1