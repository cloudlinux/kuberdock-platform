def config_master(config, nodesCount, rhostsCount)

    masterMemory = Integer(ENV['KD_MASTER_MEMORY'] || '2048')
    masterCpus = Integer(ENV['KD_MASTER_CPUS'] || '1')

    config.vm.hostname = "master"
    config.vm.network "private_network", ip: "192.168.77.10"
    config.vm.network "forwarded_port", guest: 5000, host: 5000
    config.vm.provider "virtualbox" do |vb, override|
        vb.memory = masterMemory
        vb.cpus = masterCpus
    end
    config.vm.provider :opennebula do |one, override|
        one.cpu = masterCpus
        one.vcpu = masterCpus
        one.memory = masterMemory
        one.title = 'master'
    end
    config.vm.provision "ansible" do |ansible|
        config_ansible(ansible, nodesCount, rhostsCount)
    end
end

def config_ansible(ansible, nodesCount, rhostsCount)

    ansible.playbook = "ansible/main.yml"

    if ENV['KD_DEPLOY_DEBUG']
        ansible.verbose='vvv'
        commitHash = `git rev-parse HEAD`
        ENV['ANSIBLE_LOG_PATH']="./ansible_deploy_"+commitHash[0..8]+".log"
    end
    if ENV['KD_DEPLOY_SKIP']
        ansible.skip_tags=ENV['KD_DEPLOY_SKIP']
    end
    if ENV['KD_RETRY_FROM_LAST_FAIL']
      ansible.limit = '@ansible/main.retry'
    else
      ansible.limit = 'all'
    end

    defaultBuildDir =File.expand_path('../../../builds', __FILE__)
    buildDir = ENV['KD_BUILD_DIR'] || defaultBuildDir

    ansible.groups = {
        "master" => ["kd_master"],
        "node" => ["kd_node[1:#{nodesCount}]"],
        "rhost" => ["kd_rhost[1:#{rhostsCount}]"],
    }

    extra_vars = {
        "add_ssh_pub_keys" => ENV['KD_ADD_SHARED_PUB_KEYS'],
        "install_type" => ENV['KD_INSTALL_TYPE'],
        "host_builds_path" => buildDir,
        "dotfiles" => ENV['KD_DOT_FILES'],
        "hook" => ENV['KD_MASTER_HOOK'],
        "license_path" => ENV['KD_LICENSE'],
        "no_wsgi" => ENV['KD_NO_WSGI'],
        "git_ref" => ENV['KD_GIT_REF'],
        "testing_repo" => true, #ENV['KD_TESTING_REPO'],
        "public_ips" => ENV['KD_ONE_PUB_IPS'],
        "fixed_ip_pools" => ENV['KD_FIXED_IP_POOLS'],
        "pod_ip_network" => ENV['KD_POD_IP_NETWORK'],

        "use_ceph" => ENV['KD_CEPH'],
        "ceph_user" => ENV['KD_CEPH_USER'],
        "ceph_config" => ENV['KD_CEPH_CONFIG'],
        "ceph_user_keyring" => ENV['KD_CEPH_USER_KEYRING'],
        "pd_namespace" => ENV['KD_PD_NAMESPACE'],

        "node_types" => ENV['KD_NODE_TYPES'],
        "timezone" => ENV['KD_TIMEZONE'],

        "install_plesk" => ENV['KD_INSTALL_PLESK'],
        "plesk_license" => ENV['KD_PLESK_LICENSE'],

        "use_zfs" => ENV['KD_USE_ZFS'],

        "install_whmcs" => ENV['KD_INSTALL_WHMCS'],
        "whmcs_license" => ENV['KD_WHMCS_LICENSE'],
        "whmcs_domain_name" => ENV['KD_WHMCS_DOMAIN_NAME'],
        "add_timestamps" => ENV['KD_ADD_TIMESTAMPS'],
    }

    # Clean undefined vars
    extra_vars.each do |key, value|
        if value == nil
            extra_vars.delete(key)
        end
    end

    ansible.extra_vars = extra_vars
end
