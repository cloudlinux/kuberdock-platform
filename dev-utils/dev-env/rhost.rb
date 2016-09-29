
def config_rhost(config, index)

    rhostMemory = Integer(ENV['KD_RHOST_MEMORY'] || '2048')
    rhostCpus = Integer(ENV['KD_RHOST_CPUS'] || '1')
    rhostTemplateId = Integer(ENV['KD_NEBULA_RHOST_TEMPLATE_ID'] || '0')

    if ENV['KD_INSTALL_WHMCS']
        rhostTemplateId = 457
    end

    config.vm.hostname = "rhost#{index}"
    config.vm.network "private_network", ip: "192.168.77.#{10+index}"
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
