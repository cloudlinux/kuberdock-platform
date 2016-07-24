#!/usr/bin/env bash
yum install -y gcc
yum install -y epel-release
yum install -y libpqxx-devel
yum install -y python-devel
yum install -y gmp-devel
curl "https://bootstrap.pypa.io/get-pip.py" -o "get-pip.py"
python get-pip.py
pip install --upgrade pip
pip install virtualenv

#virtualenv kuberdock_env
#source kuberdock_env/bin/activate
#pip install -U setuptools
#pip install funcsigs
#pip install pyyaml
#pip install python-dateutil
#pip install nose -I
#pip install -r requirements.txt
#pip install -r requirements-dev.txt

sudo -u postgres psql -c "CREATE DATABASE testkuberdock OWNER kuberdock ENCODING 'UTF8'"

