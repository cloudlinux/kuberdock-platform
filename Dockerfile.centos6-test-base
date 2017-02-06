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

FROM centos:6

RUN yum -y install epel-release && \
    yum -y update && \
    yum -y install python-pip && \
    yum clean all
RUN pip install --upgrade pip && pip install virtualenv

# Pre-build test env. Before test run requirements are checked again.
# It is much faster to check/install-missing than full install.
COPY requirements-dev.txt /

RUN cd / && \
    virtualenv venv && \
    source venv/bin/activate && \
    pip install -r requirements-dev.txt && \
    rm -f requirements-dev.txt

# Rebuild & push with (always bump X):
# docker build -t USER/centos6-test-base:vX -f Dockerfile.centos6-test-base --rm=true --no-cache=true --pull .
# docker push USER/centos6-test-base:vX
