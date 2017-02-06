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
    yum -y install wget make gcc rsync wget git python-netaddr python-passlib && \
    wget http://cbs.centos.org/kojifiles/packages/ansible/2.1.0.0/1.el7/noarch/ansible-2.1.0.0-1.el7.noarch.rpm && \
    yum -y localinstall ansible-2.1.0.0-1.el7.noarch.rpm && rm -f ansible-2.1.0.0-1.el7.noarch.rpm && \
    wget https://releases.hashicorp.com/vagrant/1.8.5/vagrant_1.8.5_x86_64.rpm && \
    yum -y localinstall vagrant_1.8.5_x86_64.rpm && rm -f vagrant_1.8.5_x86_64.rpm && \
    vagrant plugin install vagrant-gatling-rsync && \
    vagrant plugin install vagrant-rsync-back && \
    vagrant plugin install opennebula-provider --plugin-version 1.1.2 && \
    yum clean all

# Remove annoying "duplicated key at line 132 ignored: :nic" warning
RUN sed -i '131d' /root/.vagrant.d/gems/gems/fog-1.38.0/lib/fog/opennebula/requests/compute/template_pool.rb

# Workaround for https://github.com/mitchellh/vagrant/issues/6721
RUN cd /opt/vagrant/embedded/ && \
    bin/gem install ffi -v 1.9.14 && \
    yes | cp {lib/ruby/gems/2.2.0,gems}/extensions/x86_64-linux/2.2.0/ffi-1.9.14/ffi_c.so


# Rebuild & push with:
# docker build -t lobur/dev-env:vX -f dev-utils/Dockerfile.dev-env --rm=true --no-cache=true --pull .
# docker push lobur/dev-env:vX

# Always bump X, including vagrant.sh file, this is needed to make sure
# the new image gets pulled on Jenkins.
# If you are not lobur use your own hub.docker.com account
