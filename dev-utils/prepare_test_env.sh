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

