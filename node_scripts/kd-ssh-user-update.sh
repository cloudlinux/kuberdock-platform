#!/usr/bin/env bash
# Called by each api call to .../direct_access

user=$1
pass=$2
id -u "$user"   # check user exists
if [[ $? -ne 0 ]];then
  U_HOME="/var/lib/kuberdock/kd-ssh-users-home/$user"
  # This also prevents copy files from skel to home, because they useless for us
  mkdir -p "$U_HOME"
  useradd -g kddockersshuser -d "$U_HOME" -p "$pass" "$user"
else
  usermod -p "$pass" "$user"
fi
