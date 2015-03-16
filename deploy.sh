#!/bin/bash

KUBERDOCK_DIR=/var/opt/kuberdock
KUBE_CONF_DIR=/etc/kubernetes

#0. Import some keys
rpm --import http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
rpm --import https://dl.fedoraproject.org/pub/epel/RPM-GPG-KEY-EPEL-7
yum -y install epel-release

#1. Add kubernetes repo
cat > /etc/yum.repos.d/kube-cloudlinux.repo << EOF
[kube]
name=kube
baseurl=http://repo.cloudlinux.com/kubernetes/x86_64/
enabled=1
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF

#2. Install postgresql
yum -y install postgresql-server postgresql
postgresql-setup initdb
systemctl restart postgresql
python $KUBERDOCK_DIR/postgresql_setup.py
systemctl restart postgresql

#3. Install Redis and Influxdb
yum -y install redis influxdb python-redis python-influxdb

#4. Install kubernetes
yum -y install kubernetes
sed -i "/^KUBE_API_ADDRESS/ {s/127.0.0.1/0.0.0.0/}" $KUBE_CONF_DIR/apiserver

#5. Install packages for app
yum -y install python-flask python-sqlalchemy python-flask-sqlalchemy python-requests python python-flask-influxdb python-celery python-cerberus python-flask-login python-sse python-simple-rbac python-paramiko python-gevent python-blinker python-flask-assets python-unidecode python-ipaddress python-flask-mail python-psycopg2

#6. Create and populate DB
cd $KUBERDOCK_DIR
python createdb.py

systemctl enable redis
systemctl start redis

systemctl enable influxdb > /dev/null 2>&1
systemctl start influxdb

systemctl enable etcd
systemctl start etcd

for i in kube-apiserver kube-controller-manager kube-scheduler;do systemctl restart $i;done