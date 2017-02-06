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

FROM centos:7

RUN yum -y install epel-release && \
    yum -y update && \
    yum -y install openssl-devel libffi-devel python-pip python-devel postgresql-contrib postgresql-devel gcc nmap && \
    yum clean all
RUN pip install --upgrade pip && pip install virtualenv

# Pre-build test env. Before test run requirements are checked again.
# It is much faster to check/install-missing than full install.
COPY requirements.txt requirements-dev.txt /

# FIXME http://stackoverflow.com/questions/38836293/make-python-libraries-installed-with-requirements-txt-immediately-available
RUN cd / && \
    virtualenv venv && \
    source venv/bin/activate && \
    pip install requests==2.4.3 && \
    pip install -r requirements.txt -r requirements-dev.txt && \
    rm -f requirements.txt requirements-dev.txt

# Rebuild & push with (always bump X):
# docker build -t lobur/centos7-test-base:vX -f Dockerfile.centos7-test-base --rm=true --no-cache=true --pull .
# docker push lobur/centos7-test-base:vX

# Always bump X, including Dockerfile.test, this is
# needed to make sure the new image gets pulled on Jenkins
# If you are not lobur use your own hub.docker.com account
