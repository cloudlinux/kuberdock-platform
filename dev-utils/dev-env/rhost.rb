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

def config_rhost(config, index, nodesCount)

    rhostMemory = Integer(ENV['KD_RHOST_MEMORY'] || '2048')
    rhostCpus = Integer(ENV['KD_RHOST_CPUS'] || '1')
    rhostTemplateId = Integer(ENV['KD_NEBULA_RHOST_TEMPLATE_ID'] || '0')

    if ENV['KD_INSTALL_WHMCS']
        rhostTemplateId = 457
    end

    config.vm.hostname = "rhost#{index}"
    config.vm.network "private_network", ip: "192.168.77.#{10+nodesCount+index}"
    config.vm.provider "virtualbox" do |vb, override|
        vb.memory = rhostMemory
        vb.cpus = rhostCpus
    end
    config.vm.provider :opennebula do |one, override|
        one.cpu = rhostCpus
        one.vcpu = rhostCpus
        one.memory =rhostMemory
        one.title = "rhost#{index}"
        one.template_id = rhostTemplateId
    end
end
