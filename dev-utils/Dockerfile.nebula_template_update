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
    yum -y install python-pip git gcc python-devel openssl-devel && \
    yum clean all

COPY ./requirements-integration.txt ./

RUN pip install --upgrade pip && \
    pip install -r requirements-integration.txt

# Rebuild & push with:
# docker build -t lobur/nebula_template_update:vX -f dev-utils/Dockerfile.nebula_template_update --rm=true --no-cache=true --pull .
# docker push lobur/rpm-build-base:vX

# Always bump X, this is
# needed to make sure the new image gets pulled on Jenkins
# If you are not lobur use your own hub.docker.com account
