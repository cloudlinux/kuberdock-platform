KuberDock: platform to run and sell dockerized applications
============================

![KuberDock logo](kubedock/frontend/static/img/logo-login.png "KuberDock")

KuberDock - is a platform that allows users to run applications using Docker container images and create SaaS / PaaS based on these applications.

KuberDock hides all complexity of underlying technologies from end-users and admins allowing to focus on creating and using [Predifined applications](https://github.com/cloudlinux/kuberdock_predefined_apps) and/or **any** dockerized app.

------

## Features
- Extremely simple UI/UX for both end-users and admins
- Rich API to run yaml-based declarative [Predifined applications](https://github.com/cloudlinux/kuberdock_predefined_apps)
- Real-time, centralized elasticsearch-based logs for all containers
- Complete network isolation of users from each other
- Continuous resource usage monitoring for Pods and cluster nodes itself
- Easy SSH/SCP/SFTP access into containers
- Complete persistent storage support with few backends: Ceph, LocalStorage, ZFS, ZFS-on-EBS
- Ability to set resource limits per container(CPU, Mem, Persistent storage, Transient storage)
- Ability to expose Pods to Internet with:
    - floating or fixed Public IPs
    - Shared IP (http/https traffic)
    - ELB on AWS
    - cPanel proxy and similar
- Automatic SSL certificates generation with [Let’s Encrypt](https://letsencrypt.org/)
- AWS support
- Simple cluster upgrades with just a one command
- Ability to control overselling parameters for CPU and Memory
- Backups for KuberDock cluster(master and nodes)
- Backups for users' pods, and persistent volumes
- Improved security with SELinux

#### Built-in integrations with:
- WHMCS billing system
- Various control panels like _cPanel_, _Plesk_, _DirectAdmin_
- DNS management systems like _CloudFlare_, _cPanel_, _AWS route 53_


## Under the hood
- [Kubernetes](https://github.com/kubernetes/kubernetes)
- [Docker](https://github.com/docker/docker)
- [Etcd](https://github.com/coreos/etcd)
- [OverlayFS](https://docs.docker.com/engine/userguide/storagedriver/overlayfs-driver/)
- [Heapster](https://github.com/kubernetes/heapster)
- [Influxdb](https://github.com/influxdata/influxdb)
- [Calico](https://github.com/projectcalico/calico)
- [Fluentd](https://github.com/fluent/fluentd/)
- ElasticSearch
- Redis
- PostgreSQL
- Python2, Flask, Gevent, 70+ libs
- WebPack, Backbone, Marionette, npm, yarn, etc.

------

# How the project is run
KuberDock now is a free OSS and have no commercial support from CloudLinux right now.

However, rpm repositories will be hosted by CloudLinux for minimal reasonable time, till the project completely moved to GitHub with all dependencies and CI.


# Deploy production cluster
_Note: You may use this software in production only at your own risk_

To install KuberDock package that is already in Cloudlinux stable repositories you can just follow _"Master installation guide"_ or _"Install KuberDock at Amazon Web Services"_ from [docs folder](docs/kd_doc.md).

To install custom build, you have to use [deploy.sh](deploy.sh) from the **same** commit as your KuberDock package, and run it in the same folder where you put the rpm package. Deploy script will pick up that package instead of any existing in repositories.
Something like this:
```bash
[root@your-kd-master-host] ls
deploy.sh
kuberdock-1.5.2-1.el7.noarch.rpm
[root@your-kd-master-host] bash ./deploy.sh --some-needed-options
```

_Note: This process might be simplified and reworked in future to remove any dependencies from CloudLinux repos and build things in place or download from elsewhere automatically_


# Contributing to KubeDock
If you gonna hack on KuberDock, you should know few things:
1. This is an Awesome Idea! :)
2. We are opened to discussions and PRs. Feel free to open Github issues.
3. You can contact some contributors for help. See [CONTRIBUTORS.md](CONTRIBUTORS.md)


## Deploy cluster for development
KuberDock has scripts that automatically provision KD cluster and doing preliminary configuration.

_Note: Current rpm package repositories is still hosted by CloudLinux, but this support will be eventually discontinued, so appropriate PRs are welcome;)_

Release branches (like `1.5.2`) are intended to be production ready and should recieve only bug fixes.

`Master` branch should be stable enough to use for development and testing purposes but may contain some new features with bugs.

`Development` branch is experimental and could be unstable.

See [versioning policy](docs/versioning.md) also.


#### Requirements:
KuberDock development cluster could be created in VMs with Vagrant either in VirtualBox or OpenNebula.

_Note: If you need to work on more than 1 cluster at time you have to make a separate repo clone because vagrant doesn't support switching clusters in place.
Another way to do this you can destroy your previous cluster (vagrant destroy -f) and create new one._

If you are going to use OpenNebula, make sure you have configured password-less ssh-key in it.

Also, for OpenNebula clusters, it's recommended(but not required) to use our docker-wrapped version of vagrant, because latest Vagrant often breaks backward compatibility in various places. However, this also has own limitations:
- No VBox support. The only cross-platform way to make it is reverse-ssh: http://stackoverflow.com/a/19364263/923620 we did not implement this yet
- vagrant global-status will not show all clusters - obviously: each of vagrants is isolated in own container

In case of docker-wrapped Vagrant:
- docker 1.11 (or later) is running
- export PATH=dev-utils:$PATH

In case of native Vagrant(either for VBox or OpenNebula) you will need:
- Vagrant 1.8.4+
- gatling-rsync-plugin (Installation is required, but usage is optional, only if you not satisfied with vagrant built-in "rsync-auto" performance)
    - _vagrant plugin install vagrant-gatling-rsync_
- rsync --version (2.6.9 or later)
- ansible --version (ansible 2.0.2.0 or later)
- python2-netaddr and python2-passlib (python2 !) for ansible filters
- OpenNebula plugin (Optional, if you will provision into OpenNebula)
    - _vagrant plugin install opennebula-provider --plugin-version 1.1.2_
- VirtualBox (Optional, if you will provision into VirtualBox)
    - _vboxmanage —version (v5.0.18r106667 or later)_


##### Developer Flow (KD_INSTALL_TYPE=dev):
```bash
    git clone https://github.com/cloudlinux/kuberdock-platform
    cd AppCloud
    cp dev-utils/dev-env/kd_cluster_settings.sample ~/my_cluster_settings
    # Edit my_cluster_settings:
    # - Set KD_INSTALL_TYPE=dev.
    # - Set KD_NEBULA_TEMPLATE to one of the predefined for this purposes
    # Customize other settings if needed.
    # Import settings
    source ~/my_cluster_settings
    # Build cluster (run from AppCloud/ dir)
    vagrant up --provider=opennebula && vagrant provision
    # (for VirtualBox it's just "vagrant up")
    # Done
    # Find KD IP in deploy output, access it with creds admin/admin
    # For ssh use:
    vagrant ssh kd_master
    vagrant ssh kd_node1
    ...
    # Done
```

What does it do:
- provisions few VMs in your VirtualBox or OpenNebula
- builds "kuberdock.rpm", "kdctl.rpm", "kcli.rpm" RPMs inside master
- runs deploy.sh
- resets password to "admin"
- runs wsgi app from tmux screen (tmux at to attach). To restart tmux session use `run_wsgi_in_tmux.sh`
- add nodes
- Turns off billing dependency
- Creates test users
- Creates IPPool
- Adds all Predefined Apps from Github to KD cluster
- setups everything needed to run unit tests inside master
- some more dev-specific tune-ups

Continuous code syncing to OpenNebula:
- Way 1: _vagrant rsync-auto_ may be less performant than Way 2, but it works and more stable. Also, it's built-in and no plugins required.
- Way 2: _vagrant gatling-rsync-auto_ This may be slow for interactive development, takes about 6 seconds to sync. Pros: in-place code editing; Cons: async.
- Way 3: Use _sshfs_ Pros: Blocking, suitable for interactive coding; Cons: not in-place. You edit code in a mount point, not the initial repo.

### Unittests
Best way is to run them in docker:
```bash
    # with tox (p.s. make sure it's installed)
    (venv)Appcloud tox -eunit
    # or directly:
    (venv)Appcloud bash ./_run_tests_in_docker.sh
```

### Front-end stuff
see this [README.md](./kubedock/frontend/static/README.md)

### Integration tests
Integration tests have been strongly integrated with CloudLinux infrastructure, so after moving project to Github and quick code changes they, of course, will not work out of the box anymore. This is a "number one TODO" to rework them. However, it's not easy and requires big infrastructure(OpenNebula cloud, Ceph cluster, some AWS if needed, etc.) and/or rework.

Tests are developed to use OpenNebula as a VM provider, but some tests(and it's a good news) could be run locally with a VirtualBox-based cluster.

From a high-level perspective they do the following things:
1. Create one or more pipelines (each pipeline is a KuberDock cluster consisting of few VMs)
2. Deploy KuberDock in each pipeline with some configuration (e.g. Ceph as persistent storage, or LocalStorage etc.)
3. Provision test users, Pods etc.
4. Run tests
5. Teardown the cluster (or leave it as is in case of failed tests)

Typical workflow on local cluster will look like:
```bash
(venv)AppCloud source ./your-kd_cluster_settings
(venv)AppCloud source ./your-kuberdock-ci-env
# run all tests and pipelines or comma-separated list of them
# if BUILD_CLUSTER=0 then current cluster will be used, but make sure
# that it has appropriate configuration(incl. number of Nodes, rHosts, kube-types etc.)
(venv)AppCloud BUILD_CLUSTER=1 python run_integration_tests.py --pipelines main --all-tests --live-log
```
Pipelines could be started in parallel

##### TODO
To make tests work we need to fix at least this files to use correct values from some configuration files and/or envvars instead of hardcoded things:

    dev-utils/dev-env/ansible/roles/master/defaults/main.yml
    dev-utils/dev-env/ansible/roles/common/vars/main.yml
    dev-utils/dev-env/ansible/roles/node/tasks/main.yml
    dev-utils/dev-env/ansible/roles/rhost/tasks/routes.yml
    dev-utils/dev-env/ansible/roles/whmcs/tasks/main.yml
    dev-utils/dev-env/ansible/roles/whmcs/vars/main.yml
    dev-utils/dev-env/Vagrantfile
    tests_integration/assets/cpanel_credentials.json
    dev-utils/dev-env/ansible/roles/plesk/defaults/main.yml
    dev-utils/dev-env/ansible/roles/whmcs/defaults/main.yml
    dev-utils/dev-env/ansible/roles/common/tasks/ceph.yml
    kuberdock-ci-env

--------

# Licensing
KuberDock code itself is licensed under the GPL License, Version 2.0 (see
[LICENSE](https://github.com/cloudlinux/kuberdock-platform/blob/master/LICENSE) for the full license text), but some parts and dependencies may use their own licenses, and for this components, we include their licenses to this repo as well.
- Kubernetes AWS deploy scripts - Apache 2.0
- pyasn - BSD
- fonts - Apache 2.0
- mocha-phantomjs - MIT
- paramiko-expect - MIT
