
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
