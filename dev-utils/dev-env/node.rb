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

def config_node(config, index)
    nodeMemory = Integer(ENV['KD_NODE_MEMORY'] || '2048')
    nodeCpus = Integer(ENV['KD_NODE_CPUS'] || '1')

    config.vm.hostname = "node#{index}"
    config.vm.network "private_network", ip: "192.168.77.#{10+index}"
    config.vm.provider "virtualbox" do |vb, override|
        vb.memory = nodeMemory
        vb.cpus = nodeCpus
    end
    config.vm.provider :opennebula do |one, override|
        one.cpu = nodeCpus
        one.vcpu = nodeCpus
        one.memory = nodeMemory
        one.title = "node#{index}"
    end
end
