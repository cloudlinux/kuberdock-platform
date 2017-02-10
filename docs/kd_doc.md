* [Introduction](#bookmark=kix.lsruz1pdat8t)

* [Terminology](#bookmark=kix.95mzojtvp79k)

* [Installation](#bookmark=kix.j3ysv2g1ge6n)

    * [Requirements](#bookmark=kix.xei3ie79mzr)

    * [Master installation guide](#bookmark=kix.t1y7i4uv3npu)

    * [Node installation guide](#bookmark=kix.kk7g58hhs2hx)

    * [Install KuberDock at Amazon Web Services](#bookmark=kix.ll1yzhnn6w3g)

        * [Managing Elastic Block Storage (EBS) on Amazon AWS](#bookmark=kix.i6jv12tkk3yo)

        * [Setting up VPC peering connection](#bookmark=kix.63cmr6g7dcd5)

        * [Uninstalling KuberDock on AWS](#bookmark=kix.9szpl6ifqk8b)

    * [KuberDock update instruction](#bookmark=kix.xirm38o7bp5g)

    * [KuberDock design customization](#bookmark=kix.5alqctcejwfu)

* [Billing](#bookmark=kix.kehjzpxinvfw)

* [Billing integration (supported systems)](#bookmark=kix.h3ap0t5wt00b)

    * [Billing API](#bookmark=kix.womzgkotjx46)

        * [Packages](#bookmark=kix.vzxv4jlhbg1j)

        * [Kube Type](#bookmark=kix.go69osv6srvs)

        * [Users](#bookmark=kix.xaswnhpitqc)

        * [Billing data](#bookmark=kix.2eza3so5otuj)

        * [Predefined application](#bookmark=kix.h9tso8248msn)

    * [WHMCS integration](#bookmark=kix.g6e7yl8938ix)

        * [Update WHMCS addon](#bookmark=kix.4jdwimv0kbi7)

        * [Configure packages](#bookmark=kix.5v2qu297pktq)

        * [Configure Kube Types](#bookmark=kix.bg64es9c3bt3)

        * [Managing clients](#bookmark=kix.h4up8881d8o8)

* [Shared hosting panels integration](#bookmark=kix.5y33yfrxm50v)

    * [cPanel](#bookmark=kix.yz0di4zcl8k7)

        * [KuberDock plugin installation](#bookmark=kix.bhkj2tru9k52)

        * [Configure cPanel to work with WHMCS](#bookmark=kix.brjb9xk1sgke)

        * [Set up predefined applications](#bookmark=kix.axbydgpfj330)

        * [cPanel user guide](#bookmark=kix.keiza68hjxmx)

            * [Start predefined applications](#bookmark=kix.x16nfagnp753)

            * [Set up custom application](#bookmark=kix.5i0d9f8sa4yq)

            * [Managing applications](#bookmark=kix.u38xo1q1vkbf)

    * [Plesk](#bookmark=kix.jtt6d6rgog5g)

        * [KuberDock plugin installation](#bookmark=kix.h9tskn58wep4)

        * [Configuring Plesk to work with WHMCS](#bookmark=kix.x0xa0vcgqc3c)

        * [Set up predefined applications](#bookmark=kix.itnvsqoyppy8)

        * [Plesk user guide](#bookmark=kix.nwk7nrjsjner)

            * [Start predefined applications](#bookmark=kix.gwhn8f8v1ixi)

            * [Set up custom applications](#bookmark=kix.zgjuhj4lqivf)

            * [Managing applications](#bookmark=kix.a6aix2fbpqq3)

    * [DirectAdmin](#bookmark=kix.xpgd2achv91y)

        * [KuberDock plugin installation](#bookmark=kix.hbcr561941zr)

        * [Configure DirectAdmin to work with WHMCS](#bookmark=kix.p0ekgeh67dzp)

        * [Set up predefined applications](#bookmark=kix.q8v1a7jej190)

        * [DirectAdmin user guide](#bookmark=kix.l60jtdm8esou)

            * [Start predefined applications](#bookmark=kix.7rz3mrux28ob)

            * [Set up custom application](#bookmark=kix.c3vax9m1quyk)

            * [Managing applications](#bookmark=kix.h1uplzubxdft)

    * [KuberDock plugin update instructions](#bookmark=kix.d9sjhxwzilj6)

* [Command line API](#bookmark=kix.72tmq3s732ks)

    * [How to set up](#bookmark=kix.eex5294e8bmo)

    * [How to use](#bookmark=kix.v6aw3lmtqsa8)

    * [Kdctl utility](#bookmark=id.5ri3anqj1ppz)

        * [How to set up](#bookmark=id.5ri3anqj1ppz)

        * [How to use](#bookmark=id.q6hdzkwe88cp)

* [User guide](#bookmark=id.6roskdwr4mhz)

    * [Managing pods](#bookmark=kix.pqbp7um60i2z)

        * [Pod page](#bookmark=id.hw0vpnqrx9iv)

        * [Edit pod](#bookmark=id.zunryz958a8)

        * [SSH/SFTP access to containers](#bookmark=id.1uur7ym0r7cb)

    * [Creating a container](#bookmark=id.up82ec30tz2j)

    * [Managing containers](#bookmark=id.z15lpnb0em97)

        * [Container page](#bookmark=id.60079mfjiyyl)

        * [Logs](#bookmark=id.60079mfjiyyl)

        * [Monitoring](#bookmark=id.oe9ly6oy1nzt)

        * [Configuration](#bookmark=id.ygigttv2pcx7)

        * [Environment variables](#bookmark=id.5gr1c4mdsq4t)

    * [Update container](#bookmark=kix.unigxdi0ku5y)

    * [View public IP`s or service addresses](#bookmark=id.pem6upya7tjt)

    * [Managing Persistent volumes](#bookmark=id.bmm5foek49hg)

    * [Edit user profile](#bookmark=kix.suig262ailao)

    * [Start predefined application](#bookmark=id.m0l8pp5xuwf9)

        * [Switch application package](#bookmark=id.ys6zrvinvn3z)

* [Administration](#bookmark=id.7pxl05tta8vb)

    * [Adding predefined applications](#bookmark=id.ko8fspz5k0ub)

        * [Using predefined application with "No billing" settings](#bookmark=id.wkmfwe26s023)

    * [Managing Nodes](#bookmark=id.i34dlhnsb9z8)

        * [Managing accessibility of node ports](#bookmark=id.knbt5n1br9w7)

    * [Managing public IP pool](#bookmark=id.xv5s3da9yvx4)

        * [Using service addresses in AWS deployment](#bookmark=id.7donxzvk5m3a)

    * [Managing Users](#bookmark=id.qwkkae7zok4c)

        * [Adding and editing user](#bookmark=id.8lk4gsaz66ul)

        * [Restore user](#bookmark=id.wkffwz9il22z)

        * [User login session history](#bookmark=id.wguukgne6tt6)

        * [User View Mode](#bookmark=id.1q3wdqdmkqs6)

    * [Domain Control](#bookmark=id.imcr9obn4qas)

    * [Settings](#bookmark=id.c01h49n10v3h)

        * [General](#bookmark=id.t65hbz2rfrts)

        * [License](#bookmark=id.qxa17tqvg5b2)

        * [DNS provider](#bookmark=id.ggmzcpo7r5tq)

        * [Billing](#bookmark=id.msorjvtsdtoj)

        * [Profile](#bookmark=id.qhbvtwq3tc61)

    * [Backups](#bookmark=id.6vcw89eyaq39)

        * [Instructions for KuberDock master server backup & restore](#bookmark=id.mhrxmg402guz)

        * [Instructions for Ceph backup & restore](#bookmark=id.dyt3ug2axtrq)

        * [Instructions for Node backup & pod restore](#bookmark=id.u96dcxsg8m9q)

* [YAML specification](#bookmark=id.fkc1bzaifkgp)

* [Modifying predefined application template](#bookmark=id.ba3ak2q0hrjn)

    * [KuberDock template](#bookmark=id.po8cysoescut)

    * [cPanel template](#bookmark=id.vbqbky3j5sl6)

* [Troubleshooting](#bookmark=id.8l63ciics4q9)

    * [Known issues](#bookmark=id.poj6qduhdapv)

INTRODUCTION

KuberDock is a PaaS solution that allows users to run applications using Docker container images. Containers are grouped into [Pods](#bookmark=kix.dzhy9271gfyo). Creating a container will automatically create an New Pod.

Containers inside a pod:

* can have only one public (external) IP. The IP is shared among containers in the pod;

* are located on the same server;

* are connected to each other by localhost IP address(127.0.0.1) and pod port which is mapped to container port;

* share the same [Kube Type](#bookmark=kix.k0vfh3mcl1if);

* share the same [restart ](#bookmark=kix.32a6e3nbg8yt)[policy](#bookmark=kix.32a6e3nbg8yt);

* can be stopped/started together in one click.

Containers in different pods can only connect to each other via [pod IP](#bookmark=kix.ewulbshykxbf). Different pods can have different [Kube Types](#bookmark=kix.k0vfh3mcl1if), and can be located on different servers, their restart policy and lifecycle are individual.

The interaction between containers and pods and their connection to the Internet are displayed in the following diagram:

![image alt text](screenshot_part1/image_0.png)

TERMINOLOGY

**Node **-- a server in KuberDock cluster where users' pods and containers are located. Each node can have only one Kube Type (multiple Kube Types within one node will be supported hereafter). KuberDock administrator can add and control the nodes using KuberDock web-interface.

**Kube **-- an abstract minimal set of resources allocated to a container.

**Kube Type** -- a particular set of resources predefined for each [container](#bookmark=kix.ik3gk0zal05j). 

For example, a Kube can have:

0.1 of CPU core (which means 10% of one CPU core);

128MB of RAM;

1GB of disk space;

10GB of traffic (under development).

Then a container with 10 Kubes would have:

1 CPU core;

1280MB of RAM;

10GB of disc space;

100 GB of traffic (under development).

Kubes can be of multiple types. Such setup allows service provider to sell different sets of resources at different prices, as well as resources based on different hardware.

Different KuberDock [nodes](#bookmark=kix.2otaocteqk1x) can support different Kube Types.

For example, provider might want to have SSD Kube Type defined for the nodes with SSD drives, or high memory nodes for servers with a lot of memory on them.

**Pod **-- a collocated group of containers running with a shared context. Containers within the pod share the same Pulbic IP, restart policy and Kube Type, they are connected to each other via 127.0.0.1 IP.

A pod models an application-specific "logical host" in containerized environment. It may contain one or more relatively tightly coupled applications - in pre-container world, they would have executed on the same physical or virtual host.

**Container** -- a virtualized, isolated environment for applications to run within a pod.

**Container image** -- an application image with all the necessary data for it to run. Images can be retrieved from [Docker hub registry](https://registry.hub.docker.com/) or other registries.

**Pod IP** -- IP address of KuberDock internal network pod, that is used for connection with other pod owned by the same user.

**Restart policy** -- defines if a container in the [pod](#bookmark=kix.dzhy9271gfyo) should be restarted, after it has been executed:

* *Never *- if you don't need to restart a container automatically;

* *Always *-  if you need to restart a container in case of it terminated with error, or when application inside a container terminated causing container to stop;

* *OnFailure *- if you need to restart a container only if its exit code equals "0", (container terminated with an error).

**User roles** -- user access level to KuberDock which has few types:

* *Admin *-- a user with administrator access level;

* *User *-- standard KuberDock user access level;

* *TrialUser *-- a user with limited access level; provides the same credentials as standard KuberDock user, but with limited number of Kubes (no more than 10 Kubes per user)

* LimitedUser -- a user with no ability to create new pods and containers.

INSTALLATION

**Requirements**

* Hardware requirements: 

Master or Node: 2 core CPU, 2 GB RAM and 100 GB HDD.

To use ZFS as a Local Storage backend it is strongly recommended to have at least 1 GB RAM per Node plus additional 1 GB for each whole or partial TB of total storage.

* OS requirements:

Clean 64bit CentOS Linux release 7.2.1511 (Core) or higher, XFS file system.

UTF8 is expected otherwise your system locale would be set to UTF8.

* Networking requirements:

1) KuberDock nodes must share the same broadcast domain to enable public IP migration from node to node.

2) Master must have ability to resolve all node hostnames to IPs.

3) A free subnet of 16-bit mask in the block of IP addresses 10.0.0.0 - 10.253.255.255 (e.g. 10.201.0.0/16) is necessary for service purposes.

4) To provide pods with [SSH feature](#bookmark=id.1uur7ym0r7cb) the node where they are hosted must be accessible from the Internet via the TCP protocol.

* Persistent storage requirements (optional):

Ceph ([http://ceph.com/ceph-storage/file-system](http://ceph.com/ceph-storage/file-system/))

or

Amazon EBS (if running inside AWS [https://aws.amazon.com](https://aws.amazon.com/), [http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/AmazonEBS.html](http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/AmazonEBS.html)),

or

Local disks (on KuberDock nodes)

*Other persistent storage solutions will be supported hereafter.*

* Load Balancer requirement - will be added soon.

* Web interface supports the following browsers: Safari version 6 or later, Chrome version 38 or later, Firefox version 28 or later.

**Master Installation guide**

Before installation please read the [requirements](#bookmark=kix.xei3ie79mzr) carefully.

As an example, please check our [video guide](https://www.youtube.com/watch?v=4jjYubmGkS4&list=PLpqZ4QntcUI_FptpsEzN7oGRTXKuwHD8p) about how to deploy KuberDock without Ceph. (Note. Video is still under development.)

The following points should be kept in mind while deploying the master:

* For the reasons of scalability, backup and migration simplification, it is strongly recommended to use a virtual machine instead of a hardware server for the master deployment.

* SELinux is expected to be enabled on the master server.

* KuberDock implements all necessary protection of the master and nodes to ensure its network security. Any additional firewall setup will break the networking system.

* The 16-bit-long service subnet can be either directly specified or auto-detected during the deployment.

Use the option *--pod-ip-network* of the *deploy.sh* script to define the subnet directly (e.g. *--pod-ip-network 10.1.0.0/16*). If specified subnet isn’t free KuberDock networking may be disrupted.

If the option is omitted the required free IP address range will be detected automatically in the block from 10.0.0.0 to 10.253.255.255. Lack of free subnet in the block will result in the deployment error.

Log in to master server console as root and perform the following steps:

1. Download installation script from the repository by running the command. Note that when you download and install the file you automatically agree to the terms and conditions of [KuberDock licence agreement](http://kuberdock.com/terms.html):

*wget **[http://repo.cloudlinux.com/kuberdock/deploy.s*h](http://repo.cloudlinux.com/kuberdock/deploy.sh)

(to install wget use:  *yum install wget)*

2. Start installation script by running the command and don't forget to read available deploy options below:

*bash ./deploy.**sh*

Available option for deployment script:

* [Deploy with a fixed IP pools](#bookmark=kix.4gfm3gtqcq0z)

* [Deploy with CEPH support](#bookmark=kix.xpqb4e1fz17e)

* [Deploy with ZFS as a local storage backend](#bookmark=kix.q4jbbpl70mk9)

**Deploy with fixed IP pools**

KuberDock supports **fixed IP pools** from 1.3.0 version. To deploy KuberDock cluster with **fixed IP pools ** use option *--fixed-ip-pools:*

Example:

*deploy.sh --fixed-ip-pools*

After installation with this option it would be possible to assign IPs for each node. Read more about adding IPs for nodes in [Managing IP pool section](#bookmark=id.xv5s3da9yvx4).

**Deploy with CEPH support**

To install KuberDock with CEPH support all CEPH parameters (ceph.conf file, ceph user and user keyring) must be specified to enable CEPH in KuberDock. CEPH user must have at least the following capabilities:	*caps mon = "allow r"	caps osd = "allow rwx pool=<your-KD-pool-name-here>"*

If provided CEPH user has no capabilities to create CEPH pool, then the pool must be created before adding any new nodes to KuberDock cluster by an administrator. Follow official CEPH instruction to create pool http://docs.ceph.com/docs/hammer/rados/operations/pools.

To install cluster with CEPH support, the following options for *deploy.sh* must be defined:

*--ceph-user <username>*where username is a name of a user in CEPH cluster (in CEPH this is a "client.<username>").

*--ceph-config /path/to/ceph.conf*defines path to ceph.conf filename.

It must be copied to KuberDock master server from a CEPH admin host. For example, copy file to */etc/ceph *folder, then option will be *--ceph-config /etc/ceph/ceph.conf*.

*--ceph-user-keyring /path/to/ceph.client.***_username_***.keyring*defines path to keyring file with credentials for CEPH user. It must be copied from CEPH admin host to KuberDock master server.

If you cannot find this file then you can execute it by command on CEPH admin host:

*ceph auth export client.***_username_*** > ceph.client.***_username_***.keyring*where username must be the same as defined by *--ceph-user* option.

Finally, the example of running KuberDock deploy script with CEPH support will look as follows:

*bash ./deploy.sh --ceph-user your_ceph_user --ceph-config /path/to/ceph.conf --ceph-user-keyring /path/to/client.your_ceph_user.keyring*

If you install cluster with default namespace for persistent drives, thenthe pool will be named as ipv4 address of KuberDock master server, for example *123.123.123.*1. Alternatively you can specify namespace using option:

*--pd-namespace <your-KD-pool-name-here>*

This parameter allow to explicitly define CEPH pool name.Example:

*bash ./deploy.sh --ceph-user my_ceph_user --ceph-config /path/to/ceph.conf --ceph-user-keyring /path/to/client.my_ceph_user.keyring ***_--pd-namespace my_namespace_name_**

**Deploy with ZFS as a local storage backend**

Please read [requirements](#bookmark=kix.xei3ie79mzr) before start to deploy KuberDock with ZFS.

KuberDock adjusts several ZFS-related settings to optimize overall Input/Output performance:

* ZFS filesystem parameter *recordsize* is set to 16K instead of default 128K. This is done at the zpool level and affects all Persistent Volumes of user pods

* Maximal size of ZFS-used caching tool ARC is limited to 1/3 of total memory available at the host

* The file-level prefetching mechanism of ZFS is disabled:*zfs_prefetch_disable = 1*

To deploy KuberDock as a backend for local storage run command:

*bash ./deploy.sh --zfs*

Then all local storages of docker containers will be located on the ZFS.

3. Then the script automatically detects available IP address of the master and proposes to confirm it or enter another value:

*Enter master server IP address to communicate with the nodes (it should be an address of the cluster network):*

*[**founded_ip_here**]*

Make sure that this address is the same as specified in the cluster network settings for the master to communicate the nodes.

4. Enter interface to bind public IP addresses on nodes:* [founded_interface_here]:*

5. When installation completed you will see the following message:

*Installation completed and log saved to /var/log/kuberdock_master_deploy.log*

*KuberDock is available at **[https://master-ip*/](https://master-ip/)

*login: admin*

*password: [your password]*

Please, save your password in secure place

Note that if during installation errors occurred and you don't see this message, then run the command:

*bash ./deploy.sh --cleanup*

After that start installation from the first step.


6. Go to the following address in your browser: *[https://master-ip*/](https://master-ip/) and log in using your administrator credentials.

7. Go to Settings page and click License. Click pen icon to enter Installation ID to activate KuberDock. If you do not have Installation ID, then go to [kuberdock.com](http://kuberdock.com) and click Try KuberDock, fill in the application form and get get trial Installation ID.

![image alt text](screenshot_part1/image_1.png)

Enter Installation ID and click Apply. KuberDock will be activated within the next few minutes:

![image alt text](screenshot_part1/image_2.png)

8. Perform the following steps to configure SSL certificate:

    1. Upload SSL certificate file to the KuberDock master server

    2. Edit file */etc/nginx/conf.d/**kuberdock-ssl.conf* where set path to the ssl files:

    *ssl_certificate /path/to/crt_file.crt; *//path to *crt *file of your certificate  *  ssl_certificate_key /path/to/key_file.key;* //path to *key *file of your certificate  *  ssl_dhparam /path/to/pem_file.pem;* // path to *pem *file of your certificate

Note. Make sure that process "nginx" has access to that files.

    3. Restart process "nginx" by the command:

*service nginx restart*

**Node Installation Guide**

Note that SELinux and SSH PermitRootLogin are expected to be enabled on the node. 

Note that if you install KuberDock master with CEPH support then node installation script will setup CEPH client on this node automatically.

Log in to master server console as root and perform the following steps:

1. Copy nginx users’ SSH key to the node, running the following command: 

*ssh-copy-id -i /var/lib/nginx/.ssh/id_rsa.pub root@your_node*

where *your_node* is node IP address.

**Note**. Nginx user requires root access to the node. The key is generated automatically during master server installation.

When key installation succeeded you will see the following message:

*Number of key(s) added: 1*

2. Log in to KuberDock as Admin.

Note. To restore Admin password, perform the following steps: Log in to master server console and run the command:

*python /var/opt/kuberdock/manage.py reset-password*

Enter new password;

Retype new password.

New password will be saved.

3. Click *Add node*.

![image alt text](screenshot_part1/image_3.png)

4. Specify "uname -n" of the node in *Node hostname* field. Note that “uname -n” should have records in direct and reverse DNS zones or, if you don't have an access to DNS,  in /etc/hosts of all servers in cluster:

![image alt text](screenshot_part1/image_4.png)

The specified hostname will be checked whether or not it can be resolved to a really existing public IP address assigned to one of network interface of the node.

If the check fails, the node won’t be added to the cluster and the following error message will be displayed:

*Node hostname "<NodeHostname>" is resolved to "<NodeIP>" and the Node is accessible by this IP but there is no such IP address on any Node network interface*

When deploying in non-AWS environment with ZFS as a Local Storage backend, an existing free block device (like /dev/sdc or /dev/sdd) should be specified. You can add multiple devices to the node:

![image alt text](screenshot_part1/image_5.png)

Devices are needed to create zpool.

In AWS, all that is required for zpool provisioning will be done automatically.

Choose [Kube Type](#bookmark=kix.k0vfh3mcl1if) for this node from drop-down menu. You can find information on how to add new Kube Types in [Configure Kube Types](#bookmark=kix.bg64es9c3bt3) section. 

Note that only pods with the Kube Type that you have chosen for the node, can be located on that node.![image alt text](screenshot_part1/image_6.png)

5. Click *Add* to start node installation.

Note that deploy script will execute clean up of a node and clear all data to perform clean installation. That is why the node that was previously added will be cleared.

![image alt text](screenshot_part1/image_7.png)

6. Wait until the node is installed - its status will change from *pending *to *running*. Note that during installation process (which can take up to an hour) the node will be restarted. During the reboot node status may be displayed incorrectly (if it takes more than one minute), it will be changed automatically right after reboot completed.

![image alt text](screenshot_part1/image_8.png) 

You can go to the Node page while its status is still *pending* to monitor installation process log.

If node installation failed, you can find the reason in the log as well.

Note that memory swap is disabled on the nodes by default, which is required to ensure strict limitation of RAM allocated to users' containers. It is strongly recommended not to enable memory swap on the nodes.

**Install KuberDock at Amazon Web Services**** (AWS)**

## Requirements

1. You need an AWS account. Visit[ http://aws.amazon.com](http://aws.amazon.com) to get started.

2. Install and configure[ AWS Command Line Interface](http://aws.amazon.com/cli) (AWS CLI).

3. You need an AWS[ instance profile and role](http://docs.aws.amazon.com/IAM/latest/UserGuide/instance-profiles.html) with the *Administrator Access* policy (see below).

4. You need to generate a pair of AWS access key ID and secret access key that will be used by KuberDock. 

In CentOS environment, AWS CLI can be installed as follows:

*yum install python-pip*

*pip install -U pip*

*pip install awscli*

If you use another operating system or need more detailed instructions of how to install and configure AWS CLI please refer *[Installing the AWS Command Line Interface - AWS Command Line Interfac*e](http://docs.aws.amazon.com/cli/latest/userguide/installing.html).

Note: KuberDock deploy script creates AWS Virtual Private Cloud (VPC) instances.

Note: KuberDock deploy script will create EBS storage to use it as persistent storage. More information and instruction are in section [Managing Elastic Block Storage (EBS) on Amazon AWS as KuberDock persistent storage](#bookmark=kix.i6jv12tkk3yo). **This functionality is still under development.** 

## Getting started with AWS

You may skip this section if you are aware of how to setup Amazon Web Services (AWS) and get permissions necessary to deploy KuberDock.

 

To start AWS usage log in[ its official site](https://aws.amazon.com/) and select the *Security Credentials* item in the *My Account* dropdown:

![image alt text](screenshot_part1/image_9.png)

In the pop-up dialog box, click the *Get Started with IAM Users* button:

![image alt text](screenshot_part1/image_10.png)

Click *Create new user* in the new form:

![image alt text](screenshot_part1/image_11.png)

The next screen presents user’s security credentials — Access Key ID and Secret Access Key — as on the example below:

![image alt text](screenshot_part1/image_12.png)

The keys may be downloaded as a text file pressing the *Download Credentials* button or merely copied directly from the screen.

On the *Permissions* tab of the next form press the *Attach Policy* button:

![image alt text](screenshot_part1/image_13.png)

You will be presented with list of available permission policies on the *Attach Policy* screen. At least the *Administrator Access* policy is needed to use Kubernetes:

![image alt text](screenshot_part1/image_14.png)

 

Then it is necessary to obtain Amazon Machine Image (AMI) of Centos 7.

This may be accomplished visiting[ AWS Marketplace](https://aws.amazon.com/marketplace/). Search there for the image *CentOS 7 (x86_64) - with Updates HVM*:

![image alt text](screenshot_part1/image_15.png)

Click *Continue* and on the *Manual Launc*h tab click *Accept Software Terms*:

![image alt text](screenshot_part1/image_16.png)

 

Now KuberDock cluster may be deployed using created user’s credentials.

KuberDock setup instructions:

1. Download archive with installation script:

*wget **[http://repo.cloudlinux.com/kuberdock/aws-kd-deploy.tar.g*z](http://repo.cloudlinux.com/kuberdock/aws-kd-deploy.tar.gz)

2. Unpack it to any folder:

*tar xvfz aws-kd-deploy.tar.gz*

3. Change defaults in cluster/aws/config-default.sh or export as environment variables:

*export **NUM_NODES**=2 // number of nodes in KuberDock**export KUBE_AWS_ZONE=eu-west-1c // specify appropriate region, available for amazon servers*

*export AWS_S3_REGION=eu-west-1 // specify time zone for Amazon Simple Storage Service (S3)*

*export AWS_EBS_DEFAULT_SIZE=20 // This variable available from  **[KuberDock .1.5.*0](#bookmark=id.h1p9rk3zbng1)*; default size of EBS for node which is used for a local persistent storage.*

During the deployment, KuberDock dynamically defines instance types (see[ Amazon EC2 Instance Types](https://aws.amazon.com/ec2/instance-types/)) for the master and nodes to optimize resource usage. However the types can be manually redefined with *MASTER_SIZE* and *NODE_SIZE* variables respectively:

*export MASTER_SIZE=m3.medium // choose appropriate server type for KuberDock master available on Amazon*

*export NODE_SIZE=t2.small // choose appropriate server type for KuberDock node available on Amazon*

Other two variables are intended to define volume type of Elastic Block Storage (EBS) which is used to build Local Storage

Any volume type can be specified in the variable *AWS_DEFAULT_EBS_VOLUME_TYPE* allowing the following value:

* *standard* — it corresponds to a magnetic drive (see[ EBS Previous Generation Volumes](https://aws.amazon.com/ebs/previous-generation/)); default

* *gp2* — one of the new, SSD-backed, volume types optimized for high average number of read I/O operations per second (IOPS) (see[ Amazon EBS Volume Types](http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EBSVolumeTypes.html)). It offers cost-effective storage

* *io1* — another such type designed to meet the needs of I/O-intensive workloads.

The variable *AWS_DEFAULT_EBS_VOLUME_IOPS* is meaningful for the type *io1* only. Its acceptable range is 100 – 20000 (IOPS) and default value is 1000.

Be aware that the maximal number of IOPS which can be provisioned for a volume depends on its size: the maximum ratio of the IOPS to the size in GB is 50:1, but not greater than 20,000 IOPS. That is a 10 GB volume can be provisioned with up to 500 IOPS while a 400 GB or greater one — up to the 20,000 IOPS.

The effect of these variables extends to all nodes in the cluster.

4. To access AWS programmatically, an access key is used. The key consists of an access key ID (something like ‘AKIAIOSFODNN7EXAMPLE’) and a secret access key (something like ‘wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY’). As AWS does not provide the keys for user accounts, a user should create it by own efforts according to [Amazon documentation](http://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSGettingStartedGuide/AWSCredentials.html) and then export such environment variables:

*export AWS_ACCESS_KEY_ID=your_aws_access_key_idexport AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key*

5. By default, all AWS instances assume names starting with the prefix ‘kuberdock’. The default prefix is saved in the variable KUBE_AWS_INSTANCE_PREFIX in the file config-default.sh.

6. When being deployed at AWS KuberDock uses ZFS as a default Local Storage backend. This can be changed via environment variable *KD_USE_ZFS*:

*export KD_USE_ZFS=no*

Another controlled variable of the file config-default.sh is the default EBS volume size in GB. It is named AWS_EBS_DEFAULT_SIZE and is set to 20 (GB):

# EBS Storage initial size

AWS_EBS_DEFAULT_SIZE=20

This variable prescribes initial size of EBS volume for persistent storage when a node is created. It is also used as the default increment when the storage is expanded.

7. A pair of public and private cryptographic keys are used for encryption and decryption of login information, in digital signing, etc. The pair will be generated automatically during the deployment and the public key is imported in AWS under the name captured in the variable AWS_SSH_KEY_NAME of the file util.sh. The name consists of the prefix kuberdock and the key fingerprint:

AWS_SSH_KEY_NAME="kuberdock-${AWS_SSH_KEY_FINGERPRINT//:/}"

If there is necessity to use a particular, but not the automatically generated private key, it should be saved as $HOME/.ssh/kube_aws_rsa (referred by the variable AWS_SSH_KEY of the file config-default.sh) since the auto-generated key is saved in this way.

Regardless of the manner to obtain the keys it is expected that the public key will be saved in the same directory and under the same name as the private one, but with the file extension *.pub.

Note that only owner of the keys can have right to read them, otherwise the deployment will be aborted.

The cluster can be accessed after installation using the private key in a command like:

*ssh -i ~/.ssh/kube_aws_rsa centos@*

8. Run installation script:

*cluster/aws-kd-deploy.sh*

By default, the script provides a new Amazon VPC and a KuberDock cluster with 2 nodes in us-west-2b (Oregon) running on CentOS 7. At that, the master has the *m3.medium* instance type while the nodes — the *t2.small* one. As a result you will get an external IP of KuberDock master and admin login and password.

Note that Amazon VPC has its own limit where only 50 routes per one route table can be added. It means that maximum 50 nodes can be added to KuberDock cluster. You can submit a request for an increase a maximum to 100, see Amazon official documentation [http://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/VPC_Appendix_Limits.html#vpc-limits-route-tables](http://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/VPC_Appendix_Limits.html#vpc-limits-route-tables).

When more than 100 nodes needed, Amazon VPC shouldn’t be used. For this purpose KuberDock should be deployed not by means of AWS KD deploy script which creates VPC, but by running deploy.sh script at instances created and prepared before. During the deployment, VXLAN should be explicitly specified as a backend.

**Managing Elastic Block Storage (EBS) on Amazon AWS as KuberDock persistent storage**

Important note: this feature is under development.

Note that it is possible to add EBS volumes during [KuberDock deploy on Amazon AWS](#bookmark=kix.ll1yzhnn6w3g) and they will be attached to all nodes in the future cluster.

EBS volume will be located in LVM kdstorage00 group of volumes. In this group a logical volume kdls00 formatted to xfs will be created, it will fill all EBS space.

Logical volumes are used for creating persistent storages for user containers.

To add one more EBS volume run the command on KuberDock master server:

*python /var/opt/kuberdock/manage.py node-storage add-volume --hostname <node_hostname> [--size <size in GB>]*

where:

*python /var/opt/kuberdock/manage.py* - execution of python script manage.py

*node-storage add volume* - required parameters of the script

*--hostname <node_hostname>* - option to specify hostname of the node, new EBS volume will be attached to. Enter proper name in <node_hostname> 

--size <size> - size of EBS volume being added in GB. Enter number of GB in <size>.

For example:

*python /var/opt/kuberdock/manage.py* *node-storage add-volume --hostname my.node.com --size 200*

As a result 200 GB sized EBS volume will be created and attached to specified node. This volume will be added to LVM kdstorage00 group of nodes, logical volume and file system of kdls00 will be increased by 200GB.

To get information on used space on EBS volumes run the command:

*python /var/opt/kuberdock/manage.py node-storage get-info --hostname <node_hostname>*

where:

*python /var/opt/kuberdock/manage.py* - execution of python script manage.py

*node-storage get-info* - required parameters of the script

*--hostname <node_hostname>* - option to specify hostname of the node, new ELB volume will be attached to. Enter proper value in <node_hostname> 

**Setting up VPC peering connection**

When deploying in Amazon Web Services, external hosts (like hosting control panels or billing systems) may be set up in a Virtual Private Cloud other than that where KuberDock cluster has been installed. To enable KuberDock and the host interaction in such cases, a VPC peering connection is required.

The VPC peering connection can be established between VPCs of the same AWS account as well as between ones belonging to different accounts.

Both cases are similar to great extent. Brief description of the connection setup within a common AWS account is given below. For the detailed explanations please refer the *[Working with VPC Peering Connection*s](http://docs.aws.amazon.com/AmazonVPC/latest/PeeringGuide/working-with-vpc-peering.html) section of the AWS documentation.

 

A VPC peering connection can be created via Amazon VPC console:

![image alt text](screenshot_part1/image_17.png)

Select a desired VPC and initiate a request to peer it with another VPC:

![image alt text](screenshot_part1/image_18.png)

Accept the request:

![image alt text](screenshot_part1/image_19.png)

At this point you will be proposed to modify your route tables (it may be done later as well).

Go to the route tables page and add a route to the route table associated with the subnet where the instance resides:

![image alt text](screenshot_part1/image_20.png)

![image alt text](screenshot_part1/image_21.png)

The connection needs proper configuration of KuberDock and the host subnets:

![image alt text](screenshot_part1/image_22.png)

Route Tables should be updated for both ends of the VPC Peering Connection:

![image alt text](screenshot_part1/image_23.png)

![image alt text](screenshot_part1/image_24.png)

Then it is necessary to enable DNS for the connection:

![image alt text](screenshot_part1/image_25.png)

Finally, the inbound and outbound rules for both VPC security groups should be properly updated to reference security groups in the peered VPC:

![image alt text](screenshot_part1/image_26.png)

![image alt text](screenshot_part1/image_27.png)

Note that to be able to perform the actions above, users need to be granted by means of an appropriate IAM policy with permission to create or modify VPC peering connections.

**Uninstalling KuberDock on AWS**

To uninstall KuberDock cluster previously deployed at Amazon AWS run the following command (the path below is relative to the deployment package):

*bash cluster/aws-kd-down.sh*

This command should be run from that AWS client OS where the credential variables were set and with the same credentials as during the deployment. It will delete all instances and destroy VPC.

**Note** that unlike other VPC-associated (Virtual Private Cloud) resources EBS volumes should be deleted manually via AWS management console.

**KuberDock update instruction**

Note that during update process KuberDock turns into maintenance mode. When KuberDock is updating, the master server is being updated first, then each node is being updated one after another.

While updating, the node is disabled to adopt new users' pods, but the existing pods continue running. When the node is updated, adoption of the new pods is enabled again.

To update KuberDock, perform the following steps:

1. Log in to KuberDock master server as root.

2. Run the command:

kuberdock-upgrade

3. To start update enter "y" in confirmation dialog:

*Newer KuberDock package is available. Do you want to upgrade it ? [y/n]:*

Before upgrade starts, "health check" process will verify KuberDock master server and nodes state. Possible results:

* *Health check: OK.*

If all services work with no errors, then KuberDock upgrade process will start.

* *There are some problems with cluster.*

If a problem discovered - upgrade process will not start. Discovered problem will be described below. To start upgrade - solve the problem and restart upgrade. You can skip "Health check" and restart upgrade, but it will be done at your own risk. 

To skip "Health check" run:

*kuberdock-upgrade --skip-health-check*

This option is quite allowable, however it is strongly recommended not to use it without real need but only when risk of the upgrade failure is probable.

To start "Health check" only, run:

*kuberdock-upgrade health-check-only*

If no updates are required for your KuberDock, then you will be notified with the message: KuberDock is up to date.

If the update process hasn’t completed successfully (e.g. one of the nodes is down or network is disrupted) you will be informed as follows:

*KuberDock has been restarted.*

*Cluster was left in a maintenance mode, you can contact support team for help or remove the error causes and resume the upgrade.*

*Use kuberdock-upgrade set-maintenance on|off to manually switch cluster work mode (careful!)*

It is strongly recommended to [contact KuberDock Support Team](#bookmark=id.hioc5fq6f1zc) in such cases.

However, if you are sure of actual reason of the failure you may eliminate it (restart the failed node or fix the network problem) and continue the update process running the following command:

*kuberdock-upgrade resume-upgrade*

If you need help while using kuberdock-upgrade, run the following command to get additional information or [contact support](#bookmark=id.hioc5fq6f1zc):

kuberdock-upgrade --help

 

There is the *–t* option of the command which enables testing repository. It is intended for development purposes only and should not be used in the production.

If remote hosts (like billing system or shared hosting panel server) have been added to KuberDock it is necessary to restore their connectivity, e.g. access of a shared hosting panel to pods.

For this purpose, upon successful completion of KuberDock upgrade follow the steps as described in[ KuberDock plugin update instructions](#bookmark=kix.d9sjhxwzilj6).

**KuberDock design customization**

To set custom logo and styles go to master server with root permissions. Use command *kdcustomize *to set path to files. For example:

*kdcustomize --logo=/path/to/logo.png --styles=/path/to/custom/styles.css --login-logo=/path/to/login-log.png --login-styles=/path/to/custom/login/styles.css*

Where:

--logo and --styles - path to files for KuberDock user and administrations panels

--login-logo and --login-styles - path to files for login page of KuberDock.

Size of logo and login-logo are different and must be equal to 162x48 and 227x67 pixels accordingly. If an image of different size is specified an error will be raised.

It's advisable to clear a browser cache after updating logos and styles.

Note that currently resetting to original logos and removing custom styles are not provided.

For more information about usage of kdcustomize use help:

*kdcustomize --help*

BILLING

**How do we calculate the prices**

KuberDock billing is based on resource levels allocated to user per hour, per month, per quarter, or per year. The resources are calculated in [Kubes](#bookmark=kix.updlgo6yxca4). Service providers can set up different [Kube Types](#bookmark=kix.k0vfh3mcl1if) and sell them at different prices. Container limits are considered as ‘allocated resources’, meaning that if a customer set up a container that is 5 Kubes size, we will bill it as 5 Kubes per chosen period without accounting for amount of resources container is actually using.

KuberDock calculates the amount of resources allocated to user at any given hour (or other chosen period), and submit that info to the billing system using KuberDock API. This data is used by billing system to calculate the charges.

*For example:*

End user has 2 [pods](#bookmark=kix.dzhy9271gfyo). Each pod has a number of  [docker containers](#bookmark=kix.ik3gk0zal05j) and containers inside the pod are limited to:

Pod #1 -- 3 Kubes of Kube Type #1.

Pod #2 -- 2 Kubes of Kube Type #2.

Each pod has been working for 4 hours during the day. Then the total amount that end user would have to pay will be the following:

*12 Kubes for Pod#1 multiplied by price of  Kube Type#1 per hour + *

*8 Kubes for Pod#2 multiplied by price of Kube Type#2 per hour*

The information on consumed Kubes is submitted to billing system. Billing system makes calculations and charges user for this amount of resources.

**How prices are set based on packages, Kube Types**

In KuberDock prices are set by a provider in billing system on package level. Service provider can set the following prices:

* first deposit;

* price per public IP;

* price per GB for persistent storage;

* price per additional traffic, per GB (traffic count will be added soon);

* price per Kube per chosen period for each Kube Type for this package. More about [Kube Type](#bookmark=kix.k0vfh3mcl1if).

**What does end user see when he orders KuberDock **

**	**When a customer signs up for a KuberDock account, end user should see the following according to service provider billing setup:

* first deposit sum;

* price for using one Public IP;

* price per GB for using persistent storage*;

* traffic volume included in a package;

* over traffic* cost per GB (traffic count will be added soon);

* one Kube price for each [Kube Type](#bookmark=kix.k0vfh3mcl1if) in a package. Kube Type includes:

    * RAM capacity;

    * Disk space capacity;

    * CPU power

    * Included amount of traffic in GB (under development).

**The correlation between data volume and price is set by a provider.*

**What happens if an end user does not pay for resources**

** **Few different behaviors are possible in that case:

* In case of PAYG billing type.

When an end user does not have money to continue using a KuberDock, then he becomes suspended in billing system and in KuberDock. His pods stop, but IPs and persistent storage still exist.

Depending on billing configuration it is possible to set *suspended **days* which means that according to the configured amount of suspended days KuberDock will wait until suspend unpaid pods.

Other configuration is *termination days* which means that after configured amount of termination days after due payment date KuberDock will unbind IP and destroy persistent storage of the pod.

* In case of fixed price billing type.

After an end user does not pay for for the working services (predefined application or custom pods) for the upcoming period, then unpaid services acquire "unpaid" status. It means that it will not work but all IPs and persistent storages will be saved. Note that paid services will continue running. That`s why we do not suspend user in billing system and it will be active.

Depending on billing configuration it is possible to set *suspended** days* which means that according to configured amount of suspended days KuberDock will wait until stop the pod and will change it status to unpaid. Note that as we do not suspend user in case of fixed price billing type we still use the same parameter in billing system to count days after which we will stop services.

BILLING INTEGRATION (supported systems)

	KuberDock can be integrated to different billing systems by means of API. The integration with WHMCS is implemented by means of this API as well. Out of the box support for other popular billing systems will be added soon, however you can integrate KuberDock with your own custom billing solution through the API provided below.

	**Introduction**

The following instructions provide you with API requests designed to integrate KuberDock to your billing solution. To learn about the principles of KuberDock billing system operation, please read [Billing](#bookmark=kix.kehjzpxinvfw) section. To integrate with WHMCS go to [WHMCS ](#bookmark=kix.g6e7yl8938ix)Integration section.

Important note

To set up integration with billing API correctly, perform the following steps:

1. [Install KuberDock](#bookmark=kix.j3ysv2g1ge6n) and save generated password for the user "admin".

2. Apply token authorization, follow the instruction of getting a token in "[Configuring Users requests](#bookmark=kix.xaswnhpitqc)" section.

*PUT **[https://kuberdock.master/api/pricing/kubes*/](https://kuberdock.master/api/pricing/kubes/)*<kube_type_id>?token=admin_token*

json-data:

*{*

*		… //here is data of the request*

*}*

3. Create necessary packages and submit them to KuberDock following the instructions in [Packages](#bookmark=kix.vzxv4jlhbg1j) section.

4. Create Kube Types and specify their prices for each package. Follow the instructions in "[Kube Types configuration](#bookmark=kix.go69osv6srvs)" section to submit your data to KuberDock. Specifying the price will automatically include a Kube Type into the package. If Kube Type price is not specified for a package, then this Kube Type will not be available in this package. Note that you can add unlimited number of Kube Types to a package.

5. Follow the instruction in [Configuring users](#bookmark=id.brw9g8yosp4) section to set up the submission of your data to KuberDock. When registration successfully completed, send user email notification with KuberDock master IP address and credentials. Save package name purchased by a user in billing system to define Kube Type cost when getting statistics. A user can purchase only one package at a time.

6. Follow the instructions in [Billing data capture requests](#bookmark=id.2bbqd3qie1ys) section to set up KuberDock usage daily statistics notifications. Usage statistics for each container includes: start and stop time marks, Kube Type and Kubes number.

Package related API calls:

* create a package:

request:

*POST https://kuberdock.master/api/pricing/packages/*

json-data:

*{*

*"first_deposit": “first_deposit”, // *specify sum of money a user should pay to start using KuberDock *e.g “2”, “20”, “5.5”*

*"currency": “currency_code”, // e.g. USD*

*"id": “package_id”,*

*"name": “package_name”,*

*"period": “hour”, // can be “hour”, “month”, “quarter”, “annual”*

*"prefix": “currency_prefix”,*

*"suffix": “currency_suffix”,*

*"price_ip": “price_per_ip"*

*"price_pstorage": “price_pstorage”, // per GB*

*"price_over_traffic": “price_over_traffic”, // ***_under development_***, per GB*

*}*

response:

*{*

*  "data“: {*

*"first_deposit": “first_deposit”,*

*"currency": “USD”,*

*"id": “1”,*

*"name": “package_name”,*

*"period": “hour”,*

*"prefix": “currency_prefix”,*

*"suffix": “currency_suffix”,*

*"price_ip": “price_per_ip”,*

*"price_pstorage": “price_pstorage”,*

*"price_over_traffic": “price_over_traffic”,*

*},*

*  "status": “OK”*

*}*

* update a package:

	Please note, that making changes in pricing will affect existing users of this package starting from the date the changes have been made.

You can change several fields for a package in one request.

request:

PUT https://*kuberdock.master*/api/pricing/packages/<package_id>

json-data: 

*{*

*"currency": “USD”,*

*"first_depoist": “20” *

*}*

response:

{

  "status": “OK”

}

* retrieve billing info for a package

request:

*GET https://kuberdock.master/api/pricing/packages/<package_id>*

	response:

*{*

*  "data": {*

*	"first_deposit": “first_deposit”,*

*	"currency": “USD”,*

*	"id": “1”,*

*	"name": “pacakge_name”,*

*	"period": “hour”,*

*	"prefix": “currency_prefix”,*

*	"suffix": “currency_suffix”,*

*"price_ip": “price_per_ip”,*

*	"price_pstorage": “price_pstorage”,*

*	"price_over_traffic": “price_over_traffic”, ***_under development_*** *

*  },*

*  "status": "OK"*

*}*

* retrieve all packages:

request:

*GET https://kuberdock.master/api/pricing/packages*

response:

*{*

*  "data": [*

*	{*

*  	"first_deposit": “first_deposit”,*

*  	"currency": “USD”,*

*  	"id": 0,*

*  	"name": “package_name”,*

*  	"period": “hour”,*

*	"prefix": “currency_prefix”,*

*	"suffix": “currency_suffix”,*

*	"price_ip": “price_per_ip”,*

*	"price_pstorage": “price_pstorage”,*

	*"price_over_traffic": “price_over_traffic”, ***_under development_**

},{…}

  	],

"status": "OK"

}

* delete package:

Note that you can not delete a package if it is assigned to any user in the database. To check users' attachment to a package, use the information you can get from "get all users info" request. (Users section of the current topic). 

request:

*DELETE https://kuberdock.master/api/pricing/packages/<package_id>*

response:

*{*

*  "status": “OK”*

*}*

API calls related to [Kube Types](#bookmark=kix.k0vfh3mcl1if):

* create a Kube Type:

request:

*POST https://kuberdock.master/api/pricing/kubes/*

json data:

*{*

*"name": “some_kube_type_name,*

*"cpu": 0.2, *// specify core percentage allocated to one Kube. E.g. 0.1 means 10% of a CPU core; 1.5 means 100% of one core and 50% of another. 

*"memory": 128,* // in MB

*"disk_space": 5,*

*"included_traffic": 100, *// **_under development_****_, _**in GB

"is_default": “true” // Is not mandatory. Setting this flag to false is forbidden. You can change default kube type by setting another kube type as default.

*}*

response:

*{*

*  "data":*

*{*

*	"cpu": 0.2,*

*	"cpu_units": “Cores”,*

*	"disk_space": 5,*

*"disk_space_units": “GB" // value for disk space limits*

*"cpu_units": “Cores”, //value for CPU limits*

*	"id": 9,*

*	"memory": 128,*

*	"memory_units": “MB”, //value for memory limits*

*	"name": “personal”,*

*	"total_traffic": 100 // ***_under development_**

*	"is_default": null,*

* 	},*

*  "status": “OK”*

*}*

* update a Kube Type:

	Note that changing Kube Type will not affect existing containers until they are restarted.

You can change several fields for Kube Type in one request.

request:

*PUT https://kuberdock.master/api/pricing/kubes/<kube_type_id>*

json-data:

*{*

*"cpu": 0.3,*

*"name": “new_name”*

*}*

response:

*{*

*  "status": “OK”*

*}*

* get a Kube Type:

request:

*GET https://kuberdock.master/api/pricing/kubes/<kube_type_id>*

response:

*{*

*  "data": *

*{*

*  	"cpu": 0.2,*

*  	"cpu_units": “Cores”,*

*  	"disk_space": 0,*

*  	"id": 0,*

*  	"memory": 64,*

*  	"name": “kube_name”,*

*  	"included_traffic": 0, // ***_under development_**

*	},*

*  "status": “OK”*

*}*

* get all Kube Types:

request:

*GET https://kuberdock.master/api/pricing/kubes*

response:

*{*

*  "data": [*

*	{*

*  	"cpu": 0.2,*

*  	"cpu_units": "Cores",*

*  	"disk_space": 0,*

*  	"id": 0,*

*  	"memory": 64,*

*  	"name": "kube_name",*

*  	"included_traffic": 0, // ***_under development_**

*	},*

*            ….*

*  ],*

*  "status": "OK"*

*}*

* retrieve list of Kube Type IDs available in a package by package ID:

request:

*GET https://kuberdock.master/api/pricing/packages/<package_id>/kubes-by-id*

response:

*{*

*  "data": [*

*	0,*

*	1,*

*	2*

*  ],*

*  "status": "OK"*

*}*

* retrieve Kube Type names of a package by package IP:

request:

GET https://*kuberdock.master*/api/pricing/packages/<package_id>/kubes-by-name

response:

*{*

*  "data": [*

*	"Standard kube",*

*	"High CPU",*

*	"High memory"*

* 	],*

*  "status": "OK"*

*}*

* retrieve details of Kube Types of a package:

request:

*GET https://kuberdock.master/api/pricing/packages/<package_id>/kubes*

response:

*{*

*  "data":[*

*	{*

*"cpu": 0.2,*

*"cpu_units": "Cores",*

*"disk_space": 0,*

*"disk_space_units": "GB",*

*"id": 0,*

*"memory": 64,*

*"name": "kube_name",*

*"kube_price": 0.7,*

*"memory_units": "MB",*

*"name": "Test Kube 2"*

*"included_traffic": 0, // ***_under development_**

*	},*

*           {...}, ...*

* 	   ],*

*  "status": "OK"*

*}*

* add a Kube Type to a package:

request:

POST: https://*kuberdock.master*/api/pricing/packages/<package_id>/kubes/

json data: 

*{*

*"id": 1, *// ID of the kube to be added

*"kube_price": 0.03*

*}*

response:

*{*

*  "status": "OK"*

*}*

* exclude Kube Type from a package:

request:

*DELETE https://kuberdock.master/api/pricing/packages/<package_id>/kubes/<kube_type_id>*

response:

*{*

*  "status": "OK"*

*}*

* delete a Kube Type

request:

*DELETE https://kuberdock.master/api/pricing/kubes/<kube_type_id>*

response:

*{*

*  "status": "OK"*

*}*

Requests for working with users:

* create a user:

request:

*POST **https://kuberdock.master**/api/users/all*

json data:

*{*

*"first_name": “user_first_name”,*

*"last_name": “user_last_name”,*

*"middle_initials": “user_middle_initials”,*

*"username": “username”,*

*"active": “true”, // or “false” equal “Locked” in web-interface*

*"suspended": false, // can be true or false*

*"email": “user@email”,*

*"password": “user_password”,*

*"role": “role_name”, // see predefined **[user role*s](#bookmark=kix.efooma3ui4pu)

*"package" : “package_name”*

*}*

**response:

if success user data

*{*

*"result": “OK”,*

*}*

otherwise

*{*

*"result": “error”,*

*"message": “...”*

*}*

* update a user:

You can change several user’s fields in one request.

request:

*PUT **https://kuberdock.master**/api/users/all/<username>*

json data:

*{*

*"first_name": “new_user_firstname”*

*"last_name": “new_user_lastname”*

*}*response:

if success user data

*{*

*"result": “success”*

*}*

otherwise

*{*

*"result": “error”,*

*"message": “...”*

*}*

User update includes suspending this user for the time of changing his/her "active" state from True to False and vice versa, and accordingly stopping all his/her containers.

* get user token to login to KuberDock:

request:

*curl -k -s -u <username>:<password> "https://**kuberdock.master**/api/auth/token"*

result:

*{*

*"status": "OK",*

*"token": "token"*

*}*

token usage:

*curl -k -s "https://**kuberdock.master**/api/users/all?token=<token>"*

* get user info:

request:

*GET https://kuberdock.master/api/users/all/<username>*response:

if success user data

*{*

*"result": “success”,*

*"data":*

* {*

*"first_name": “John”,*

*"last_name": “Smith”,*

*...}}*

otherwise:

*{*

*"result": “error”,*

*"message": “...”*

*}*

* get all users info:

request:

*GET **https://kuberdock.master**/api/users/all**response:*

if success user data

{

"result": “success”,

"data":

[{

"first_name": “John”,

"last_name": “Smith”,...},

{"first_name": “Jack”,

"last_name": “Doe”,...},

… }]

otherwise

{

"result": “error”,

"message": “...”

}

Capture billing data requests:

* get billable data by user

request:

GET *https://kuberdock.master*/api/usage/<username>

response:

array of user containers usage

*{ "data": {*

*	"ip_usage":[*

* {*

*"end": end_time,*

*"ip_address": “address_here”,*

*"pod_id": “pod_id”*

*"start": start_time*

*	}, …*

*	],*

*	"pd_usage": [*

*		{*

*		"end": end_time,*

*"pd_name": “persistent_drive_name”,*

*"size": “size”, // number in GB*

*"start": start_time*

*		}, …*

*	]*

*	"pods_usage": [*

*		{*

*		"id": “pod_id”,*

*"kube_id": “kube_id”,*

*"kubes": pod_kube_count,*

*"name" : “pod_name”,*

*"time": {*

*"id": [{ //container_id*

*"kubes": “conatainer_kube_count”,*

*"start": “timestamp”,*

*"end": “timestamp”,*

*}, {...}], // each time period*

*"id": [{...}],*

*… },*

*…},*

*"status": “OK”*

*}*

* get all billable data

request:

GET *https://kuberdock.master*/api/usage

response:

array of users and their container` usage

*"data":{*

*	"username":[{*

*"ip_usage":[*

* {*

*"end": end_time,*

*"ip_address": “address_here”,*

*"pod_id": “pod_id”*

*"start": start_time*

*	}, …*

*	],*

*	"pd_usage": [*

*		{*

*		"end": end_time,*

*"pd_name": “persistent_drive_name”,*

*"size": “size”, // number in GB*

*"start": start_time*

*		}, …*

*	]*

*	"pods_usage": [*

*		{*

*		"id": “pod_id”,*

*"kube_id": “kube_id”,*

*"kubes": pod_kube_count,*

*"name" : “pod_name”,*

*"time": {*

*"id": [{ //container_id*

*"kubes": “conatainer_kube_count”,*

*"start": “timestamp”,*

*"end": “timestamp”,*

*}, {...}], // each time period*

*"id": [{...}],*

*… },*

*…}],*

*"next_username":[{...}],*

*…},*

*"status": “OK”*

*}*

**Predefined application**

The logic of interaction between KuberDock and billing system, implemented to start predefined application, is as follows. 

When a user clicks Order now on Start predefined application page, he is redirected to the script specified in KuberDock settings (see Administration -> Predefined application section of the present manual). Script uses YAML-file of application with data specified by a user and the information that is needed for predefined application billing. 

For example in WHMCS:

*http://whmcs.cloudlinux.com/cart.php?yaml="data_from_YAML_here"*

*cart.php* script has to receive data from *yaml="data_from_YAML_here”* parameter and form invoice according to this data.

[Here ](#bookmark=id.fkc1bzaifkgp)is an example of YAML file which starts Wordpress and MySQL in one pod.

After purchase succeeded, a request for adding a user and starting predefined application should be sent to KuberDock. KuberDock WHMCS plugin will do it automatically, for other billing systems perform the following steps:

(Note that packages and Kube Types should be created in the billing system and in KuberDock according to the instructions for [package ](#bookmark=kix.vzxv4jlhbg1j)and Kube Type).

* Send request for creating a user according to the Requests for working with users section.

* Send request for creating a predefined application and save response to POD_ID request for the further work:

*POST /api/yamlapi*

arguments:

*'data' => data_from_YAML_file*

* Send request for acquiring user authorization token according to the[ instructions](#bookmark=kix.7i3pxe2fi00z). 

* Readdress user to the following link: 

http://kubedock.master?token=user_token&next=pods/POD_ID, where:

kuberdock.master - KuberDock master server domain or IP address;

user_token - acquired user authorization token;

pod_id - acquired ID of a created pod after adding a predefined application.

	**WHMCS integration**

1. Go to *[http://repo.cloudlinux.com/kuberdoc*k](http://repo.cloudlinux.com/kuberdock)* and *download the latest available plugin version. For example:

*whmcs-kuberdock-plugin-1.0.4.zip*

2. Unzip archive content into WHMCS root directory.

3. Go to WHMCS server console and synchronize time and date with KuberDock server by running a command:

*ntpdate pool.ntp.org*

You need to have NTPD installed to use this command. Use NTPD official documentation to install [https://www.eecis.udel.edu/~mills/ntp/html/index.html](https://www.eecis.udel.edu/~mills/ntp/html/index.html).

Note: if KuberDock and WHMCS will have more than 15 minutes time difference, then it will cause an error for KuberDock user that will try to buy an application in KuberDock.

4. To add KuberDock instance, go to *Setup*, find *Products/Services* section and choose *Servers*.

![image alt text](screenshot_part1/image_28.png)

Click *Add new server* and fill in the proper fields:

![image alt text](screenshot_part1/image_29.png)

4.1 In *Add server* section specify:

* Name - preferred KuberDock instance name;

* Hostname - leave blank;

* IP Address - KuberDock master-server IP address.

![image alt text](screenshot_part1/image_30.png)

4.2 In Server details section specify:

* Type -- choose *KuberDock* from drop-down menu;

* Username -- KuberDock master server administrator name;

* Password -- KuberDock master server administrator password.

![image alt text](screenshot_part1/image_31.png)

4.3 Click *Test Connection* button to check the validity of specified data. If you see *Successful!* message, then click *Save Changes*. If not, check your login and password accuracy.

4.4 Tick "Secure" checkbox to use secure https connection:

![image alt text](screenshot_part1/image_32.png)

5. To add a group of servers go to *Setup* section, choose *Products/Services* and choose *Servers*. Click *Create new **group*:

![image alt text](screenshot_part1/image_33.png)

5.1 In *Name* field enter *KuberDock*. 

Choose *Fill Type* by matching appropriate radio button - *Add to the list full server* or *Fill active server until full then switch to the next least used*.

In *Selected Servers* list choose a server that you just have added on the left side and click *Add*. When done click *Save changes*.

![image alt text](screenshot_part1/image_34.png)

 

6. Create Product Group. Go to *Setup* section, choose *Products/Services* and click *Create Group*. Enter the name of your group in *Product Group Name* field, choose *Use Specific Template *and tick KuberDock template from template list* *(or match your own template). When done, click *Save changes*.

![image alt text](screenshot_part1/image_35.png)

7.Activate KuberDock Addon plugin in WHMCS. Go to *Setup* section and choose *Addon modules*. Find KuberDock addon and click *Activate* in front of it.

![image alt text](screenshot_part1/image_36.png)

 Then click *Configure* and match *Full Administrator* checkbox. When done, click *Save changes*.

![image alt text](screenshot_part1/image_37.png)

8. Configure AutoAuth key in WHMCS to be used for single sign-on. You will need to add the following line to your WHMCS configuration.php file to define an AutoAuth key. The value just needs to be a random sequence of letters and numbers:

*$autoauthkey = "abcXYZ123";*

Please, read this WHMCS documentation to create key [http://docs.whmcs.com/AutoAuth](http://docs.whmcs.com/AutoAuth) and put in this field.

9. Restart your web-server (for example via command *systemctl httpd restart *in CentOS).

10. Go to KuberDock and login as admin. Go to Settings tab "Billing" and choose WHMCS in Select your billing system field. Then paste URL to WHMCS in Link to WHMCS field and add WHMCS admin credential to WHMCS admin username and WHMCS admin password fields. Finally, add AutoAuth key generated on Step 8 to the Secret key for Single sign-on field in Settings, section General.

![image alt text](screenshot_part1/image_38.png)

Now WHMCS installation is completed with default package "KuberDock package" (with three Kube Types included), which is already installed in KuberDock.

11. Set up currencies available for users when purchasing KuberDock packages.

Go to *Setup* section, choose *Payments *and click *Currencies*. Fill the proper fields in Add Additional Currency section and click Add Currency.

![image alt text](screenshot_part1/image_39.png)

You can add as much currencies as you need. Users will be able to choose currency when choosing a package.

Note that if you change default currency settings, then you need to edit each KuberDock product and just click Save changes button to apply currency changes for the KuberDock products.

Note that when Configuring Packages and Configure Kube Types WHMCS default currency is used. To check which currency is default in Setting section choose Payments and click on Currencies - the one that doesn't contain delete icon in the end of the line is default:

![image alt text](screenshot_part1/image_40.png)

12. Go to Setup section, choose Automation Settings. Tick the checkboxes "Enable Suspension" and “Enable termination” and specify the number of days after which KuberDock must suspend or terminate users` application. It is important to setup this section otherwise KuberDock will not terminate and suspend users pods after due date.

![image alt text](screenshot_part1/image_41.png)

The KuberDock will do the following actions if suspend is needed:

* For PAYG packages

If a user doesn't pay for the Pod after one day/or for the next month:

1. User status in KuberDock become 'suspended'.

2. Users` pod status become stopped with inability to start it.

3. WHMCS product status become 'suspended'.

* For Fixed Price package

If user doesn't pay for Pod on first day/or for the next month:

1. Pod status become unpaid (means stopped) with inability to start it.

Also, tick proper checkboxes to let WHMCS send email notification to the user according to described cases.

![image alt text](screenshot_part1/image_42.png)

		

That`s all you need to configure WHMCS integration with KuberDock. Now you should also set up resource limits, package prices (check step 3 of [Configure Packages](#bookmark=kix.5v2qu297pktq) section) and price for each Kube Type (check step 2 in [Configure Kube Types](#bookmark=kix.bg64es9c3bt3) section). 

You can also create additional packages and add Kube Types to them, to enable users purchase KuberDock.

Note that you need to set up payments gateway in WHMCS according to their [documentation](http://docs.whmcs.com/Payment_Gateways).

**Update WHMCS addon**

To update WHMCS addon perform the following steps:

* This steps is only for plugin version before 1.0.6.3 (you can find current version in whmcs in Setup -> Addon Modules):

    * Download the latest version of KuberDock plugin for WHMCS from our repository:

[http://repo.cloudlinux.com/kuberdock](http://repo.cloudlinux.com/kuberdock/whmcs-kuberdock-plugin-1.0.7.zip)

    * Unzip KuberDock plugin to WHMCS root directory.

    * Run script:

*php <whmcs_root>/deploy.php --migrate*

* For plugin version 1.0.6.3 and later perform the following steps:

Run script:

*php <whmcs_root>/deploy.php*

The script will download the latest version of KuberDock plugin to current directory and upgrade it to the latest version.

Available options:

*--help, -h*

print this help

*--user, -u*

change owner of downloaded files. For example:

*php deploy.php --user=whmcs:whmcs*

Use this option only if you have write permissions.

**Configure Packages**

1. Go to *Setup* section, choose *Products/Services* and click on *Create a New Product*.

![image alt text](screenshot_part1/image_43.png)

Enter the following information:

* Product Type -- choose *Other Products/Services*;

* Product Group -- choose product group that you have created before plugin activation on step 4 of [WHMCS installation guide](#bookmark=kix.g6e7yl8938ix) section;

* Product Name -- enter your [package](#bookmark=id.ps8hx5kfq0bk) name, this name will be displayed to a user in WHMCS.

When done, click *Continue*.

![image alt text](screenshot_part1/image_44.png)

2. Choose *Module Settings* tab:

Note. When setting price for a package, default WHMCS currency is used.

* In *Server Group* field choose a server group created for KuberDock.

![image alt text](screenshot_part1/image_45.png)

* In *Service payment type* field choose proper billing period: "hourly", “monthly”, “quarterly”, “annual”  - resource usage statistic will be collected every selected period.

* In *Billing type* choose which billing behavior you need between PAYG and Fixed price:

    * PAYG -- user can start it`s pod or application without immediately pay for it, but as soon as WHMCS get statistic data (each 24 hours).

    * Fixed price -- user needs to pay and then use it`s pod or application.

* Match *Debug Mode *checkbox to trace errors in API responds. To view this log in WHMCS go to *Utility *section, choose *Logs*, then choose *Module log*.

* Next step you should specify prices in package:

Important note: at least one of the prices should me more than zero price otherwise invoices will not be sent.

    * In *First deposit* field specify the sum of money a user should pay to start using KuberDock. If there is first deposit in case of PAYG than auto-setup will be automatically set to "Automatically setup the product as soon as the first payment is received" after saving the package.

![image alt text](screenshot_part1/image_46.png)

    * In* Price for IP* field specify the Public IP usage cost.

    * In *Price for persistent storage* field specify persistent storage usage cost. 

    * In *Price for additional traffic* field specify the cost of traffic (**traffic count will be added soon**).

* In case you need to restrict a user to create pods in KuberDock User Interface match checkbox *Restricted users*.

![image alt text](screenshot_part1/image_47.png)

* If you need to create a package with trial period, then match *Trial package* checkbox and specify the number of days for trial period in *User Free Trial period* field. Kube Types for such package will be limited to maximum 10 Kubes per user account (more about limits for Trial user [here](#bookmark=id.t65hbz2rfrts)).

    * Follow [WHMCS documentation](http://docs.whmcs.com/Products_Management#Upgrades.2FDowngrades) to configure upgrade process from Trial package. This will allow users to upgrade their KuberDock Trial package to other packages you need. For manual change of users package use the same documentation section "Manual Upgrades".

Please note, after Trial period ends a user will be suspended and pods will be stopped without ability to run them. As soon as package will be upgraded, then in KuberDock User Role (read more about User Roles [here](#)) Trial User will be switched to User and in case of PAYG package his pods will run, in case of Fixed Price his pods become unpaid and will not run until payment will be received.

1. If Users trial period expired, thеn this user in KuberDock will be also suspended with all its pods and applications. After package will be upgraded, than users product in WHMCS will be changed to Standard package (or the package, [configured ](http://docs.whmcs.com/Products_Management#Upgrades.2FDowngrades)in the trial package).

You can also set up periodic notification for cases:

1. *Trial period ending notice repeat* - how often WHMCS should send email with notification about trial period expiration. Enter a number of days before expiration you want to send notice to the user. Note that "0" means not to send such notice at all.

2. *Trial period expired notice *- tick checkbox if you need to send notice that trial period has expired, otherwise leave it unchecked.

![image alt text](screenshot_part1/image_48.png)

			

3. This step is only required for WHMCS version 6.3.1 and higher. Since version 6.3.1 WHMCS does not send invoices to customers for packages with setting Payment Type *Free* in *Pricing *tab. As a temporary solution set *One time* option with zero price:

![image alt text](screenshot_part1/image_49.png)

After KuberDock addon activation, KuberDock default package Standard packages will obtain this option automatically by default.

4. When done, click *Save changes* - the information on this package will be submitted to KuberDock at once. Note that when a package is updated, the information is submitted to KuberDock by API right after clicking *Save changes*.

All the packages created for KuberDock are available in *KuberDock addons* section on *Addons* page, where you can configure Kube Types for them.

Note that if a package has not been added to KuberDock  for some reason (API error, connection error etc.), then you will see the following message in Packages list: "*Package not found*".

![image alt text](screenshot_part1/image_50.png)

In this case you should check WHMCS logs - go to *Utilities*, choose *Logs*, then choose *Module logs*.
**Configure Kube Types**

To create Kube Types, go to *Addons* menu and choose *KuberDock Addons*. On this page all the KuberDock packages with all Kube Types are displayed.

1. Click *Add Kube Type* on the right:

![image alt text](screenshot_part1/image_51.png)

2. Specify all the necessary information according to the instruction:

Note that when setting prices for Kube Types, default WHMCS currency is used.

* Server - choose server where this kube type will be used

* Kube Type name - new Kube Type name, which will be displayed to a user in WHMCS and KuberDock interface.

* CPU limits (%) -- core percentage allocated to one Kube. E.g. 0.1 means 10% of a CPU core; 1.5 means 100% of one core and 50% of another.

* Memory limits (MB) → RAM capacity for one Kube.

* HDD limits (GB) → disc space allocated for one Kube

* Traffic limit (GB) → traffic volume included in one Kube (**under development**).

![image alt text](screenshot_part1/image_52.png)

3. Click *Add* to create Kube Type with all specified parameters. Each Kube Type is created on KuberDock remote server with API query and record in local WHMCS database. Kube Type parameters are used to calculate resource usage for packages.

4. Add all the necessary Kube Types and click  *Pricing* tab, where you can set the price per one Kube for each Kube Type.

![image alt text](screenshot_part1/image_53.png)

All packages will be displayed in a table below. Note that packages are grouped by Billing type for the price setting convenience.

Click "Active" checkbox(1) to enable “Price” field(2) to enter price for Kube Type. This checkbox allows to enable or disable Kube Type in the package. If it is unchecked then this Kube Type will be not available in the package and in KuberDock for users with that package. If it is checked then price must be entered and Kube Type will be available in KuberDock for users with that package.

![image alt text](screenshot_part1/image_54.png)

In *Price *field specify price for one Kube. Price type depends on settings of the chosen Package in KuberDock package column. For example, if you have *Standard package* with *monthly* billing type in its settings, then in Price field a price per month must be set.

When done, click *Save* to save specified price and submit your settings to KuberDock, or click Cancel.

![image alt text](screenshot_part1/image_55.png)

Note that you can remove Kube Type only if it is not used in any package.

You can track price changes log in *Changes log* tab:

Login - username, which made changes;

Time - time the changes were made;

Description - changes details.

![image alt text](screenshot_part1/image_56.png)

**Managing clients**

To control clients' statuses go to *Clients* section and choose *View/Search clients*.

1. Click on proper client's ID (alternatively Last name or First name) from the list to get to his/her page.

2. Go to *Products/Services* tab, in *Products* section choose KuberDock package (only purchased packages are available).![image alt text](screenshot_part1/image_57.png)

3. To change user’s status use the following buttons:

* *Create* - this action is disabled for KuberDock;

* *Suspend* - to suspend a user an attribute "suspended" = true is set. All user's services will be stopped, user will not be able to create new containers.

* *Unsuspend* - to unsuspend a user an attribute "suspended" = false is set. All user's services start working, user can create and run new containers.

* *Terminate* - to lock an account and give attribute "active" value false.  User will not be able to access KuberDock.

When done, confirm your actions by clicking *Yes* in pop-up - the data will be submitted to KuberDock.

![image alt text](screenshot_part1/image_58.png)

To change password for a user in KuberDock, perform the following steps:

1. Enter new password in appropriate field:![image alt text](screenshot_part1/image_59.png)

2. Click *Save Changes* below and new data will be submitted to KuberDock.

To delete a package and a user in KuberDock, click Delete:

![image alt text](screenshot_part1/image_60.png)

To log in to KuberDock as a user click Log in to KuberDock:

![image alt text](screenshot_part1/image_61.png)

**Shared hosting panels integration**

**Requirements:**

KuberDock nodes must be able to create IPIP tunnel to shared hosting panel server.

The documentation on shared hosting panels plugins setup and use is available for:

* [cPanel](#bookmark=kix.yz0di4zcl8k7)

* [Plesk](#bookmark=kix.jtt6d6rgog5g)

* [DirectAdmin](#bookmark=kix.xpgd2achv91y)

To update your plugin for shared hosting panels use [this instruction](#bookmark=kix.x9fltutjjyk2).

**cPanel**

**To set up KuberDock plugin in cPanel **perform the following steps:

*We strongly recommend to read **[requirement for shared hosting panel server*s](#bookmark=kix.5y33yfrxm50v)*.*

*Note that current plugin for cPanel works with CentOS 6** **or higher.*

If you need to update KuberDock plugin then follow [KuberDock plugin update instructions](#bookmark=kix.d9sjhxwzilj6).

1. Go to Service Configuration, choose Apache configuration and click Include Editor. In Pre Main Include section choose All Versions from drop-down menu. In text editor start new line and add *ProxyPreserveHost On* directive, and click Update. This a mandatory step if you need to use proxy. You can learn more about proxy in [YAML specification](#bookmark=id.fkc1bzaifkgp).

![image alt text](screenshot_part1/image_62.png)

On the next page click Restart Apache to make changes take effect.

![image alt text](screenshot_part1/image_63.png)

2. Log in to cPanel server console as root, download and install release package:

*wget  **[http://repo.cloudlinux.com/kuberdock-client/kcli-deploy.s*h](http://repo.cloudlinux.com/kuberdock-client/kcli-deploy.sh)

*bash ./kcli-deploy.sh*

3. During installation, enter KuberDock master server address and admin credentials:

*Enter KuberDock host name or IP address:*

*Enter KuberDock admin username:*

*Enter KuberDock admin password:*

Note that you can change these settings in cPanel section. Go to Plugin, choose KuberDock tab and Edit kubecli.conf

![image alt text](screenshot_part1/image_64.png)

4. This step is needed only if cPanel works through WHMCS. Set up connection to WHMCS API using guide in section [Set up cPanel server in WHMCS](#bookmark=id.h0eq55snne31).

 

Note that if you had to redeploy KuberDock with cPanel previously set on it, then after redeploy, run the following command on cPanel server under root:

*/usr/share/kuberdock-plugin/install_kuberdock_plugins.sh -u*

This command will remove all nonexistent templates and icons from user interface for KuberDock and cPanel correct interaction.

**Configure cPanel to work with WHMCS**

To add KuberDock plugin for cPanel you should add cPanel server to WHMCS and add the package. Perform the following steps:

1. Go to *Setup*, find *Products/Services* section and choose *Servers*. Click *Add new server* and fill in the proper fields:

![image alt text](screenshot_part1/image_65.png)

In *Add server *section specify:

* Name -- cPanel instance name;

* Hostname -- leave blank;

* IP Address -- IP address where cPanel is located.

![image alt text](screenshot_part1/image_66.png)

In *Server details* section specify:

* Type - choose cPanel from drop-down menu;

* Username - cPanel server username with permission to create/delete users;

* Password - cPanel server password with permission to create/delete users.

![image alt text](screenshot_part1/image_67.png)

2. Then add a group of servers. Go to *Setup* section, choose *Products/Services* and choose *Servers*. Click *Create new **group*:

![image alt text](screenshot_part1/image_68.png)

In *Name* field specify cPanel. In *Selected Servers* list on the left choose a server that you just have added and click *Add* (in the given example, server name is cPanel). When done, click *Save changes*.

![image alt text](screenshot_part1/image_69.png)

3. Go to *Setup* section, choose *General Settings* and click on *Security* tab. In *API IP Access Restriction *section click *Add IP*, in pop-up specify cPanel server IP address to locate cPanel KuberDock addon, and click *Add IP*. Now the access to WHMCS API from cPanel must be provided.

![image alt text](screenshot_part1/image_70.png)

When done click *Save Changes*.

4. cPanel server setup in WHMCS is now completed. Configured Packages and [Kube Types](#bookmark=kix.k0vfh3mcl1if) are available for customers to allocate resources for their applications in cPanel.

**Set up predefined applications**

To manage predefined applications, log in to cPanel as admin and perform the following steps:

Note. Before Predefined application setup, choose Application defaults tab and choose proper Default package and Default Kube Type from the corresponding drop-down to use by default, if YAML file does not contain this parameters. Current Default package and Default Kube Type are displayed above in brackets.. When done click Save.

![image alt text](screenshot_part1/image_71.png)

1. In Plugins section choose KuberDock and click Add new application tab:

![image alt text](screenshot_part1/image_72.png)

2. Upload YAML. Click *Browse...* to choose proper file and then click *Upload YAML*. You can use ready-to-use YAML files from our github repository ([https://github.com/cloudlinux/kuberdock_predefined_apps](https://github.com/cloudlinux/kd_predefined_apps)). YAML file data will be displayed below in a separate section.

![image alt text](screenshot_part1/image_73.png)

3. Add application name to be displayed for users:

![image alt text](screenshot_part1/image_74.png)

4. Edit YAML if needed. Please check [YAML specification](#bookmark=id.fkc1bzaifkgp) before making changes.

5. When setup complete, click Add application:

![image alt text](screenshot_part1/image_75.png)

**cPanel user guide**

Start predefined application

The icons of predefined applications that can be started in few clicks are displayed in KuberDock Apps section. Click on an icon of the application that you want to start:

![image alt text](screenshot_part1/image_76.png)

Choose the most suitable plan for your application:

![image alt text](screenshot_part1/image_77.png)

Click Show details under the package to show resources that will be allocated to your application according to each plan. Click Choose plan to proceed to the next step. Depending on application type you will need to specify different data for it to start on the next step. It can be user and password, domain or subdomain to use, etc. For example, this is a second step of Wordpress application:

* Select application domains - you can select one of your domain to be used for this application (for example, *your.domain/wordpress*)

* Enter your application name - enter the name of application to be displayed in all your applications list.

Click* Pay and Start your App *to start application or click "Choose different package" to change package.

![image alt text](screenshot_part1/image_78.png)

If payment successfully proceeded then you will be redirected to application page.

The main information on resources and settings is displayed on the application page :

* Your application information is displayed on pale green area of the page.This text will be different for the different applications:

![image alt text](screenshot_part1/image_79.png)

* MySql & phpMyAdmin - the name of the application with resources information below.

* Host - application IP address or service address available from the internet. If no IP assigned - none.

* Status - your application current status:

    * Running - the application is started and running;

    * Pending - the application is starting or stopping;

    * Stopped - the application is stopped.

* Actions - application control buttons:

    * Stop/Start - start or stop application (changes depending on application status);

    * Edit - open KuberDock page with your application (see [Managing pods](#bookmark=id.oxq4h1tmou6h) for details).

    * Delete - delete application (the application will be no more available and removed from cPanel). 

    * Restart - restart application with 2 options: Wipe Our data and get fresh application, or Just Restart. After clicking on the proper button you will get pop-up where you can choose what exactly you want to do.

![image alt text](screenshot_part1/image_80.png)

* In the bottom of the page application cost is displayed

![image alt text](screenshot_part1/image_81.png)

* *Upgrade *button allows you to change Kubes quantity. After clicking on the button you will be redirected to the Upgrade page. Use slider to change Kube number for each part of your application. In the bottom of the page you will see the changes of total amount of resources and new price for your application.

![image alt text](screenshot_part1/image_82.png)

Set up custom applications

KuberDock allows cPanel end user to run many custom containerized applications  (nginx, apache, redis, elasticsearch, etc...) in just few clicks.

To start the application:

1. In cPanel UI go to KuberDock Apps section and click on "More Apps":

![image alt text](screenshot_part1/image_83.png)

2. You can choose an applications that can be started in few clicks from the list above:

![image alt text](screenshot_part1/image_84.png)

Or enter application name (or part of) in *Search for app* line and click Search to search for available applications:

![image alt text](screenshot_part1/image_85.png)

3. Choose proper application and click Install in front of it to begin installation or More details to view application description:

![image alt text](screenshot_part1/image_86.png)

4. Select Kube Type and [Kube](#bookmark=kix.updlgo6yxca4) number to specify the amount of resources used to run this application. In the right section of the screen you will see the total resource levels that will be allocated for the application.

![image alt text](screenshot_part1/image_87.png)

5. In Ports section change ports if needed. Host port is external port of a container used to access container port from external IP or from other ports. By default *Host port* equals *Container port*. To provide external IP tick Public checkbox in front of proper port. Use the following addresses to access the container:

* from other applications: *pod_ip:pod_port*

* from external IP: *public_ip:pod_port*.

* from containers within same pod: 127.0.01:pod_port

![image alt text](screenshot_part1/image_88.png)

6. In Environment variables section change variables if needed. Click Learn more about this application to go to this application image description page in Docker Hub Registry. Here you can find all the necessary information on  this application variables.

![image alt text](screenshot_part1/image_89.png)

7. To add a volume click *Add volume* and specify its location path in *Container path* field. Mark *Persistent* checkbox to mark a volume as persistent (would persist when container is restarted or moved to another server). In contrast to the local volume, data in persistent volume will be saved after container is restarted or even removed.

![image alt text](screenshot_part1/image_90.png)

8. In the bottom you will see price per one hour of this application running. The price depends on amount of resources (Kube Type & size). Click *Start your App* to start the application and go to Apps section.

![image alt text](screenshot_part1/image_91.png)

Your application will start within a few minutes - its status will change to "running".

![image alt text](screenshot_part1/image_92.png)

Manage your applications

In KuberDock Apps choose My Apps - you will get to cPanel page with all running applications displayed.

![image alt text](screenshot_part1/image_93.png)

The information on current applications’ statuses is displayed in Application table. You can start, stop or remove an application in Actions section. Click Edit, to go to KuberDock and control this application.

![image alt text](screenshot_part1/image_94.png)

The application that was not payed successfully will be also displayed in this list. You will be able to click "Pay and Start" to pay for application and start it normally.

![image alt text](screenshot_part1/image_95.png)

Click on the application name to view detailed information:

1. Allocated resources and control buttons:

* Limits - resources allocated for this application;

* Public IP - application IP address available from the internet. If no IP assigned - none.

* Status - your application current status:

Running - the application is started and running;

Pending - the application is starting or stopping;

Stopped - the application is stopped.

* Actions - application control buttons:

Stop/Start - start or stop application (changes depending on application status);

Edit - open KuberDock page with your application (see [Managing pods](#bookmark=id.oxq4h1tmou6h) for details).

Delete - delete application (the application will be no longer available and removed from cPanel). Note that after deleting Public IP and Persistent drive, applications will not be removed automatically and the fees will still be processing. If you are not going to use them anymore, remove [Persistent drive](#bookmark=id.bmm5foek49hg) and [Public IP](#bookmark=id.pem6upya7tjt)  from KuberDock manually.

![image alt text](screenshot_part1/image_96.png)

2. In Ports section the information on running container is displayed.

Here you can view all the ports with their settings shown in the table:

* Container’s port - container’s internal port;

* Protocol - data transmission protocol (udp or tcp);

* Host port - is external port of a container used to access container port from using external IP or from other ports.

* Public - if the port is available from the Internet, then checkbox will be ticked, otherwise no.

![image alt text](screenshot_part1/image_97.png)

3. *Volumes* section displays all added volumes and their parameters specified for container when creating:

* Persistent - means that this is a persistent volume, that will persist through container restarts & removal

* Name - persistent volume name;

* Size - persistent storage disc space capacity in MB. 

![image alt text](screenshot_part1/image_98.png)

4. In *Environment variables*  section all the variables names and values are displayed in the list. 

![image alt text](screenshot_part1/image_99.png)

5. Pricing - the price for application based on Kube Type and the number of Kubes.

![image alt text](screenshot_part1/image_100.png)

If you need to add one more application, click Add more apps.

**Plesk**

**	KuberDock plugin installation**

To** Set up KuberDock plugin in Plesk **perform the following steps:

*We strongly recommend to read **[requirement for shared hosting panel server*s](#bookmark=kix.5y33yfrxm50v)*.*

*Note that current plugin for Plesk works with CentOS 6** **or higher.*

If you need to update KuberDock plugin then follow [KuberDock plugin update instructions](#bookmark=id.doztgas0vszv).

1. This is a mandatory step if you need to use proxy. You can learn more about proxy in [YAML specification](#bookmark=id.fkc1bzaifkgp). Login to Plesk server as a root and add directive *ProxyPreserveHost On** *to the file */etc/httpd/conf/httpd.conf* and run command:

		*service httpd restart*

2. Download and install KuberDock plugin by running the commands:

*wget  **[http://repo.cloudlinux.com/kuberdock-client/kcli-deploy.s*h](http://repo.cloudlinux.com/kuberdock-client/kcli-deploy.sh)

*bash ./kcli-deploy.sh*

3. During installation, enter KuberDock master server address and admin credentials:

*Enter KuberDock host name or IP address:*

*Enter KuberDock admin username:*

*Enter KuberDock admin password:*

Note that you can change these settings in Plesk administration panel. Go to Extensions, choose Module KuberDock and click tab  *Edit kubecli.conf*

![image alt text](screenshot_part1/image_101.png)

Your KuberDock plugin is ready to use now. Learn how to add Predefined Application and configure default Kube Type and Package.

 

**Configuring Plesk to work with WHMCS**

To configure Plesk and WHMCS please check WHMCS [official Plesk documentation section ](http://docs.whmcs.com/Plesk)with step by step instruction.

**Set up predefined applications**

To manage predefined applications, log in to Plesk as admin and perform the following steps:

Note. Before Predefined application setup, go to Application defaults tab and choose proper Default package and Default Kube Type from the corresponding drop-down to use by default, if YAML file does not contain this parameters. Current Default package and Default Kube Type are displayed above in brackets. When done click Save.

![image alt text](screenshot_part1/image_102.png)

1. In KuberDock Existing apps section click Add new application button:

![image alt text](screenshot_part1/image_103.png)

2. Upload YAML. Click *Browse...* to choose proper file and then click *Upload YAML*. You can use ready-to-use YAML files from our github repository ([https://github.com/cloudlinux/kuberdock_predefined_apps](https://github.com/cloudlinux/kd_predefined_apps)). YAML file data will be displayed below in a separate section.

![image alt text](screenshot_part1/image_104.png)

3. Add application name to be displayed for users:

![image alt text](screenshot_part1/image_105.png)

4. Edit YAML if needed. Please check [YAML specification](#bookmark=id.fkc1bzaifkgp) before making changes.

5. When setup complete, click Save application:

         ![image alt text](screenshot_part1/image_106.png) 

**Plesk User Guide**

	**Start predefined application**

Available predefined applications are displayed in KuberDock Apps page Applications tab. Click on an icon of the application  that you want to start:

![image alt text](screenshot_part1/image_107.png)

Choose the most suitable plan for your application:

![image alt text](screenshot_part1/image_108.png)

Click *Show details *under the package to show resources that will be allocated to your application according to each plan. Click *Choose plan* to proceed to the next step. Depending on application type you will need to specify different data for it to start on the next step. It can be user and password, domain or subdomain to use, etc. For example, this is the second step of Wordpress application:

* Select application domains - you can select one of your domains to be used for this application (for example, *your.domain/wordpress*)

* Enter your application name - enter the name of application to be displayed in all your applications list.

Click* Pay and Start your App *to start application or click "Choose different package" to change package.

![image alt text](screenshot_part1/image_109.png)

If payment proceeded successfully you will be redirected to application page.

The main information on resources and settings is displayed on the application page :

* Your application information is displayed on pale green area of the page.This text will be different for the different applications:

![image alt text](screenshot_part1/image_110.png)

* MySql & phpMyAdmin - the name of the application with resources information below.

* None - application IP address or service address available from the internet. *None *if nothing is assigned.

* Status - your application current status:

    * Running - the application is started and running;

    * Pending - the application is starting or stopping;

    * Stopped - the application is stopped.

* Actions - application control buttons:

    * Stop/Start - start or stop application (changes depending on application status);

    * Edit - open KuberDock page with your application (see [Managing pods](#bookmark=id.oxq4h1tmou6h) for details).

    * Delete - delete application (the application will be no more available and removed from Plesk). 

    * Restart - restart application with 2 options: Wipe Out data and get fresh application, or Just Restart. After clicking on the proper button you will get pop-up where you can choose what exactly you want to do.

![image alt text](screenshot_part1/image_111.png)

* In the bottom of the page application cost is displayed

![image alt text](screenshot_part1/image_112.png)

* You can change Kubes quantity using *Upgrade *button. After clicking on the button you will be redirected to the Upgrade page. Use slider to change Kube number for each part of your application. In the bottom of the page you will see the changes of total amount of resources and new price for your application.

![image alt text](screenshot_part1/image_113.png)

**Set up custom application**

To run custom application in Plesk follow next steps:

1. In Plesk UI go to KuberDock Apps section and click "Create custom application":![image alt text](screenshot_part1/image_114.png)

2. You can choose an applications that can be started in few clicks from the list above:![image alt text](screenshot_part1/image_115.png)Or enter application name (or part of) in *Search for app* line and click Search to search for available applications:

![image alt text](screenshot_part1/image_116.png)

3. Choose proper application and click Install in front of it to begin installation or More details to view application description:

![image alt text](screenshot_part1/image_117.png)

4. Select [Kube Type](#bookmark=kix.k0vfh3mcl1if) and [Kube](#bookmark=kix.updlgo6yxca4) number to specify the amount of resources used to run this application. In the right section of the screen you will see the total resource levels that will be allocated for the application.

![image alt text](screenshot_part1/image_118.png)

5. In Ports section change ports if needed. Host port is external port of a container used to access container port from external IP or from other ports. By default *Host port* equals *Container port*. To provide external IP tick Public checkbox in front of proper port. Use the following addresses to access the container:

* from other applications: *pod_ip:pod_port*

* from external IP: *public_ip:pod_port*.

* from containers within same pod: *127.0.01:pod_port*

![image alt text](screenshot_part1/image_119.png)

6. You can change variables in Environment variables section if needed. Click Learn more about this application to go to this application image description page in Docker Hub Registry. Here you can find all the necessary information on  this application variables.![image alt text](screenshot_part1/image_120.png)

7. To add a volume click *Add volume* and specify its location path in *Container path* field. Tick *Persistent* checkbox to mark a volume as persistent (would persist when container is restarted or moved to another server). In contrast to the local volume, data in persistent volume will be saved after container is restarted or even removed.![image alt text](screenshot_part1/image_121.png)

8. In the bottom you will see price per one hour of this application running. The price depends on amount of resources (Kube Type & size). Click *Start your App* to start the application and go to Apps section.

![image alt text](screenshot_part1/image_122.png)

Your application will start within a few minutes - its status will change to "running".

![image alt text](screenshot_part1/image_123.png)

**Managing applications**

In KuberDock Apps choose My Apps - you will get to page with all running applications displayed.

![image alt text](screenshot_part1/image_124.png)

The information on current applications’ statuses is displayed in Application table. You can start, stop or remove an application in Actions section. Click Edit, to go to KuberDock and control this application.

![image alt text](screenshot_part1/image_125.png)

The application that was not payed successfully will be also displayed in this list. You will be able to click "Pay and Start" to pay for application and start it normally.

Click on the application name to view detailed information:

1. Allocated resources and control buttons:

* Limits - resources allocated for this application;

* Public IP - application IP address available from the internet. If no IP assigned - none.

* Status - your application current status:

Running - the application is started and running;

Pending - the application is starting or stopping;

Stopped - the application is stopped.

* Actions - application control buttons:

Stop/Start - start or stop application (changes depending on application status);

Edit - open KuberDock page with your application (see [Managing pods](#bookmark=id.oxq4h1tmou6h) for details).

Delete - delete application (the application will be no longer available and removed from cPanel). Note that after deleting Public IP and Persistent drive, applications will not be removed automatically and the fees will still be processing. If you are not going to use them anymore, remove [Persistent drive](#bookmark=id.bmm5foek49hg) and [Public IP](#bookmark=id.pem6upya7tjt)  from KuberDock manually.

![image alt text](screenshot_part1/image_126.png)

2. In Ports section the information on running container is displayed.

Here you can view all the ports with their settings shown in the table:

* Container’s port - container’s internal port;

* Protocol - data transmission protocol (udp or tcp);

* Host port - is external port of a container used to access container port from using external IP or from other ports.

* Public - if the port is available from the Internet, then checkbox will be ticked, otherwise no.

![image alt text](screenshot_part1/image_127.png)

3. *Volumes* section displays all added volumes and their parameters specified for container when creating:

* Persistent - means that this is a persistent volume, that will persist through container restarts & removal

* Name - persistent volume name;

* Size - persistent storage disc space capacity in MB. 

![image alt text](screenshot_part1/image_128.png)

4. In *Environment variables*  section all the variables names and values are displayed in the list. 

![image alt text](screenshot_part1/image_129.png)

5. Pricing - the price for application based on Kube Type and the number of Kubes.

![image alt text](screenshot_part1/image_130.png)

If you need to add one more application, click Add more apps.

**DirectAdmin**

**KuberDock plugin installation**

To** Set up KuberDock plugin in DirectAdmin **perform the following steps:

*We strongly recommend to read **[requirement for shared hosting panel server*s](#bookmark=kix.5y33yfrxm50v)*.*

*Note that current plugin for DirectAdmin works with CentOS 6** **or higher.*

If you need to update KuberDock plugin then follow [KuberDock plugin update instructions](#bookmark=id.doztgas0vszv).

1. This is a mandatory step if you need to use proxy. You can learn more about proxy in [YAML specification](#bookmark=id.fkc1bzaifkgp). Login to DirectAdmin server as a root and add directive *ProxyPreserveHost On** *to the file */etc/httpd/conf/httpd.conf* and run command:

		*service httpd restart*

2. Download and install KuberDock plugin by running the commands:

*wget  **[http://repo.cloudlinux.com/kuberdock-client/kcli-deploy.s*h](http://repo.cloudlinux.com/kuberdock-client/kcli-deploy.sh)

*bash ./kcli-deploy.sh*

3. During installation, enter KuberDock master server address and admin credentials:

*Enter KuberDock host name or IP address:*

*Enter KuberDock admin username:*

*Enter KuberDock admin password:*

Note that you can change these settings in DirectAdmin administration panel. Go to Home page and in section Extra Features click KuberDock, then click tab  *Edit kubecli.conf* and on this page you can change credentials for connection with KuberDock:

![image alt text](screenshot_part1/image_131.png)

**Configuring DirectAdmin to work with WHMCS**

To configure DirectAdmin and WHMCS please check WHMCS [official documentation section ](http://docs.whmcs.com/DirectAdmin)with step by step instructions.

**Set up predefined applications**

To manage predefined applications, log in to DirectAdmin as an admin and perform the following steps:

Note. Before Predefined application setup, go to KuberDock page Application defaults tab and choose proper Default package and Default Kube Type from the corresponding drop-down to use by default, if one of the YAML file does not contain this parameters. Current Default package and Default Kube Type are displayed above in brackets. When done click Save.

![image alt text](screenshot_part1/image_132.png)

6. In KuberDock Existing apps tab click Add app button:

![image alt text](screenshot_part1/image_133.png)

7. Upload YAML. Click* Upload YAML * to choose proper file. You can use ready-to-use YAML files from our github repository ([https://github.com/cloudlinux/kuberdock_predefined_apps](https://github.com/cloudlinux/kd_predefined_apps)). YAML file data will be displayed below in a separate section.

![image alt text](screenshot_part1/image_134.png)

8. Add application name to be displayed for users:

![image alt text](screenshot_part1/image_135.png)

9. Edit YAML if needed. Please check [YAML specification](#bookmark=id.fkc1bzaifkgp) before making changes.

10. When setup complete, click Add application:

         ![image alt text](screenshot_part1/image_136.png)

Predefined application successfully added to DirectAdmin. You can now see all added Predefined application in tab Existing apps:

![image alt text](screenshot_part1/image_137.png)

**DirectAdmin user guide**

**Start predefined applications**

Available predefined applications are displayed in Advanced Features block, page KuberDock, Applications tab. Click on an icon of the application  that you want to start:

![image alt text](screenshot_part1/image_138.png)

Choose the most suitable plan for your application and click Choose package:

![image alt text](screenshot_part1/image_139.png)

Click *Show details *under the package to show resources that will be allocated to your application according to each plan. Click *Choose package* to proceed to the next step. Depending on application type you will need to specify different data for it to start on the next step. It can be user and password, domain or subdomain to use, etc. For example, this is the second step of Joomla application:

* Select application domains - you can select one of your domain to be used for this application (for example, *your.domain/joomla*)

* Enter your application name - enter the name of application to be displayed in all your applications list.

Click* Pay and Start your App *to start application or click "Choose different package" to change package.

![image alt text](screenshot_part1/image_140.png)

If payment proceeded successfully you will be redirected to application page otherwise to the billing page.

The main information on resources and settings is displayed on the application page :

* Your application information is displayed on pale green area of the page.This text will be different for the different applications:

![image alt text](screenshot_part1/image_141.png)

* MySql & phpMyAdmin - the name of the application with resources information below.

* Host - application IP address or service address available from the internet. If no IP assigned - none.

* Status - your application current status:

    * Running - the application is started and running;

    * Pending - the application is starting or stopping;

    * Stopped - the application is stopped.

* Actions - application control buttons:

    * Stop/Start - start or stop application (changes depending on application status);

    * Edit - open KuberDock page with your application (see [Managing pods](#bookmark=id.oxq4h1tmou6h) for details).

    * Delete - delete application (the application will be no more available and removed from Direct Admin). 

    * Restart - restart application with 2 options: Wipe Out data and get fresh application, or Just Restart. After clicking on the proper button you will get pop-up where you can choose what exactly you want to do.

![image alt text](screenshot_part1/image_142.png)

* In the bottom of the page application cost is displayed

![image alt text](screenshot_part1/image_143.png)

You can change Kubes quantity using *Upgrade *button. After clicking on the button you will be redirected to the Upgrade page. Use slider to change Kube number for each part of your application. In the bottom of the page you will see the changes of total amount of resources and new price for your application.

![image alt text](screenshot_part1/image_144.png)

**Set up custom application**

To run custom application in DirectAdmin perform the following steps:

1. In DirectAdmin go to KuberDock section and click "Create custom application":![image alt text](screenshot_part1/image_145.png)

2. You can choose an applications that can be started in few clicks from the list above:![image alt text](screenshot_part1/image_146.png)Or enter application name (or part of) in *Search for app* line and click Search to search for available applications:

![image alt text](screenshot_part1/image_147.png)

3. Choose proper application and click Install in front of it to begin installation or More details to view application description:

![image alt text](screenshot_part1/image_148.png)

4. Select [Kube Type](#bookmark=kix.k0vfh3mcl1if) and [Kube](#bookmark=kix.updlgo6yxca4) number to specify the amount of resources used to run this application. In the right section of the screen you will see the total resource levels that will be allocated for the application.

![image alt text](screenshot_part1/image_149.png)

5. In Ports section change ports if needed. Host port is external port of a container used to access container port from external IP or from other ports. By default *Host port* equals *Container port*. To provide external IP tick Public checkbox in front of proper port. Use the following addresses to access the container:

* from other applications: *pod_ip:pod_port*

* from external IP: *public_ip:pod_port*.

* from containers within same pod: *127.0.01:pod_port*

![image alt text](screenshot_part1/image_150.png)

6. You can change variables in Environment variables section if needed. Click Learn more about this application to go to this application image description page in Docker Hub Registry. Here you can find all the necessary information on  this application variables.![image alt text](screenshot_part1/image_151.png)

7. To add a volume click *Add volume* and specify its location path in *Container path* field. Tick *Persistent* checkbox to mark a volume as persistent (would persist when container is restarted or moved to another server). In contrast to the local volume, data in persistent volume will be saved after container is restarted or even removed.![image alt text](screenshot_part1/image_152.png)

8. In the bottom you will see price per one hour of this application running. The price depends on amount of resources (Kube Type & size). Click *Start your App* to start the application and go to Apps section.

![image alt text](screenshot_part1/image_153.png)

Your application will start within a few minutes - its status will change to "running".

![image alt text](screenshot_part1/image_154.png)

**Managing applications**

Click KuberDock section to proceed to page with all applications displayed in the list.

![image alt text](screenshot_part1/image_155.png)

The information on current applications’ statuses is displayed in Application table column Status. You can start, stop or remove an application in Actions column. Click Edit, to go to KuberDock and control this application.

The application that was not payed successfully will be also displayed in this list. You will be able to click "Pay and Start" to pay for application and start it normally.

Click on the application name to view detailed information:

1. Allocated resources and control buttons:

* Limits - resources allocated for this application;

* Public IP - application IP address available from the internet. If no IP assigned - none.

* Status - your application current status:

Running - the application is started and running;

Pending - the application is starting or stopping;

Stopped - the application is stopped.

* Actions - application control buttons:

Stop/Start - start or stop application (changes depending on application status);

Edit - open KuberDock page with your application (see [Managing pods](#bookmark=id.oxq4h1tmou6h) for details).

Delete - delete application (the application will be no longer available and removed from cPanel). Note that after deleting Public IP and Persistent drive, applications will not be removed automatically and the fees will still be processing. If you are not going to use them anymore, remove [Persistent drive](#bookmark=id.bmm5foek49hg) and [Public IP](#bookmark=id.pem6upya7tjt)  from KuberDock manually.

![image alt text](screenshot_part1/image_156.png)

2. In Ports section the information on running container is displayed.

Here you can view all the ports with their settings shown in the table:

* Container’s port - container’s internal port;

* Protocol - data transmission protocol (udp or tcp);

* Host port - is external port of a container used to access container port from using external IP or from other ports.

* Public - if the port is available from the Internet, then checkbox will be ticked, otherwise no.

![image alt text](screenshot_part1/image_157.png)

3. *Volumes* section displays all added volumes and their parameters specified for container when creating:

* Persistent - means that this is a persistent volume, that will persist through container restarts & removal

* Name - persistent volume name;

* Size - persistent storage disc space capacity in MB. 

![image alt text](screenshot_part1/image_158.png)

4. In *Environment variables*  section all the variables names and values are displayed in the list. 

![image alt text](screenshot_part1/image_159.png)

5. Pricing - the price for application based on Kube Type and the number of Kubes.

![image alt text](screenshot_part1/image_160.png)

If you need to add one more application, click Add more apps.

**KuberDock plugin update instructions**

To update KuberDock plugin perform the following steps:

1. Log in to shared hosting panel server console as root.

2. Use the commands:

*wget  **[http://repo.cloudlinux.com/kuberdock-client/kcli-deploy.s*h](http://repo.cloudlinux.com/kuberdock-client/kcli-deploy.sh)

*bash ./kcli-deploy.sh --upgrade*

**Command line API**

Note that cPanel users are not required to install kuberdock-cli and can go straight to [How to use](#bookmark=kix.v6aw3lmtqsa8) section.

Requirements:

* RedHat, CentOS or ClouLinux OS.

* Python 2.6.0 or higher.

**How to set up**

To set up command line interface in KuberDock perform the following steps:

1. According to your OS architecture choose the latest version of proper kuberdock-cli rpm-package from our repository and  install it:

СentOS 6: [http://repo.cloudlinux.com/kuberdock-client/6/](http://repo.cloudlinux.com/kuberdock-client/6/)

CentOS 7: [http://repo.cloudlinux.com/kuberdock-client/7/](http://repo.cloudlinux.com/kuberdock-client/7/)

For example, for CentOS 7 (x86_64):

*yum install http://repo.cloudlinux.com/kuberdock-client/7/x86_64/kuberdock-cli-1.0-4.el7.cloudlinux.x86_64.rpm*

2. Note. This step should be missed by root access users.

Run command to create config in home directory:

*kcli kuberdock start start_pod*

3. Get a token for your account in KuberDock using command:

*curl -X GET -k --user <username>:<password> https://kuberdock.domain/api/auth/token*

You will get the answer with your token:

*{*

*"status": "OK",*

*"Token":*

**_admin|1469540670|cc8b11e2e801e8357cb7655ce4fcc6e611698396_**

*}*

Use your token on the next step.

4. Edit and save *config* file kubecli.conf (~/.kubecli.conf) enter KuberDock server address and your KuberDock account token from step 3:

[global]

*# kuberdock server URL*

*url = ***_https://domain.name_**

[defaults]

*# default registry to pull docker images from*

*registry = **[registry.hub.docker.co*m](http://registry.hub.docker.com/)

*#token **to **connect with kuberdock*

*token = ***_admin|1469540670|cc8b11e2e801e8357cb7655ce4fcc6e611698396_**

	

**How to use**

To start kuberdock-cli program just type *kcli*. The list of available commands with their descriptions and instructions is presented below.

Note that:

<**angle brackets**> - denote parameters that are required to complete a command

[**brackets**] - denote options that are not required to complete a command

**Config option:**

You can specify config file in each command with the options below or run any kcli command to generate config in user’s home directory (~/.kubecli.conf), which can be edited according to the instructions in [How to Set up](#bookmark=kix.eex5294e8bmo) section. This config will be used as default for this user. Options available in each kcli command:

*-c, --config*

path to config file (ini format), default path is "~/.kubecli.conf"

To do output data in json, use the following option:

*-j, --json*

Example:

*kcli -c /etc/mykubecli.conf kuberdock set newpod --image nginx*

Config /etc/mykubecli.conf is used to create a pod "newpod" with a container "nginx".

**Commands are:**

*kuberdock *-- provides KuberDock specific functionality: creating and configuring pods and containers to be transmitted on the server, searching for images;

*kubectl *-- mimics kubernetes ‘kubectl’ functionality

*docker *-- mimics docker functionality

To create a pod, first you need to [create and set up temporary pod configuration](#bookmark=id.s4rvczzdpqk3) on a local machine, [add and configure container images](#bookmark=id.2yenkp6m33it) in it, then submit pod configuration to KuberDock and use [start and install commands](#bookmark=id.opxn5tkxrpk5) to control pod. 

**Actions for kuberdock:**

The following commands are available:

*create*, *delete*, *describe, drives, forget, image_info, kube-types, list, save, search, set, start, stop*

For work with temporary pod:

**_create:_** create new temporary pod

To set up new [pod](#bookmark=kix.dzhy9271gfyo) and work with temporary pods use the following commands:

*kcli [-c config] kuberdock create <POD_NAME>*

Create a new temporary pod configuration on your local machine with the name you need.

**_set_**: configuring a temporary pod

Use the command *set <POD_NAME>* until container/containers setting is finished. You can not reset parameters of pod after saving it configuration and command *kcli kuberdock save <POD_NAME>* was executed, as pod data is submitted to KuberDock. 

	To set up pod configuration use options below:

*kcli [-c config] kuberdock set <POD_NAME> [***_--kube-type_*** <STRING>]*

Set pod [Kube Type](#bookmark=kix.k0vfh3mcl1if) name. If there is a space in Kube Type name, then specify "Kube Type name" in quotes*. *To see a list of available Kube Types use command *kcli kuberdock kube-types.*

*kcli [-c config] kuberdock set <POD_NAME> [***_--restart-policy_*** <STRING>]*

	Set [restart policy](#bookmark=kix.32a6e3nbg8yt) for the pod.

**_forget_**: delete temporary pod

Use this command to delete temporary pod from your local machine. Note that all configured containers in that pod would be deleted if using command without argument <POD_NAME>.

*kcli [-c config] kuberdock forget <POD_NAME>*

	

**_list_**: list all temporary pods stored on local machine

*kcli [-c config] kuberdock list*	

**_save_**: send a pod configuration to KuberDock server

*kcli [-c config] [-j] kuberdock save <POD_NAME>*

After you save a pod it will be not available in a list of temporary pods.

**_describe_**: returns a configuration of a temporary pod

			*kcli [-c config] [-j] kuberdock describe <POD_NAME>*

Describes the pod configuration that is not saved and sent to KubeDock server

**_kube-types_**: returns a list of available [Kube Types](#bookmark=kix.k0vfh3mcl1if)

			*kcli [-c config] [-j] kuberdock describe <POD_NAME>*

Describes the pod configuration that is not saved and sent to KubeDock server

### **KDCTL utility**

Requirements:

* RedHat, CentOS 7 or higher, ClouLinux OS.

* Python 2.7 or higher.

How to set up

To install command line interface tool *kdctl* in KuberDock perform the following steps:

According to your OS architecture choose the latest version of proper kuberdock-manage rpm-package from our repository and  install it:

CentOS 7: [http://repo.cloudlinux.com/kuberdock-client/7/](http://repo.cloudlinux.com/kuberdock-client/7/)

For example, for CentOS 7 (x86_64):

*yum install http://repo.cloudlinux.com/kuberdock-client/7/x86_64/kuberdock-manage-0.2.0-1.el7.noarch.rpm*

How to use

Kdctl is an Administrator command line interface tool for KuberDock. This tool provides a set of utilities to manage cluster settings, IP pools, nodes, users and so on:

*   config       Commands for config management

*   images     Commands for docker images management

*   ippool      Commands for IP pool management

*   login         Login to remote server

*   nodes       Commands for nodes management

*   pods         Commands for pods management

*   predefined-apps  Commands for predefined applications...

*   pricing      Commands for pricing management

*   pstorage  Commands for persistent volumes management

*   restricted-ports Commands to manage outgoing traffic from containers

*   system-settings  Commands for system settings management

*   users        Commands for users management

The actual set of resources can be found at "kdctl --help"

### Login

Using of this tool is started from login:

kdctl login

   	 Username: <enter admin username>

   	 Password: <enter admin password>

Login requests token from KD API and save it locally under the user directory. Thus login needs to be issued once per system unless you want to switch the account.

Each of the resources kdctl supports always provides basic CRUD operation and optionally some resource-specific utilities.

Config 

Commands for config management

kdctl config

Commands:

  set   Set config value

  show  Show current config

IPpool

Command used for IP pool management: 

kdctl ippool [OPTIONS] COMMAND [ARGS]...

Commands:

  create	Create new IP pool

  delete 	Delete existing IP pool

  get 		Get existing IP pool by network

  list 		List all existing IP pools

  update 	Update existing IP pool

Nodes

Usage: kdctl nodes [OPTIONS] COMMAND [ARGS]...

  Commands for nodes management

Options:

  -h, --help  Show this message and exit.

Commands:

  check-host 	Check hostname

  Create	Create new node

  delete      	Delete existing node

  get         	Get existing node

  list        	List existing nodes

  update      	Update existing node

Domains

Usage: kdctl domains [OPTIONS] COMMAND [ARGS]...

  Commands for domains management

Options:

  -h, --help  Show this message and exit.

Commands:

  create  Create new domain (see [example](#bookmark=kix.ujf52mmfocht))

  delete  Delete existing domain

  get     Get existing domain

  list    List all existing domains

  update  Update existing domain

Predefined-apps 

Usage: kdctl predefined-apps [OPTIONS] COMMAND [ARGS]...

  Commands for predefined applications management

Options:

  -h, --help  Show this message and exit.

Commands:

  create         	Create new predefined application

  create-pod     Create pod from template

  delete         	Delete existing predefined application

  get            	Get existing predefined application

  list           	List existing predefined applications

  update         	Update existing predefined application

  validate-template  Validate template of predefined application

Restricted-ports

By default, outgoing traffic from almost all container ports is enabled. Only TCP connections of the 25 port are disabled to prevent unauthenticated mailing.

The commands below provide necessary manageability level of access to the ports:

kdctl restricted-ports COMMAND [ARGS]...

 

Commands:

  close <PORT> [<PROTOCOL>] 	Close a port for outgoing traffic

  list 	                               	        	List all closed ports

  open <PORT> [<PROTOCOL>]  	Open a port for outgoing traffic.

Arguments:

  *<PORT>* is port number, mandatory

  *<PROTOCOL>* is port protocol which can have one of the two values — *TCP* or *UDP*, optional, *TCP* is default.

 

The commands affect all containers of all users’ pods of the given cluster.

 

Examples:

1. **Adding the new predefined app to catalog**

Create PA from yaml template file

kdctl predefined-apps create --file <yaml_template_file> --validate --name <app_name>

Show details about PA

kdctl predefined-apps get --name <app_name>

2. **Create pod on behalf of the user**

Besides the admin functions, kdctl also allows admin to perform any user action on behalf of specified user. Create pod:

kdctl pods create --file <pod spec file> --owner <username>

Where *<pod spec file>* contains a json specification like following:

{

    "kube_type": 1,

    "restartPolicy": "Always",

    "name": "My pod",

    "containers": [

        {

            "kubes": 4,

            "image": "nginx",

            "name": "dss7686nkx",

            "ports": [

                {

                    "containerPort": 80,

                    "hostPort": 80,

                    "isPublic": true,

                    "protocol": "TCP"

                }

            ]

        }

    ]

}

List user pods

kdctl pods list --owner <username>

Delete user pod

kdctl pods delete --name <pod_name> --owner <username>

3. **Manage persistent storage on behalf of the user**

List PVs

kdctl pstorage list --owner <username>

Delete PV

kdctl pstorage delete --id <pv_id> --owner <username>

**4. Create domain **

Admin is able to create base domain with kdctl. It is possible to also use custom certificate using following command:

kdctl -d domains create '{"name": "hosted.example.com", "certificate": {"cert": "-----BEGIN CERTIFICATE-----\nMIIDQ...1WV8=\n-----END CERTIFICATE-----", "key": "-----BEGIN PRIVATE KEY-----\nMIIEv...WP2DYA=\n-----END PRIVATE KEY-----"}}'

To work with container images and add it in temporary pod use the following command and option for command *kcli kuberdock set*:

**_search_**: allows to search container image at docker hub

			*kcli [-c config] [-j] kuberdock search <IMAGE_NAME>*

This command returns a list of founded container images in docker hub. You can set docker hub address in config file (~/.kubecli.conf) in section *registry*.

**_image_info_**: describe specific dockerfile

			*kcli [-c config] [-j] kuberdock image_info <IMAGE_NAME>*

This command returns a content in dockerfile of founded container images.

*kcli [-c config] kuberdock set <POD_NAME> [***_--container_*** <IMAGE-NAME>]*

Add specified image to the pod and pull the image configuration file (dockerfile). Container ports and volumes will be added from this file.

*kcli [-c config] kuberdock set <POD_NAME> [***_--delete_***] <IMAGE-NAME> *

Delete specified image from the pod.

To set up a container added to the temporary pod use the following commands:

*kcli [-c config] kuberdock set <POD_NAME> [--container <IMAGE-NAME> [***_--container-port_*** <STRING>]]*

This command allows to control ports and make them available from the Internet.* *Note that:

* To define container port, specify them separated by commas: *--container-port ***_80,8443,22_**

* To specify a pod port which is different from container port, use colon (:) after container port number: *--container-port 80,***_8443:443_***,22*

* To make a container port available from the Internet, use plus (+) before port number: *--container-port ***_+80_***,8443:443,22* or *--container-port 80,***_+8443:443_***,22*

* To specify protocol for proper container port, use colon (:) after port number: *--container-port +80,8443:443,***_22:udp_** or *--container-port 80,***_+8443:443:tcp_***,22*

*kcli [-c config] kuberdock set <POD_NAME> [--container <IMAGE-NAME> [***_--mount-path _***<STRING>] [***_--index _***<INT>]]*

This commands allows to control volumes inside the specific container. Change or add container path. Use index, to add and change several container paths.

*kcli [-c config] kuberdock set <POD_NAME> [--container <IMAGE-NAME> [***_--kubes _***<INT>]]*

This command allows to set limits (number of Kubes) for container:

	

*kcli [-c config] kuberdock set <POD_NAME> [--container <IMAGE-NAME> [***_--env _***<ENV_NAME>:<ENV_VALUE>,<ENV_NAME>:<ENV_VALUE>,…]]*

This commands allows to set up environment variables for container, where ENV_NAME - variable name, ENV_VALUE - variable value.

*kcli kuberdock set <POD_NAME> --container <IMAGE_NAME> ***_--list-env_**

This command allows to return all environment variables that already configured for specific container image.

*kcli kuberdock set <POD_NAME> --container <IMAGE_NAME> ***_--delete-env_*** <ENV_NAME>*

This command allows to delete specific environment variable from specific image

*kcli [-c config] kuberdock set <POD_NAME> [--container <IMAGE-NAME> ***_-p_*** <STORAGE_NAME>] [--size=<SIZE> --mount-path=<STRING>] *

This commands allows to mount persistent storage to specific volume in container. Note that data in persistent storage will not wipe out during pod stop, restart or even delete.

Use the following commands to control pods statuses in KuberDock:

*kcli [-c config] [-j] kuberdock ***_start _***<POD_NAME>*

	Start specified container

*kcli [-c config] [-j] kuberdock ***_stop _***<POD_NAME>*

Stop specified container

*kcli [-c config] [-j] kuberdock ***_delete _***<POD_NAME>*

	Delete specified pod

Other commands:

**_drives_**: command for managing persistent volumes

*kcli [-c config] [-j] kuberdock drives list*

*	Return a list of persistent volumes*

*kcli [-c config] [-j] kuberdock drives add --size <SIZE_IN_GB> <VOLUME_NAME>*

*Add persistent volume with exact size and name. Example: kcli kuberdock drives add --size 2 new_volume*

*kcli [-c config] [-j] kuberdock drives delete <VOLUME_NAME>*

*Delete persistent volume by name*

**Actions for kubectl**

The following commands are available:

*create, delete, describe, get*

**_create_**: allows to start pod from yaml file

*kcli [-c config] [-j] kubectl create pod -f [FILE_NAME]*

Create new pod from specification in YAML-formatted file. Specify '-' instead of [FILE_NAME] to pass content via stdin.

Note that we are still on the way to add ability to create and start pod from our YAML-files from [github](https://github.com/cloudlinux/kd_predefined_apps).

**_delete_***: allows to delete pod by name*

*kcli [-c config] [-j] kubectl delete pod <POD_NAME>*

**_describe_**: print detailed information about pod specified by POD_NAME

*kcli [-c config] kubectl describe pod <POD_NAME> *

**_get_***: *List all pods or one pod if POD_NAME specified

*kcli [-c config] kubectl get pods [POD_NAME]*

*	*

USER GUIDE

MANAGING [PODS](#bookmark=id.on9qty5pb8g)

Note. Web interface supports the following browsers: Safari version 6 or later, Chrome version 38 or later, Firefox version 28 or later.

Log in to KuberDock as user. Go to *Pods* tab to view and manage all your [pods](#bookmark=id.on9qty5pb8g).

![image alt text](screenshot_part2/image_0.png)

**Remember that any actions with a pod will affect all ****[container**s](#bookmark=id.ndk4t2vgncvp)** within that pod.**

On this page you can click on pod name and proceed to [pod page](#bookmark=kix.vhfx5rsf0tzc) to manage containers in it and you can use action buttons in the right column to:

* Restart pod that is already running. This action will affect all the containers within the pod. When restarting a pod - two options are available in pop-up: click *Wipe Out* to erase all data and launch fresh pod, or click *Just Restart* to restart a pod with saving data on persistent storages.

 ![image alt text](screenshot_part2/image_1.png)

* Start/stop pod depend on its current state. Stopping a container will purge all container data, except data on persistent storages.

When KuberDock is deployed on Amazon Web Services, some latency may be experienced while connecting an application from the Internet via Elastic Load Balancer for the first time. The issue is caused by delay in refresh of cached DNS records. No special actions are required — the problem disappears in several minutes.

It is also possible to use bulk action by tick on checkboxes on the left side.

![image alt text](screenshot_part2/image_2.png)

**Pod page**

On the pod page you can manage pod itself as described below, [edit pod configuration](#bookmark=kix.930yagkjbw31), [monitor resources](#bookmark=kix.fjjwsyt463iq), [manage containers](#bookmark=kix.haprif68exg) and [control ssh/sftp access](#bookmark=kix.xq0iyeywz1mv).

You can manage your pod by clicking "Manage pod" drop-down menu where you are able to:

![image alt text](screenshot_part2/image_3.png)

* Start -- if your pod is stopped then you can start it and it means that you start all containers in the pod.

* Stop -- if your pod is running then you can stop it and it means that you stop all containers in the pod. Stopping a container will purge all container data, except data on persistent storages.

* Restart -- these actions will affect all the containers within the pod. When restarting a pod - two options are available in pop-up: click *Wipe Out* to erase all data and launch fresh pod, or click *Just Restart* to restart a pod with saving data on persistent storages.

 ![image alt text](screenshot_part2/image_4.png)

* [Edit pod](#bookmark=kix.930yagkjbw31) -- allows you to change whole pod configuration and containers in it.

To monitor resources usage click Stats:

![image alt text](screenshot_part2/image_5.png)

Resources usage diagrams will be displayed below:

![image alt text](screenshot_part2/image_6.png) 

Blue curve shows limits set, orange curve shows resources usage at a certain time. 

To go back to containers list click Data:

![image alt text](screenshot_part2/image_7.png)

In the information sections on the left current status is displayed:

* Public IP (or Service address) - IP address or service address accessible from the internet;

* [Pod IP](#bookmark=id.1cgvmbs6c7aq) - internal pod IP within KuberDock;

* [Restart policy](#bookmark=id.583q795oizo7) - set restart policy behavior;

* [Kube Type](#bookmark=id.oevr4pqmszru) - bunch of resources;

* Number of Kubes - number of Kubes in that container;

* Price for a pod.

![image alt text](screenshot_part2/image_8.png)

Click on any container in the table to get to Container page where you can control it.

![image alt text](screenshot_part2/image_9.png)

**Edit pod**

You can change configuration of your existing [pod](#bookmark=id.on9qty5pb8g) with its containers by clicking "Edit" on the [pod page](#bookmark=kix.vhfx5rsf0tzc) in Manage pod drop-down menu.

![image alt text](screenshot_part2/image_10.png)

After clicking "Edit" you will be redirected to the [Final step](#bookmark=kix.ckvpifmww2ap) of the container creation process. On that page you can:

* Change used Kube Type in the pod and change its` restart policy. This will affect all container in the pod.

![image alt text](screenshot_part2/image_11.png)

* Change Kubes quantity for each container in the pod.

![image alt text](screenshot_part2/image_12.png)

* Change configuration of each container in the pod or delete containers from the pod. When you click on edit icon you will be proceed to second step of create container process - Set up image. Use the following [instruction](#bookmark=kix.djd50aotw6q2) you can change configuration of current container.

![image alt text](screenshot_part2/image_13.png)

* Add new containers to the pod by clicking "Add more containers". After click you will be proceed to the first step of create container process. Follow [instructions](#bookmark=kix.89n1v5g8uu08) to add container successfully.

When you are done you will have two scenarios:

1. If your changes lead to growing up the price of the pod then you can:

    1. Click "Pay and apply changes" that will proceed to billing system and after successful payment your changes will be applied and pod with all containers will be restarted with new configurations.

    2. Click "Save for later" to save change you made for future applying.

2. If your changes DO NOT lead to growing up the price of the pod then you can click "Save" to save changes and you will be redirected to the pod page. On the pod page you can click “Restart & Apply changes” that will lead to restarting the pod and its containers with new configuration or click “Reset Changes” to discard and delete changes you have made during editing.

![image alt text](screenshot_part2/image_14.png)

**SSH/SFTP access to containers**

In the main menu choose Pods and click on the name of the pod to locate a container in. On the [pod page](#bookmark=kix.vhfx5rsf0tzc) in the list of containers in *SSH (link/pass) *column - the link and the key icons lead to copy SSH link and password to clipboard accordingly. Use this link to connect to your containers via SSH or SFTP connection.

![image alt text](screenshot_part2/image_15.png)

To regenerate password click Reset SSH access at the top of the page. This action will reset password for each container in the pod but will not change the link.

![image alt text](screenshot_part2/image_16.png)

 

Sometimes, IP addresses used to compose SSH links to containers may be changed due to reasons beyond KuberDock control.

In such cases, KuberDock automatically regenerates the links which may require the pod page refresh to renew them in the container list.

Please read carefully known problems with OpenSSH [here](#bookmark=kix.vagyaqacrwm6).

	**Creating a container**

Note. web interface supports the following browsers: Safari version 6 or later, Chrome version 38 or later, Firefox version 28 or later.

On the user's main page "Pods" click *Add new container* to start creating a container. ![image alt text](screenshot_part2/image_17.png)

Change pod name if you need.

![image alt text](screenshot_part2/image_18.png)

Then the process takes 4 steps:

1. **Choose image**. Find the docker container image by entering it`s name (or part of the name) in search line and click on magnifier icon or press Enter to view search results. 

In search results you will get (If you don’t know the name of docker container image, try typing application name, like wordpress, mysql, redis, etc., and click "Enter" or magnifier and KuberDock will show you the list of potential container images that you can use):

* List of ready to use application out of the box created and configured by our team. If you choose ready to use application you will be redirected to page where you are able to choose resource plan for it.

* List of docker images from selected registry (read about it below).

Click *Select* in front of the image or application to start setting up its configuration or choose resource plan. By default, you are searching Docker Hub container image registry.

![image alt text](screenshot_part2/image_19.png)

You can view detailed information on proper container image by clicking on Learn *more..*. in image description.

To choose docker container image from private repository, choose Docker Hub/private repo from Search from directories drop-down menu:![image alt text](screenshot_part2/image_20.png)

Enter Username and Password, specify namespace and image separated by slash symbol (/) and click Select:

![image alt text](screenshot_part2/image_21.png)

To search for docker container image in other repositories, choose Other registries in drop-down menu, enter login and password and specify path to the image in the following form: 

*"**registry/**namespace/image" *,

where *registry* - domain address of needed registry, 

for instance: *"your_registry.com/my_namespace/my_image_name"*,  

and click Select.

![image alt text](screenshot_part2/image_22.png)

1. **Set up Image**. On the second step set up Docker image configuration:

* Specify** Command **to customize command to run inside a container when it starts. Use space to separate parameters as you would typically do in shell. For example, *redis --conf /etc/redis.conf*

![image alt text](screenshot_part2/image_23.png)

* **Set up Ports**. In *Ports* section define which ports of your container should be exposed. Click *Add port *and specify *Container port** (this is an internal port in container which needs to be exposed. Read more about container port usage in the schema* in "[Introduction](#bookmark=id.s6wi74jfeder)" section) and *Protocol*. By default, when you create a container port, a pod port with the same number is being created.

If you need a port to be accessible from an external IP address or Service address, tick the *Public* checkbox. In such case, you will be required to
choose public access type — Public IP or Domain:

![image alt text](screenshot_part2/image_24.png)

Note that only ports marked as *Public* are accessible from outside of the cluster.

Selecting *Public IP* you determine that the pod will be exposed outward by dedicated IP address: *public_IP:pod_port*.

Selecting *Domain *you make the pod externally accessed by its service address: *service_address:pod_port* (only port 80 for HTTP and port 443 for HTTPS can be used). Note that name-accessed pods aren’t charged for
the public IP addresses.

 

*Pod port* - is external port of a container used to access container port from using external IP or from other ports. Containers within the same pod can access the port using localhost IP 127.0.0.1. By default *Pod port* equals *Container port*. Use the following addresses to access the container:

* from other pods: *pod_ip:**pod_port*

* from external IP: *public_ip:pod_port *or *domain_name:pod_port*.

* from containers within same pod: 127.0.0.1:pod_port

Specify port number in *P**od** port* to redefine default values. KuberDock will redirect traffic from Pod port to container port.

Note that public IP usually costs extra fee, we recommend to use it only if you need.

Note that if you have bought Public IP then it means that you have one available Public IP to use in pods configuration. One available public IP can be used only by one pod at one time.It is possible to edit pod#1 and remove public IP from it and then edit/create another pod#2 with available and free public IP.

![image alt text](screenshot_part2/image_25.png)

To complete creation of the name-accessed pod you should select a domain from the dropdown list appearing upon the *Domain *selection:

* Standard domain -- the default domain of your hosting provider

* Specific domain -- additional available domains that can be used only for 80 and 443 ports. This type of domain has a more beautiful name then standard domain.

![image alt text](screenshot_part2/image_26.png)

*

The name of the pod will be composed automatically according to the following pattern:

*<username>-<podname>.<selecteddomain>*

For example, if user *jdoe* chooses the *dreamhosting.com* domain for his/her pod *wpinovado* the access point will look as follows *jdoe-wpinovado.dreamhosting.com*.

All you need to get to the name-accessed pod externally is to enter it to the browser address bar *http://<username>-<podname>.<selecteddomain>* or *https://<username>-<podname>.<selecteddomain>*.

Note. Please be aware that full pod domain name limited to 64 symbols.

* **Set up Volumes**. To add a volume click *Add volume* and specify its location path in *Path* field. Use checkbox *Container* (not persistent) or *Persistent* (will persist when container is restarted). Data in Persistent volume will be saved after container is restarted or even removed.

![image alt text](screenshot_part2/image_27.png)

Tick *Persistent *checkbox and begin to type the name of persistent storage. Choose one of persistent storages you have created from *Select Persistent Disk *drop-down menu or create new persistent:

![image alt text](screenshot_part2/image_28.png)

To cancel click recycle bin icon.

Note that in dropdown you will see all existing persistent disks and used ones would have text "busy" in parentheses: 

![image alt text](screenshot_part2/image_29.png)

Note, that additional fees will be charged by a provider for using persistent storage. You can use one persistent storage for several pods during a payed period of it, but only one pod can use the same persistent storage at one time. It is possible to edit pod and remove persistent storage from it and then edit or create another pod with the same persistent storage.

Click "Next" to proceed to the next step.

1. **Environment variables. **Here you can specify and manage environment variables for this container. Enter variable *Name* and *Value* in appropriate fields and click *Next* to go to the final step of setting up a container. 

Note that some docker container images require specific environment variables for container to work correctly. Click "*Learn more about variables for this image"* to view detailed information about the image in Docker hub. 

Click Reset values, if you need to return variables and their container image values to default values. Note that in this case all the changes made on this step will be reset.

 ![image alt text](screenshot_part2/image_30.png)

1. **Final setup**. On this step:

* Choose "[Restart policy](#bookmark=id.583q795oizo7)" from drop-down menu:

![image alt text](screenshot_part2/image_31.png)

* Choose [Kube Type](#bookmark=id.oevr4pqmszru)* for container from drop down menu. If any Kube Type is shown in grey, then this Kube Type is currently unavailable:

![image alt text](screenshot_part2/image_32.png) 

* Choose number of Kubes for this container to define resource levels allocated for the container: 

![image alt text](screenshot_part2/image_33.png)

Note that container resource levels will be depicted on the page and will be updated automatically accordingly with the chosen Kube Type and Kubes number:

![image alt text](screenshot_part2/image_34.png)

Price specified in *Total price* section is based on resource usage allocation. For example, if you have chosen 5 Kubes, then the cost is calculated as price for one Kube multiplied by 5. The cost is specified as total workload with all the options selected. 

![image alt text](screenshot_part2/image_35.png)

Click *Back *to return to the previous step, click *Add more **containers* to add another container to this pod, click *Save* to save pod configuration and its containers for later use (the containers will be displayed on Pod page with the status "unpaid"), or click *Pay And Start *to pay for this pod and launch it. 

Note that after clicking *Pay And Start* you will be charged automatically and redirected to Pod page. If on some reason payment will not succeed, then you will be redirected to billing system of your hosting provider to pay for the pod and start after successful payment. 

![image alt text](screenshot_part2/image_36.png)

To remove container image from the list click Remove (recycle bin icon) in front of it:

![image alt text](screenshot_part2/image_37.png)

To change container image settings, click Edit (pen icon):

![image alt text](screenshot_part2/image_38.png)

You will get back to the second step of Creating a Container and will need to complete the second and third steps again.

 

*Note that if you add two or more containers to one pod and change Kube Type on the final step, then this Kube Type will be reassigned for all containers in the pod and total cost will be recalculated.

MANAGING CONTAINER

**Container Page**

Select a [container](#bookmark=id.ndk4t2vgncvp) that you would like to manage by clicking on its name on the Pod page. Here you can [monitor container's resource load](#bookmark=kix.o71nibc2ktjh), [view logs](#bookmark=kix.jf0brk7qp7xu) and [container configuration](#bookmark=kix.ss9t27vlcpll).

To get SSH/SFTP access to container follow to section [SSH/SFTP access to container](#bookmark=kix.xq0iyeywz1mv).

At the top of the page you can find *Status* control indicator. Current status of a container updates automatically and doesn't require reloading the page. Status of a container can be:

    * Running - the application is started and running;

    * Pending - the application is starting or stopping;

    * Stopped - the application is stopped.

![image alt text](screenshot_part2/image_39.png)

Current settings and information on resources allocated for this container are displayed in information sections:

![image alt text](screenshot_part2/image_40.png)![image alt text](screenshot_part2/image_41.png)

To upgrade resources click "Upgrade resources" at the top.

![image alt text](screenshot_part2/image_42.png)

You will be redirected to the page with all containers in the pod where you can change amount of resources for each of them. Note that to apply new resources the whole pod will be restarted.

Click + to add more Kubes or - to reduce the number. By adding Kubes quantity you will see additional costs for upgrade and total price will be changed accordingly. 

By reducing Kubes quantity you will see that total price changed accordingly. 

When done, click Pay And Apply Changes in case of adding Kubes to proceed to payment process and upgrade resources for your pod after successful payment or Save in case of reducing Kubes. Note that pod will be restarted to upgrade its resources.

![image alt text](screenshot_part2/image_43.png)

Current pod’s hardware configuration is displayed in this section:

![image alt text](screenshot_part2/image_44.png)

Use menu on the left to view [logs](#bookmark=kix.jf0brk7qp7xu), [resources usage](#bookmark=kix.o71nibc2ktjh), [general configuration](#bookmark=kix.ss9t27vlcpll) and [container environment variables](#bookmark=kix.xykbi9ad4ris):

![image alt text](screenshot_part2/image_45.png)

**Container Log**

To view container log click on *Logs* tab. On the Logs page the standard output of a container is displayed. Log is updated automatically and doesn't require to reload the page. If a container is not running, then log is not displayed. Note that if Docker images do not support standard logging mechanisms, then such logs are not displayed on this page. 

Use *Export *button to download container log on your computer in *txt *format.

![image alt text](screenshot_part2/image_46.png)

**Monitoring**

Monitoring section contains resource usage statistics:

* CPU usage - CPU utilization percentage;

* RAM memory usage - memory used in MB;

![image alt text](screenshot_part2/image_47.png)

**Configuration**

In this section the information on running container is displayed. To view ports and volumes information, go to* General* section:

Here you can view all the ports with their settings shown in the table:

* Container’s port - container’s internal port;

* Protocol - data transmission protocol (udp or tcp);

* Pod’s port

![image alt text](screenshot_part2/image_48.png)

*Volumes* section displays all added volumes and their parameters specified for container when creating:

* Persistent - means that this is a persistent volume, that will persist through container restarts & removal

* Name - persistent volume name;

* Capacity - persistent storage disc space capacity. 

![image alt text](screenshot_part2/image_49.png)

**Environment variables**

To view the list of all added environment variables and their values, go to *Variables* tab on container page.

![image alt text](screenshot_part2/image_50.png)

UPDATE CONTAINER

To update a container to the latest up-to-date version, click Check for Updates on Container page to search for updates for your docker image:

![image alt text](screenshot_part2/image_51.png)

If updates are available, *Check for Updates* button will change for *Update*:

![image alt text](screenshot_part2/image_52.png)

Click *Update *and confirm your action by clicking OK. Note that during update the whole [pod](#bookmark=id.on9qty5pb8g) will be restarted:

![image alt text](screenshot_part2/image_53.png)

You can also update container on Pod page. Click update icon to check if any updates are available:

![image alt text](screenshot_part2/image_54.png)

If updates are available, then update icon will change for download icon:

![image alt text](screenshot_part2/image_55.png)

Click on update icon and then OK to confirm your action.

VIEW ACCESS ENDPOINTS

To view Public IPs or service addresses used by pods, in main menu choose Access endpoints - you will get to the page with all the Public IP addresses or service addresses displayed in the list with their pods’ names displayed in Pod Name column:

![image alt text](screenshot_part2/image_56.png)

MANAGING PERSISTENT VOLUMES

To manage Persistent Volumes, in main menu choose Persistent volumes - you will get to the page with all the Persistent volumes displayed in the grid with their Size and Status specified in appropriate columns:

![image alt text](screenshot_part2/image_57.png)

Persistent volumes possible statuses:

* Busy - the icon is orange, persistent volume pod name is specified.

* Free - the icon is green. Persistent volume is not used by any pod.

Each persistent volume billed as usual regardless on its status`

EDIT USER PROFILE

Go to *Settings** *section on the top of the page to go to your profile page.

![image alt text](screenshot_part2/image_58.png)

Click "Edit" to edit your profile:

![image alt text](screenshot_part2/image_59.png)

Specify the necessary information in appropriate fields and click *Save Changes* to save your profile or *Cancel *to return to profile page without saving.

![image alt text](screenshot_part2/image_60.png)

START PREDEFINED APPLICATION

You can run predefined application from the application home page or from [KuberDock control panel](#bookmark=kix.89n1v5g8uu08).

The link to predefined application home page can be placed on web-hosting provider web-site or any other web-site.

After you click on application link or choose it in KuberDock control panel you will proceed to the page with different resource plans for predefined application. Perform the following steps to launch your predefined application:

1. Choose the most suitable plan for your application:

![image alt text](screenshot_part2/image_61.png)

Click Show details under a plan to show resource levels that will be allocated to your application according to each plan. Click Choose plan to proceed to the next step. If you need to switch application package, then follow [this instructions](#bookmark=kix.t2w9zv9upanw).

2. Depending on application type you might need to specify additional configuration for it on the next step. It can be user and password, domain or subdomain, etc. For example, you need to enter only application name that will be display in the list of your apps.

![image alt text](screenshot_part2/image_62.png)

3. Click "Order now" to purchase the application. Or click "Choose Different Package" to change the package for this application. Pay for predefined application depending on hosting-provider's billing system. The application will start automatically after purchase.

4. After purchase succeeded, user gets to his [predefined application page](#bookmark=kix.qe2wmxjg2xt4) in KuberDock with brief description of the application on top of the page.

![image alt text](screenshot_part2/image_63.png)

You can find detailed information on the elements of this page as well as the information on how to control the application in [Managing Pods](#bookmark=id.oxq4h1tmou6h) and [Managing containers](#bookmark=kix.haprif68exg) sections.

**Switch application package**

Note that ability to switch package is depended on application configuration and KuberDock configuration at you service provider so if you have any difficulties then you should contact your service provider for details.

Perform the following steps to switch application package:

1. Go to application page and click Switch package:

![image alt text](screenshot_part2/image_64.png)

2. On the next page choose a package to switch:

![image alt text](screenshot_part2/image_65.png)

Your current package will have a white disabled button "Current package".

Note that depending on your hosting provider settings it can be impossible to change the size of persistent storage thus all packages will have the same size of persistent storage as your current package has.

3. After clicking "Choose package" two types of behavior are possible:

1. If new application package price is higher than your current one, then you will be redirected to billing system to pay for new application package and after successful payment you will be redirected to your application page in KuberDock and application will be restarted with new package.

2.  If new application package price is the same or lower, then you will be redirected to your application page in KuberDock and application will be restarted with new package.

Note if you will click "edit" and following [this instruction](#bookmark=kix.930yagkjbw31) will change application configuration then you will not be able to switch application packages.

ADMINISTRATION

**Adding predefined applications**

Admin can add predefined application and provide ability to user to follow generated link to it or find it in search results in KuberDock control panel and finally launch and use this predefined application.

To add predefined application log in to KuberDock as admin and click *Predefined application* in main menu to proceed to the page with the list of all added applications. Click Add new application and follow steps below.

![image alt text](screenshot_part2/image_66.png)

* Upload YAML. Click "Upload yaml" button and choose proper file or YAML code in textarea. You can use ready-to-use YAML files from our github repository ([https://github.com/cloudlinux/kuberdock_predefined_apps](https://github.com/cloudlinux/kd_predefined_apps)) or create your own YAML file according to [specification](#bookmark=kix.h57fp626m1xg). Data will be displayed below in a separate section.

* Click "Add" button to save application and make it available to run by a user.

![image alt text](screenshot_part2/image_67.png)

You can click on the name of a predefined application to see user’s view of the application setup. To place a link to the application on 3rd party websites, use the link in address bar while on application page or click "Copy link" in the list of predefined applications.

![image alt text](screenshot_part2/image_68.png)

**Using predefined application with "No billing" settings**

Use the following guide to set Predefined application in case when in *Select your billing system* field of Billing tab in KuberDock settings - *No Billing* is chosen.

With such configuration, authorization token must be sent to KuberDock, not to billing system, to allow user start predefined application and get access to KuberDock.

We use JSON Web Tokens (JWT, [jwt.io](http://jwt.io)) for authentication. To generate correct token, use libraries for different programming languages provided on [jwt.io](http://jwt.io). Find detailed information about JSON Web Tokens in official documentation available on the link [jwt.io/introduction](https://jwt.io/introduction/).

For work with predefined applications perform the following steps:

Note that we recommend to use libraries available on  [jwt.io](http://jwt.io) to generate JSON Web Token.

1. In *header* section to be transmitted:

* "alg": encrypting algorithm, HS256 is recommended;

* "exp": expiration time (read more [here](https://tools.ietf.org/html/draft-ietf-oauth-json-web-token-32#section-4.1.4)), unix timestamp;

* "iat":  issued at (read more [here](https://tools.ietf.org/html/draft-ietf-oauth-json-web-token-32#section-4.1.6)), unix timestamp;

Decoded example:

header:

{

"alg": “HS256”,

"exp": 1469943308,

"iat": 1468339708

}

2. In *payload *section to be submitted:

    * "auth": must be *true*,  log in or create user;

    * "username":  enter username for new or existing user in KuberDock;

Additional fields required only if user doesn't exist in KuberDock yet:

    * "email": users` email;

    * "passwords": users` password.

Optional fields only for new user in KuberDock. User will be created with the data from this fields, otherwise data will be:

    * "package": id of package that will be applied to the user, read more about packages [here](#bookmark=id.7upq4gi4n35u).

    * "rolename": user role in KuberDock, available user roles [here](#bookmark=id.euwjiln62erc).

    *  "first_name": user first name;

    *   "last_name": user last name;

    *   "middle_initials": user middle initials.

    *   "timezone": ""America/New_York (-04:00)""

Decoded example:

payload:

{

"auth": true,

"username": “john_snow”,

"email": “[user@email.com](mailto:user@email.com)”,

"password": “28f*.J”,

"package": 1,

"rolename": “User”,

"first_name": “John”,

"last_name": “Snow”,

"middle_initials": “Bastard”,

"timezone": ““America/New_York (-04:00)””

}

3. In KuberDock go to Settings, choose Generals tab. In Secret key for Single sign-on field enter your secret key value. It must be shared between KuberDock and application that will send users to KuberDock.Single Sign On allows a user logs in to your own application (control panel, billing or etc) and then is "automatically" signed in to KuberDock.

![image alt text](screenshot_part2/image_69.png)

4. Encrypt header, payload and signature into one JSON Web Token using libraries available on  [jwt.io](http://jwt.io) and instructions on [jwt.io/introduction](https://jwt.io/introduction/).

5. Check token generation validity on[ jwt.io](http://jwt.io) - enter encrypted token in Encoded field, enter your secret key in VERIFY SIGNATURE field. If everything is correct, then Signature Verified message will be displayed.

![image alt text](screenshot_part2/image_70.png)

6. In KuberDock go to Predefined applications page and copy the link to proper application.

![image alt text](screenshot_part2/image_71.png)

7. Add your encrypted token to Predefined application link, to make link look as follows:

*https://kuberdock.master/apps/12269deccf6ffe3f12ebaa7d481dbb4133bb98f1?token2=eyJhbGciOiJIUzI1NiIsImV4cCI6MTQ2ODUyMDM2NCwiaWF0IjoxNDY4NDg4ODEyfQ.eyJ1c2VybmFtZSI6InduY20iLCJhdXRoIjp0cnVlfQ.R4upTWJC4NT2AD8RYfNAjzdmxiGQFRGQ5CCk8ALRvxw*

Where:

*https://kuberdock.master/apps/12269deccf6ffe3f12ebaa7d481dbb4133bb98f1* -- link to predefined application

*?token2= -- *GET parameter in url

*eyJhbGciOiJIUzI1NiIsImV4cCI6MTQ2ODUyMDM2NCwiaWF0IjoxNDY4NDg4ODEyfQ.eyJ1c2VybmFtZSI6InduY20iLCJhdXRoIjp0cnVlfQ.R4upTWJC4NT2AD8RYfNAjzdmxiGQFRGQ5CCk8ALRvxw -- *encoded JSON Web Token.

The link is ready for use.

**Managing nodes**

Log in to KuberDock as admin.

The main administrator page is Nodes page where all the nodes added to KuberDock are displayed in the list. Click on any node to get to separate node page.

![image alt text](screenshot_part2/image_72.png)

In the upper area of the Node page you can view node’s status, ![image alt text](screenshot_part2/image_73.png) 

as well as information on node’s hardware.

 ![image alt text](screenshot_part2/image_74.png)

Having KuberDock deployed in Amazon Web Services, it is necessary to remember that when a node is stopped and then restarted its public IP address will unavoidably be changed unless it has been assigned with an Elastic IP address. This is because of Amazon EC2 instances’ peculiarity which is beyond users’ control (refer[ Amazon EC2 Instance IP Addressing](http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-instance-addressing.html) for details).

Click *Delete *to remove a node. Note that even if the node is removed from user's pod web-interface, internal and public IPs keep on working.

![image alt text](screenshot_part2/image_75.png)

Use menu on the left to view logs, resource usage and other information:

**General** section contains information on the node and its hardware.

**Logs**. To view node log files go to *Logs* tab. Logs are being updated automatically in real time and do not require reloading the page. All the logs that are saved via rsyslog are presented here, including:

* Kernel messages log (*kern.* *from */dev/console).*

* Log level (or higher) info log (except mail and private authentication messages).  (**.info;mail.none;authpriv.none;cron.none *from *-/var/log/messages).*

* Log of all the mail messages in one place. (*mail.* *from *-/var/log/maillog).*

* Cron log (*cron.* *from *-/var/log/cron).*

* Log of saved news errors of level crit and higher. (*uucp,news.crit *from * -/var/log/spooler)*

![image alt text](screenshot_part2/image_76.png)

Note that if a node is not running, then its log is not displayed.

**Monitoring** section contains resource usage statistics:

* CPU usage - % of all CPU cores used;

* RAM memory usage - memory used in MB;

* Storage usage - number of used and available GB.

![image alt text](screenshot_part2/image_77.png)

**Managing accessibility of node ports**

Almost all node ports are closed by default for security reasons.
Several console command are intended to manage accessibility of the ports
when necessary:

* *kdctl allowed-ports list* — to get all opened ports

* *kdctl allowed-ports open <port_number> [<protocol>]* — to open a port having the specified number

* *kdctl allowed-ports close <port_number> [<protocol>]* — to close a port having the specified number.

 

Semantics of their parameters is following:

* *port_number* — port number, required

* *protocol* — protocol (TCP/UDP), optional, default value is TCP.

**Managing public IP (IPv4) ****pool**

Note. If your cluster is located on Amazon Virtual Private Cloud (VPC) then you do not need to configure and manage IP Pool as your cluster will use Elastic Load Balancer (ELB) that provides service addresses instead of Public IP. KuberDock will show all service addresses in use.

To allow users purchase public IPs, a pool of available IPs should be added to KuberDock. Public IPs will be automatically assigned to users from this IP pool by KuberDock. To add public IPs perform the following steps:

1. Go to *Administration* section and choose *IP pool*.

2. Click *Add subnet*.

![image alt text](screenshot_part2/image_78.png)

3. In *Subnet *field specify the IP subnet of available IPs:

![image alt text](screenshot_part2/image_79.png)

Note: Network identification (zero .0) addresses and broadcast addresses are not excluded automatically. These IPs should be excluded manually otherwise these IPs will be assigned to the users pods and, as a result, will not be available from the internet. This is applicable for KuberDock release 1.4 and lower.

4. In *Exclude IPs* enter IP addresses to be excluded from this subnet.

For example:

You have added the following subnet: *10.0.0.0/24*. Enter IPs to "Exclude IPs" field if you need to exclude them from this IP pool. You can separate each IP by comma or use dash (-) to exclude range of IPs as follows:

*10.0.0.1, 10.0.0.2, 10.0.0.3* or *10.0.0.1-10.0.0.3* or both in the same time *10.0.0.1,10.0.0.2-10.0.0.4*.

![image alt text](screenshot_part2/image_80.png)

5. This step is required in case of fixed IP pool cluster setup **only. **(For more details on fixed IP pool  please check [Master installation guide](#bookmark=id.quymgecpllf9) step 2). 

In *Node hostname* drop-down menu select node where current IP pool should be assigned to.

![image alt text](screenshot_part2/image_81.png)

6. When done, click *Add* to add IPs.

New subnet will be added. The list of all added subnets will be displayed in the IP Pool section of Administration page. On the top of the table the total amount of available IPs in all IP pools will be displayed:

![image alt text](screenshot_part2/image_82.png)

To delete subnet, click on Recycle bin icon and confirm or decline this action in pop-up. Note that you can not delete a subnet that includes IPs used by users [pods](#bookmark=id.on9qty5pb8g).

To view the list of IPs in subnet click on subnet in the table. All public IP addresses will be displayed in the list. These IPs will be automatically allocated to users when they request for Public IP for one of their Pods.

![image alt text](screenshot_part2/image_83.png)

Public IP can have the following statuses:

Free - green icon - this IP can be allocated to a user. You can click "stop" icon to block IP.

Busy - orange icon - this IP is already allocated to a user.

Blocked - red icon - this IP can not be allocated to a user. You can click "play" icon to make it free and available for allocation to a user.

**Using services addresses in AWS deployment**

If KuberDock is installed on Amazon Web Server (AWS), users' pods obtain Public service address for public access to applications.

To view the list of service addresses in use, log in to KuberDock as admin, go to *Administration* and choose *IP pool *(in KuberDock 1.3.0 choose *DNS names, from KuberDock 1.4.0 choose Access endpoints*). The list displays:

* Service address in use -- Service addresses used by a user;

* Username -- the name of a user which uses service address;

* Pod -- the name of pod service address is used in.

![image alt text](screenshot_part2/image_84.png)

Service addresses list shows all domains that are used by all users in KuberDock.

**Managing Users**

To manage users go to *Administration* tab and choose *Users* in drop down menu. All KuberDock users are displayed in this list. Note that changing service user "kuberdock-internal", which starts service pods for logs and DNS correct work, will result the disruption of these features in KuberDock.

![image alt text](screenshot_part2/image_85.png)

To create new user follow [this instructions](#bookmark=kix.l2u6a449dvqi).

To view users’ login&logout history [follow this instructions](#bookmark=kix.gtofo9wm8f1t).

To *Login as* user follow [this instruction](#bookmark=kix.m4q40blbpnv1).

On the user page next information available:

Username - current username and user status (read more [here](#bookmark=kix.l2u6a449dvqi))

Registered - user registration date

Package - current user package name

Timezone - timezone of the user profile

Role - current user role (read more [here](#bookmark=id.e97aup9w124o))

First name - user first name

Last name - user last name

Middle initials - user middle initials

Email - user email

![image alt text](screenshot_part2/image_86.png)

You can also see current users’ pods in the table below:

![image alt text](screenshot_part2/image_87.png)

To **create new user** click *Create user*.

Please, check our [video guide](https://www.youtube.com/watch?v=iDR3gjjwIz0&list=PLpqZ4QntcUI_FptpsEzN7oGRTXKuwHD8p&index=2) about how to add user in KuberDock. (Note. Video is still under development)

![image alt text](screenshot_part2/image_88.png)

Enter all the necessary information in proper fields:

* Username - KuberDock account login;

* First name - user`s First name;

* Last name - user`s Last name;

* Middle initials - user`s middle initials

* Password - user’s password;

* Email - email address for sending user notifications;

* [Roles ](#bookmark=id.e97aup9w124o)- user access type;

* Package - choose package (configured in your billing system) to assign to user;

* Status - user’s status:

                * *Active* - user is enabled in KuberDock;

                * *Locked* - user is disabled, his pods are stopped, public IP`s are unbinded, persistent volumes are deleted and he can not log in to KuberDock

* Suspended - if checked, user`s services will be stopped and new pods or other services can not be added.

![image alt text](screenshot_part2/image_89.png)

When done, confirm creating by clicking Create.

![image alt text](screenshot_part2/image_90.png)

To edit users' information click *Edit user *on the user’s page.

![image alt text](screenshot_part2/image_91.png)

When done, click *Save* to save changes.![image alt text](screenshot_part2/image_92.png)

"Restore user" feature is available since [KuberDock 1.5.0](#bookmark=id.h1p9rk3zbng1).

If you are creating a user with an email that has already been registered in billing system and has been deleted from KuberDock, then you are able to restore that user in the process of creating. Once you add email and other necessary fields and click Save, then if such email is already exists, then you will get a pop-up:

![image alt text](screenshot_part2/image_93.png)

If you click Yes, Restore then a user will be recovered from database. Recovered user becomes active after restore.

If you click No, Thanks, you will be redirected to the users' page without creating a new user.

To view the history of users’ activity in the system, go to User’s page and click *Login history* on the left. Login history is displayed in chronological order and includes login date and time, session duration, logout date and IP address.

![image alt text](screenshot_part2/image_94.png)

To log in to KuberDock as a proper user, go to user's page and click Login as this user:

![image alt text](screenshot_part2/image_95.png)

At the top of the page you will see the grey line with a notification that you are viewing the page under user credentials: User View Mode:

![image alt text](screenshot_part2/image_96.png)

with user's email address:

![image alt text](screenshot_part2/image_97.png)

While logged as a user, you have the same access type and the same GUI as this user.

To exit User View Mode click Exit Mode in the upper right area:

![image alt text](screenshot_part2/image_98.png)

Use billing system to delete a user. If you need to delete a user via KuberDock, click on recycle bin icon in front of a proper user in the list:

![image alt text](screenshot_part2/image_99.png)

Alternatively click Delete on users page:

![image alt text](screenshot_part2/image_100.png)

Click Delete in confirmation pop-up - a user will be deleted.

Note that this user will remain in billing system and her KuberDock product will not be removed. 

Also note that this user will remain in database but will be marked as deleted.

This is required to save KuberDock usage information for billing system correct work.

### **Domain Control**

To add base domain click *Add new domain*:

![image alt text](screenshot_part2/image_101.png)

Please note that domain zone existence check performed while adding on this step.

On the opened page fill required field *Domain name* and optional fields: *SSL certificate, SSL key*

![image alt text](screenshot_part2/image_102.png)

In actual wildcard mode base domain has only one A/CNAME DNS record. This will be created when the base domain is being added.

Please note that certificate requires a *.<domain name> domain in common name or in alternative names header. In other words the certificate must be valid for *.<domain name>. The Key has to correspond the certificate. Otherwise domain will not be added.

Also, please note that SSL certificate and SSL key fields are optional. At the same time if you fill SSL field (certificate or key) the other one becomes required.

To delete domain, click on Recycle bin icon and confirm or decline this action in pop-up. 

To avoid conflicts domain name can be used only for one cluster. Additionally, domain name existence check performed 

Settings

	General

In this section you can set:

1. Persistent disk maximum size -  set persistent disk capacity limits in GB, so that a user will not be able to create persistent volume with bigger size than it is specified in this field.

2. Maximum number of Kubes per container - set maximum number of Kubes that user can use per one container.

3. CPU multipliers - allows to set multiplier for CPU cores for nodes. By default, CPU multiplier set to 8.

For example, we have physical 4 cores CPU at node #1 and 6 cores CPU at node #2.  After we set "4" in “CPU multiplier” then node #1 will have 14 cores and node #2 will have 24 cores.

Note that, available range of value is from 1 to 100 and value can be (e.g. 4.55).

![image alt text](screenshot_part2/image_103.png)

4. Memory multiplier - allows to set multiplier for Memory for nodes. By default, Memory multiplier set to 4.

For example, we have physical 4GB Memory at node #1 and 1GB Memory at node #2.  After we set "5" in “Memory multiplier” then node #1 will have 20GB and node #2 will have 5GB Memory.

Note that, available range of value is from 1 to 100 and can be fractional (e.g. 4.55).

5. Email for external services – the email is required to authenticate domains in external services (see the *[DNS provide*r](#bookmark=kix.1t5ujm9ppivz) section). These domains are used to compose service addresses when pods are accessed from outside of KuberDock via service addresses instead of dedicated IP addresses.

6. Kubes limit for Trial user -- this field allows to set number of kuber per Trial user account. Thus Trial user can have total quantity of kubes less or equal to this parameter. ![image alt text](screenshot_part2/image_104.png)

License

You can find all the necessary license information in License section of Settings tab.

License status and validity:

License status:

* Valid - license is valid and installation ID confirmed;

* Invalid - license has expired or invalid installation ID.

Expired Date - the last day of license validity. License becomes invalid after expire date.

License type - type of valid license:

* Standard - standard KuberDock license;

* Trial - license with limited validity period, allows to purchase standard license after trial license expires.

![image alt text](screenshot_part2/image_105.png)

Find the necessary information in two sections below.

KuberDock details:

Installation ID - KuberDock installation identifier;

Platform - cluster type (for example, generic or AWS)

Storage - persistent storage type used in cluster.

![image alt text](screenshot_part2/image_106.png)

To enter or edit Installation ID, click edit icon; enter new ID in input pop-up and click Apply - ID validity will be verified.

.

![image alt text](screenshot_part2/image_107.png)

Software name and current version is displayed on the right:

![image alt text](screenshot_part2/image_108.png)

In the table below you can view resources included in standard license and resources that are currently being used in cluster. If any resource license is approaching to expire, then this resource will be highlighted with red along with the whole cluster resource line.

![image alt text](screenshot_part2/image_109.png)

**DNS provider**

To allow users to use public service addresses for their pods you should provide a list of available valid domains. This section will help you to set up all you need. Thus users will be able to create public service addresses for their pods at one level below added. 

For example:

If you have added domain *example.com*, than service address for users pods will be:

*<username>+<app.name>.example.com*

Note that already specified email for external services (see the *[Genera*l](#bookmark=kix.48k965rzutnq) subsection of the *Settings* section) is one of prerequisites to form the domain list.

You should perform the following steps to configure DNS provider for KuberDock:

1. [Set up DNS zone at one of supported DNS providers](#bookmark=kix.7ycw6jrgd8u8).

2. [Configure DNS provider in KuberDock.](#bookmark=kix.pxmj3qijp5r)

3. [Create list of domain names.](#bookmark=kix.m3e1bk177szn)

At the moment we support cPanel, Route 53 and CloudFlare as DNS providers. Configure your DNS provider according to the instructions below:

* **cPanel**. Follow cPanel documentation [here](https://documentation.cpanel.net/display/56Docs/Add+a+DNS+Zone) to configure DNS zones in cPanel first and documentation [here](https://documentation.cpanel.net/display/ALD/Remote+Access+Key) to configure Remote Access Key. 

* **Route 53**. Refer Amazon [Route 53 setup instructions](http://docs.aws.amazon.com/gettingstarted/latest/swh/getting-started-configure-route53.html) in this regard. Despite being a part of Amazon Web Services, Route 53 can be used in non-AWS-deployed clusters as well.

* **CloudFlare**. Note, CloudFlare available from [KuberDock 1.5.0](#bookmark=id.h1p9rk3zbng1). To use this service it is necessary to[ create a CloudFlare account](https://support.cloudflare.com/hc/en-us/articles/201720164-Step-2-Create-a-CloudFlare-account-and-add-a-website). CloudFlare provides different[ pricing plans](https://www.cloudflare.com/dns/) including free one.

Having DNS zone set up you should configure chosen DNS provider in KuberDock:

**Configuring cPanel as a DNS provider**

1. Log in to KuberDock as an admin, choose Settings and click DNS provider tab.

![image alt text](screenshot_part2/image_110.png)

2. This step depends on DNS provider you use. As an example we show how to use it with cPanel. Set up the following fields:

* In "Select DNS provider" set “cpanel_dnsonly”. Please note that KuberDock doesn`t support cPanel DNSONLY software and this is only item name “cpanel_dnsonly” in dropdown menu and it does not relate to cPanel DNSONLY software. 

![image alt text](screenshot_part2/image_111.png)

* In "Link to cPanel" add link to your cPanel (e.g. [https://example.com](https://example.com))

* In "cPanel admin username" set username of an admin that has rights to change DNS zones.

* In "cPanel access token" add Remote Access Key from cPanel (see instructions above).

![image alt text](screenshot_part2/image_112.png)

**Configuring Route 53 as a DNS provider**

When Amazon Route 53 is selected as a DNS provider, the following options must be configured: AWS Access Key ID and AWS Secret Access Key.

![image alt text](screenshot_part2/image_113.png)

They are required to access Route 53 programmatically and are similar to those used to access any AWS resource (see the *[Amazon AWS installation guid*e](#bookmark=kix.cqhmx1xllsev) section).

You should obtain the necessary values following directions provided in [Amazon access keys management documentation](http://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html) and enter them in the relevant fields.

**Configuring CloudFlare as a DNS provider**

Note, CloudFlare available from [KuberDock 1.5.0](#bookmark=id.h1p9rk3zbng1).

The following fields should be set if CloudFlare is chosen as the DNS provider:

* **_CloudFlare Email_** — which is used as a login to access CloudFlare account

* **_CloudFlare Global API Key_** — it is an all-purpose token allowing to read and edit any data or settings accessible in CloudFlare dashboard

.![image alt text](screenshot_part2/image_114.png)

This  key can be found among the settings of CloudFlare account (see[ Where do I find my CloudFlare API key?](https://support.cloudflare.com/hc/en-us/articles/200167836-Where-do-I-find-my-CloudFlare-API-key-)).

**Creating domains list**

After configuring DNS provider, you may form the domain list.

For this purpose, proceed to the *Administration* page and choose *Domains control*.
Note that already specified email for external services (see the[ General](#bookmark=kix.48k965rzutnq) subsection of the *Settings* section) is prerequisite to form the domain list.

![image alt text](screenshot_part2/image_115.png)

1. Click "Add new domain".

![image alt text](screenshot_part2/image_116.png)

2. Enter domain name (e.g. example.com) and click "Add":

![image alt text](screenshot_part2/image_117.png)

3. After that, new domain name will be added to KuberDock cluster. The list of all domain names is always available in Domains control section of Administration page:

![image alt text](screenshot_part2/image_118.png)

**Billing**

In this section you can set up your billing system to work with KuberDock. First of all select billing system that you plan to use in field *Select your billing system*. It can be one of the supported billing systems, your own billing system or you can leave KuberDock without billing system.

*Note if **"No billing"** is chosen, follow this **[lin*k](#bookmark=kix.4kj5k974x2z8)* to configure Predefined applications.*

In case of WHMCS as a billing system:

* Link to WHMCS - direct link to your WHMCS 

* WHMCS admin username - set username with admin access level to billing system

* WHMCS admin password - set password for this admin username

* Set a Secret key for Single sign-on. This is an AutoAuth key in WHMCS. You will need to add the following line to your WHMCS configuration.php file to define an AutoAuth key. The value just needs to be a random sequence of letters and numbers:

*$autoauthkey = "abcXYZ123";*

Please, read this WHMCS documentation to create key [http://docs.whmcs.com/AutoAuth](http://docs.whmcs.com/AutoAuth) and put in this field.

Field *Secret key for Single sign-on* used for Single sign-on authentication. Must be shared between Kuberdock and billing system or other 3rd party application. Try to use this [section](#bookmark=kix.4kj5k974x2z8) to see how it works in actions.

![image alt text](screenshot_part2/image_119.png)

**Profile**

In this section you can set view and edit user information. Click Edit to change user info:

![image alt text](screenshot_part2/image_120.png)

Specify the necessary information in appropriate fields and click *Save Changes* to save your profile or *Cancel *to return to profile page without saving.

![image alt text](screenshot_part2/image_121.png)

**Backups**

KuberDock version 1.3.0 and higher includes ability to backup master server and ceph storage. Follow the instructions in this section to use backups.

It is possible to backup:

1. [KuberDock master server](#bookmark=kix.h9pdzstegi1m)

2. [Nodes](#bookmark=kix.uv1qvibgyj6h)

3. [CEPH storage](#bookmark=kix.xs4tevj25d68)

Instructions for KuberDock master server backup & restore

**How to do backup**

Our backup tool for KuberDock master server collects several files and dumps to preserve master state. The list of items that script backup is the following:

* Postgresql dump -- main KuberDock database;

* etcd dump and etcd certificates -- highly-available key value store which Kubernetes uses; 

* ssh keys -- ssh key from folder */var/lib/nginx/.ssh/;*

* known hosts list -- list of hosts that have access to KuberDock master;

* License -- cluster license information;

* nginx configs -- configuration of nginx at KuberDock master server.

To create backup of KuberDock master server use command *kd-backup-master* for example:

*kd-backup-master backup /mounted/backup/destination/*

where

*backup *-- option needed to run backup process

*/mounted/backup/destination/ *-- destination where archive file with backup data will be saved.

After script finishes its work there will be files like *2016-07-04T03:46:44.338859.zip *inside destination folder.

Use flag *-h* to see help of this command.

**How to do restore**

Important note: restore script assumes that master stays at same IP and all existing files and data will be overwritten (sic!).

To restore KuberDock master server from backup use command:

*kd-backup-master restore /destination/folder/backup/backup-file.zip*

Use flag *-h* to see help of this command.

**Instructions for Ceph backup & restore**

**How to do backup**

Note that only Format 2 images are supported. If you have images in older format please migrate cluster to image format 2 yourself according to [CEPH official instructions](http://ceph.com/planet/convert-rbd-to-format-v2/). 

Note. Ceph user must have 'class-read object_prefix rbd_children` right.

Note. All images from specified pool will be processed. There is no options to apply any filters for now.

To proceed to backup process *ceph-common* package should be installed on KuberDock master server and rbd kernel module should be available:

1. Run *yum install ceph-common* to install appropriate package;

2. Run *modprobe rbd && echo OK *that should return "OK".

To start backup process run command *kd-backup-ceph* with appropriate options:

* The first and only position argument is destination folder, for example */tmp*. It should be some mounted folder accessible from script.

* *--v (or--verbose) *-- optional, enables debug mode with a lot more output information

* *--skip *-- optional, will skip images if they fail with an error without interupting the script. Otherwise the script will be stopped at the first error. *Skip* flag would pass non-critical errors for volumes with notifying about it with warnings. It is useful when you have a bunch of image in old format.  

Typical usage for backup command:

*kd-backup-ceph  /tmp -v --skip*

For advanced backup settings use additional options:

* *--monitors* -- specify list of IP`s of CEPH's monitors. You can find it inside your ceph.conf (read more at [official ceph documentation](http://docs.ceph.com/docs/hammer/man/8/ceph-mon/));

* *--keyring* -- specify path to authentication key-file for the user which have access to the pool;

* *--pool* -- specify pool name where backup script will collect data;

* *--id * -- specify user name to access to pool;

Example:

*kd-backup-ceph  /tmp --monitors 192.168.101.68,192.168.101.69,192.168.101.70 --keyring /tmp/ceph.keyring --pool my_pool --id my_username -v --skip*

After script finishes its work there will be files like *drive_name_child-2016-07-04T03:46:44.338859.zip* inside destination folder.

**How to do restore**

To restore files unpack them inside any storage you need using command *unzip file_name.zip.*

Instructions for Node backup & pod restore

** **

Our backup tool script scans node local storage location and archives it to destination folder.

## Steps for node backup

1. Login to KD master with root privileges.

2. Mount backup storage to both master and nodes by running command: 

mount -t nfs <mountpoint>

 -t, --types <list> limit the set of filesystem types

Nfs		  filesystem type 

	<mountpoint>	  Specifies the directory where the backup storage should be mounted.

For more details of how to mount storage, please refer to [link](https://www.centos.org/docs/5/html/Global_File_System/s1-manage-mountfs.html).

3. Add job to cron on master by running command:

kdctl pods batch-dump --target-dir /mnt/bak/pods/

Usage: **kdctl pods batch-dump** [OPTIONS]

 

Options:

 --owner TEXT                    	If specified, only pods of this user will be dumped

 --target-dir DIRECTORY   	If specified, pod dumps will be saved there in the following structure:

                    	<target_dir>/<owner_id>/<pod_id>

 -h, --help                 	Show this message and exit.

 

Please refer to [cron documentation](https://www.centos.org/docs/5/html/5.2/Deployment_Guide/s2-autotasks-cron-configuring.html) for more details about configuring automated tasks.

1. Add job to cron on node by running command:

kd-backup-node /mnt/bak/storage/

Usage: **kd-backup-node** [-h] [-v | -q] [-s] [-e CALLBACK] backup_dir

 

Positional arguments:

·         backup_dir  	Destination for all created files

 

Optional arguments:

 -h, --help     	show this help message and exit

 -v, --verbose  verbose (debug) logging

 -q, --quiet    	silent mode, only log warnings

 -s, --skip     	do not stop if one steps is failed

 -e CALLBACK, --callback CALLBACK     	callback for backup file (backup path passed as a 1st arg)

Please note that CEPH cluster admin isn't required to have backups of persistent volumes to make restoration of a pod (because persistent data is stored on the CEPH).

So the command to restore persistent volume on a CEPH cluster looks as follows:

kdctl pods restore --file /mnt/bak/pods/<user_id>/<pod_id> --owner <to_whom_to_restore>
(without parameter backup_dir which locates persistent volume backups).) on backups by CEPH case.

## Steps for pod restore

1. Login to KD node with root privileges."

2. Make sure backup storage is mounted on all nodes and master

3. Merge storage backups from different nodes by running on the node

kd-backup-node-merge /mnt/bak/storage/

Usage: **kd-backup-node-merge** [-h] [-v | -q] [-s] [-d] [-p PRECISION] [-i]

                    	backups

 

Positional arguments:

·         backups      	Target git which contains all backups

 

Optional arguments:

 -h, --help     	How this help message and exit

 -v, --verbose  Verbose (debug) logging

 -q, --quiet    	Silent mode, only log warnings

 -s, --skip     	Do not stop if one steps is failed

 -d, --dry-run	Do not touch any files

 -p PRECISION, --precision PRECISION

                    	Maximum time gap to group in hours. Default: 1hr.

 -i, --include-latest   	Set to also include latest (possible incomplete)

                    	backup folder

1. Login to KD master with root privileges.

2. For the pod restore run the following command on master

kdctl pods restore --file /mnt/bak/pods/<user_id>/<pod_id> --pv-backups-location  file:///mnt/bak/storage/<version_of_storage_backup_to_restore> --owner <to_whom_to_restore>

Note. Please take into account that after restoring pod may have DNS-name differ from previous. This may cause problems with some applications which is use this name for referencing.

YAML specification

The following specification is made using an example of YAML file, through which you can create a Pod with official WordPress and MySQL container images configured for the WordPress web-site comprehensive work. You can find YAML file in our github repository  (https://github.com/cloudlinux/kuberdock_predefined_apps):

Note that if you use YAML files from our github repository in cPanel you need to uncomment section "*proxy*" and set “false” to all parameters “*isPublic*”.

Note that you can use variables to set proper values for YAML file fields, transfer values from one field to another, generate value automatically and show variables values in pre- and postDescription. For example:

to define field values use format:

 $VAR_NAME|default:default_value|some text to show", where:

	$VAR_NAME -- variable name that can be used in other parts of YAML file;

	default --  this variable default value. If enter "autogen", then this value will be autogenerated (8 characters, lower case, letters and numbers). For cPanel use "user_domain_list" to enter the domains and subdomains list for user to choose.

           some text to show -- title for a field specified by a user;

To use variable in other place in YAML use syntax $VAR_NAME$. This will return value of variable $VAR_NAME.

Note that you can use global variables in YAML. Their values can not be set. Use percent symbol (e.g. %PUBLIC_ADDRESS%) to show global variables values. Available global variables:

PUBLIC_ADDRESS - returns Public IP allocated to the pod;

USER_DOMAIN - returns main user domain in cPanel.

YAML File Description:

<table>
  <tr>
    <td>YAML code</td>
    <td>Description</td>
  </tr>
  <tr>
    <td>apiVersion: v1
kind: ReplicationController</td>
    <td></td>
  </tr>
  <tr>
    <td>metadata:
name:$APP_NAME|default:wordpress|app name$</td>
    <td>metadata -  application name in cPanel and Pod name in KuberDock at the same time.
$APP_NAME|default:autogen|app name$ - </td>
  </tr>
  <tr>
    <td>kuberdock:
icon: url_to_icon
packageID: 0
preDescription: |
    You are installing the application [b]WordPress[/b].
    The WordPress rich content management system can utilize plugins, widgets, and themes.
    All the components needed for this application correct work will also be installed: [b]MySQL[/b] server.
    Choose the amount of resources or use recommended parameters.
    When you click "Order now", you will get to order processing page.
  postDescription: |
    You have installed [b]WordPress![/b]
    To access [b]WordPress[/b] use this link: [url]http://%PUBLIC_ADDRESS%[/url]
    name: Wordpress





</td>
    <td>kuberdock section defines pod parameters for KuberDock:
icon -- link to application icon in "png"
packageID - optional, package id in KuberDock database.  If this parameter is not specified in YAML, then package_id value will equal 0 when started from KuberDock, or equal to value from Application defaults when started from cPanel.
preDescription -- text to show user before application start, will be displayed on the page with plans;
postDescription -- text to show user after application start. BBCode can be used to format text. Note that if you use YAML in cPanel then write [url]http://%APP_DOMAIN%[url] instead of [url]http://%PUBLIC_ADDRESS%[/url]. APP_DOMAIN must be equal to domain parameter in proxy section.
name - defines application name for user in cPanel web-interface.</td>
  </tr>
  <tr>
    <td>    appPackages:
    - name: S
      goodFor: up to 100 users
      publicIP: true
      # or “baseDomain: example.com”
      packagePostDescription: |
      Special description in a specific package for the application 
      pods:
        -
          name: $APP_NAME$
          kubeType: 1
          containers:
            - name: mysql
              kubes: 1
            - name: wordpress
              kubes: 1
          persistentDisks:
            - name: mysql-persistent-storage
              pdSize: 1
            - name: wordpress-persistent-storage
              pdSize: 1
   - name: M
      recommended: yes
      goodFor: up to 100K visitors
      publicIP: true
      pods:
        -
          name: $APP_NAME$
          kubeType: 1
          containers:
            - name: mysql
              kubes: 3
            - name: wordpress
              kubes: 2
          persistentDisks:
            - name: mysql-persistent-storage
              pdSize: 2
            - name: wordpress-persistent-storage
              pdSize: 2
</td>
    <td>appPackages - starts describing packages available for user to start predefined application, a bunch of resources allocated to pod and to containers in it. In one YAML can be 4 or less appPackages.
  name -  appPackage name. We recommend to use 3 or less words in the field (e.g. -S, -M, -XL, -XXL) because it is good for existing theme.
  recommended - only one plan can be recommended, it will be highlighted in web-interface.
  goodFor - short text to show to user.
  publicIP - defines if Public IP is available for this appPackage.  If container parameter for isPublic port in specification is "true", then publicIP should be "true" as well, to assign public IP. If publicIP value is "false" then public IP will not be assigned.
  baseDomain - defines if pod will get service address based on domain instead of public IP if any container port has parameter isPublic with value “true”. In case when domain user does not see the price for domain in the application package details. Note, that it is strongly recommended not to use publicIP and baseDomain in one appPackage.
  packagePostDescription. Use this description if you need to explain the difference between application usage in each package. For example, if you have not provide public IP in one of the packages, then postDescription for a whole YAML cannot be used.
  pods - resources allocated to each pod.
   name - name of the pod for which resources are allocated.
   kubeType - Kube Type ID in KuberDock database.
  containers - describes Kubes number to be assigned to each container in YAML.
     name - container name in container specification below
     kubes - number of Kubes for this container.
persistentDisks - persistent discs capacity.
name - persistent disk name.
pdSize - persistent disk size in GB. Note that in case of CEPH as a backend for persistent storage it is impossible to resize storage thus when customer will switch application package than persistent storage size will be the same for all packages which is equal to the current application package. In other case, it is possible to resize persistent storage if application package will have the same Kube Type as current application package.

 </td>
  </tr>
  <tr>
    <td>    proxy: 
     wordpress:
       container: wordpress
       domain: $APP_DOMAIN|default:user_domain_list|Select your domain$
</td>
    <td>proxy - sub-section is required for cPanel to do proxy to user`s domain. Not used in our original YAML for Wordpress application. This is just an example. You can set as many path as you need:
wordpress - path after domain, for example: http://domain.com/wordpress;
container - container image name used in YAML for which path will be used;
domain - show user domain list during predefined application setup to use with that path.
You can set paths for each container image in YAML.

</td>
  </tr>
  <tr>
    <td>spec:
  template:
    metadata:
      labels:
        name: $APP_NAME$</td>
    <td>spec section starts describing each YAML container specification. In template subsection we need to have metadata, where name field must be the same variable as in name field of metadata section above. This is required for KuberDock system pod name.</td>
  </tr>
  <tr>
    <td>    spec:
       volumes:
       - name: mysql-persistent-storage
         persistentDisk:
           pdName: wordpress_mysql_$PD_RAND|default:autogen|PD rand$
       - name: wordpress-persistent-storage
         persistentDisk:
           pdName: wordpress_www_$PD_RAND$</td>
    <td>spec subsection starts describing pod specification. We begin to describe persistent volumes that will be used in the pod:
name - this is a name of volume to be used in container.
persistentDisk - if this volume uses some of persistent storages (ceph for example).
pdName - name of persistent disk within persistent storage. We use $PD_RAND$ variable to autogenerate random part of name. That will give possibility to create different volumes names for each user.
</td>
  </tr>
  <tr>
    <td>      restartPolicy: "Always"</td>
    <td>restartPolicy  field describe which restart policy will be used for this pod.</td>
  </tr>
  <tr>
    <td>       resolve: ["mysql", "wordpress"]</td>
    <td>resolve allows to resolve dns-name within a pod. This part is not used in YAML file for Wordpress application from our github repository. But, for example, Redmine needs to resolve dns-name mysql.
You can add more dns-names, separated by space.</td>
  </tr>
  <tr>
    <td>      containers:
        name: wordpress
        image: wordpress:4.4</td>
    <td>containers field shows containers list within the pod.
name - name of a container within the pod.
image - container image name in DockerHub and a tag of image after “:”. You can find a tag in DockerHub registry in Tag tab on container image page. It is strongly recommended not to use tag “latest”, otherwise proper restore function of the application (pod) is not guaranteed, because latest means latest image at the current time,but latest image days or month ago can be different.

</td>
  </tr>
  <tr>
    <td>      env:
            - name: WORDPRESS_DB_USER
               value: “wordpress”
            - name: WORDPRESS_DB_NAME
               value: “wordpress”
            - name: WORDPRESS_DB_PASSWORD
               value: $MYSQL_USER_PASSWORD$
            - name: WORDPRESS_DB_HOST
               value: “127.0.0.1”</td>
    <td>env - begins a list of environment variables of this container image “mysql:5”
  name - name of an environment variable
  value - value of this environment variable. Note that it is recommended to specify value in quotes. If value consists of digits only, then quotation marks are required (for example, “1234”). If you use variable in value parameter, then quotes are not required.
Note that to connect containers within the same pod you need to use IP 127.0.0.1 instead localhost.</td>
  </tr>
  <tr>
    <td>      ports:
        - containerPort: 80
          protocol: TCP
          podPort: 8080
          isPublic: true</td>
    <td>ports field begins a list of ports to expose for this container image.
containerPort - ports number to be exposed.
protocol - protocol type for this port.
podPort - defines Pod port for this containerPort. Learn more about that here. If podPort value is missing, it equals to containerPort by default.
isPublic - expose port to PublicIP. If you want to make this port available from the web, then this value must be "true".
If at least one PublicIP parameter in the whole YAML is "true", then Public IP will be assigned.
</td>
  </tr>
  <tr>
    <td>      readinessProbe:
        tcpSocket:
            port: 80
        initialDelaySeconds: 5
        timeoutSeconds: 10
        periodSeconds: 15
        successThreshold: 1
        failureThreshold: 2</td>
    <td>readinessProbe or livenessProbe  (read more in official kubernetes documentation) allows to add tests to check if application(pod) successfully launched with all its containers. It is available to add the following tests:
exec: executes a specified command inside the container expecting on success that the command exits with status code 0. Example:
exec:
        command:
        - cat
        - /tmp/health
Where “- cat” is the command and “- /tmp/health” is the parameter.

tcpSocket: performs a TCP check against the container’s IP address on a specified port expecting on success that the port is open.
tcpSocket:
                  port: 80
Where “port” is a number of port to be tested.

httpGet: performs an HTTP Get against the container’s IP address on a specified port and path expecting on success that the response has a status code greater than or equal to 200 and less than 400.
httpGet
        path: /health
        port: 8080
        httpHeaders:
          - name: X-Custom-Header
            value: Awesome
Where “path” is the path for http request, “port” is the number of the port to be used, “httpHeader” name and value for request header.

Each probe will have one of three results:
Success: indicates that the container passed the diagnostic and status of pod become Running.

Failure: indicates that the container failed the diagnostic and status of the pod become Pending.

It is also possible to add conditions to the test:
initialDelaySeconds - number of seconds after the container has started before liveness probes are initiated.
timeoutSeconds - number of seconds after which the probe times out.Defaults to 1 second. Minimum value is 1.
periodSeconds - how often (in seconds) to perform the probe. Default to 10 seconds. Minimum value is 1.
successThreshold - minimum consecutive successes for the probe to be considered successful after having failed. Defaults to 1. Minimum value is 1.
failureThreshold - minimum consecutive failures for the probe to be considered failed after having succeeded. Defaults to 3. Minimum value is 1.
</td>
  </tr>
  <tr>
    <td>      volumeMounts:
        - mountPath: /var/lib/mysql
          name: wordpress-persistent
      </td>
    <td>volumeMounts begins a list of container directories which will be mounted to persistent storage or persistent local storage. It depends on type of volumes above.
mountPath - mount path within the container.
name - name of persistent storage to be used (name parameter from volumes section).
</td>
  </tr>
  <tr>
    <td>   name: mysql
     image: mysql:5
     env:
      - name: MYSQL_DATABASE
        value: “wordpress”
      - name: MYSQL_USER
        value: “wordpress”
      - name: MYSQL_PASSWORD
        value: $MYSQL_USER_PASSWORD|default:autogen|mysql password$
      - name: MYSQL_ROOT_PASSWORD
        value: $MYSQL_ROOT_PASSWORD|default:autogen|mysql password$
     ports:
       - containerPort: 3306
     volumeMounts:
       - mountPath: /var/lib/mysql
         name: mysql-persistent-storage</td>
    <td>Here we describe the next MySQL container image in the pod.</td>
  </tr>
</table>


Modifying predefined application template

KuberDock template

Edit styles settings and upload proper images when a user runs predefined application, to change packages design:

1. Change background of a recommended package:

		![image alt text](screenshot_part2/image_122.png)

*.plan.recommended{*

*        background: white;*

*        border: 1px solid #e0e0e0;*

* }*

2. Changing "Сhoсolate bar" background:

		![image alt text](screenshot_part2/image_123.png)

Upload 119x205 px image to var/opt/kuberdock/kubedock/frontend/static/img/.

Edit plans.html (var/opt/kuberdock/kubedock/frontend/templates/apps/plans.html), specify new image name (in bold):

*.plan .plan-img-wrapper{*

*        width: 119px;*

*        padding-top: 15px;*

*        position: relative;*

*        margin: 0 auto 18px;*

*        background: url('..***_/static/img/chocolate.png_***') 0 0 no-repeat;*

*}*

3. Changing overlay image. 

![image alt text](screenshot_part2/image_124.png)

Upload 119x133 px image to var/opt/kuberdock/kubedock/frontend/static/img/.

Edit plans.html (var/opt/kuberdock/kubedock/frontend/templates/apps/plans.html), specify new image file name (in bold):

*.plan .plan-img-wrapper .price-wrapper {*

*        height: 133px;*

*        margin: 0 auto;*

*        position: relative;*

*        background: url('..***_/static/img/price-area.png_***') 0 0 no-repeat;*

*    }*

4. Package name spot. Edit plans.html (var/opt/kuberdock/kubedock/frontend/templates/apps/plans.html) to change view:

![image alt text](screenshot_part2/image_125.png)

* Recommended package

*.plan.recommended .plan-img-wrapper .plan-name{*

*        background-color:** ***_#e65583_***;*

*    }*

* Other packages:

*.plan .plan-img-wrapper .plan-name {*

*        top: -10px;*

*        z-index: 1;*

*        right: -15px;*

*        height: 47px;*

*        color: ***_#fffefe_***;*

*        min-width: 47px;*

*        padding: 0 10px;*

*        font-size: 17px;*

*        line-height: 47px;*

*        position: absolute;*

*        text-align: center;*

*        background-color: #3d8acd;*

*        display: inline-block;*

*        -webkit-border-radius: 50px;*

*        -moz-border-radius: 50px;*

*        border-radius: 50px;*

*    }*

5. Changing fonts. Edit plans.html (var/opt/kuberdock/kubedock/frontend/templates/apps/plans.html):

* Price:

![image alt text](screenshot_part2/image_126.png)

*.plan .plan-img-wrapper .price-wrapper .plan-price{*

*        color: #fff;*

*        font-size: 19px;*

*        padding-top: 50%;*

*        line-height: 26px;*

*        word-spacing: -4px;*

*        text-align: right;*

*        padding-right: 10%;*

*        margin-bottom: 5px;*

*    }*

* Currency and period:

![image alt text](screenshot_part2/image_127.png)

*.plan .plan-img-wrapper .price-wrapper .plan-period,*

*.plan .plan-img-wrapper .price-wrapper .plan-price-suffix{*

*        color: #fff;*

*        font-size: 14px;*

*    }*

* Most popular title view:

![image alt text](screenshot_part2/image_128.png)

*.plan.recommended .title{*

*        top: -12px;*

*        left: 0;*

*        padding: 3px 0;*

*        right: 0;*

*        color: #fff;*

*        margin: auto;*

*        width: 119px;*

*        font-size: 12px;*

*        font-weight: 800;*

*        position: absolute;*

*        text-align: center;*

*        text-transform: uppercase;*

*        background-color: #e65583;*

*    }*

* Choose package button:

![image alt text](screenshot_part2/image_129.png)

.plan.recommended .buttons .submit-button -- for Choose package button in Recommended package

*.plan.recommended .buttons .submit-button{*

*        background-color:** ***_#e65583_***;*

*    }*

.submit-button -- for other buttons Choose package

*.submit-button{*

*        -webkit-border-radius: 2px;*

*        -moz-border-radius: 2px;*

*        border-radius: 2px;*

*        -moz-background-clip: padding;*

*        -webkit-background-clip: padding-box;*

*        background-clip: padding-box;*

*        -webkit-transition: all 300ms;*

*        -moz-transition: all 300ms;*

*        -ms-transition: all 300ms;*

*        -o-transition: all 300ms;*

*        -webkit-box-shadow: 0px 2px 4px 0px rgba(0, 0, 0, 0.35);*

*        -moz-box-shadow: 0px 2px 4px 0px rgba(0, 0, 0, 0.35);*

*        box-shadow: 0px 2px 4px 0px rgba(0, 0, 0, 0.35);*

*        border: none;*

*        color: #fff;*

*        height: 37px;*

*        padding: 0 31px;*

*        font-size: 12px;*

*        min-width: 105px;*

*        line-height: 37px;*

*        text-align: center;*

*        text-transform: uppercase;*

*        background-color: #2490EA;*

*        font-family: "open_sansregular";*

*    }*

* *Good for* section:

![image alt text](screenshot_part2/image_130.png)

"Good for" line:

*.plans .plan .plan-goodfor{*

*        color: ***_#e65583_***;*

*        font-size: 13px;*

*        text-align: left;*

*        font-weight: 600;*

*        padding: 0 0 0 10px;*

*        margin-bottom: 15px;*

*}*

Additionally you can change the line "regular use":

*.plans .plan .plan-goodfor span{*

*        font-size: 17px;*

*}*

* Show details button:

![image alt text](screenshot_part2/image_131.png)

*Show/hide details button*

*.plans .plan .show-more{*

*        margin: 0 10px;*

*        font-size: 14px;*

*        cursor: pointer;*

*        font-weight: 400;*

*        text-align: left;*

*        position: relative;*

*        padding-left: 27px;*

*}*

*Show/hide button icon*

*.plans .plan .show-more:before{*

*        top: 0;*

*        left: 0;*

*        bottom: 0;*

*        content: '';*

*        width: 18px;*

*        margin: auto;*

*        height: 18px;*

*        position: absolute;*

*        background: url('../static/img/item-arrow.png') 0 0 no-repeat;*

*}*

*Show details section text:*

*.plans .plan .plan-details p{*

*        color: #000;*

*        font-size: 13px;*

*        word-spacing: -1px;*

*        margin-bottom: 5px;*

*        letter-spacing: 0px;*

*   }*

Note that you can set icon rotation by clicking Show details in .plans .plan .show-more.rotate:before

cPanel template

	Edit styles settings and upload proper images when a user runs predefined application to change packages design. To change styles edit *Styles *file in cPanel which is located here /usr/local/cpanel/base/frontend/paper_lantern/KuberDock/assets/css/styles.css (for peper_lantern theme):

1. Change background of a recommended package:

		![image alt text](screenshot_part2/image_132.png)

*.preapp-plan-page form.palans .item.recommended{*

*    background: white;*

*    border: 1px solid #e0e0e0;*

*}*

2. Changing "Сhoсolate bar" background:

		![image alt text](screenshot_part2/image_133.png)

Upload 119x205 px image to /usr/local/cpanel/base/frontend/paper_lantern/KuberDock/assets/images/ on cPanel server.

Change styles, specify new image file name (in bold):

*.preapp-plan-page form.palans .item .img-wrapper{*

*    width: 119px;*

*    padding-top: 30px;*

*    position: relative;*

*    margin: 0 auto 18px;*

*    background: url(../images/***_chocolate.png_***) 0 0 no-repeat;*

*}*

3. Changing overlay image: 

![image alt text](screenshot_part2/image_134.png)

Upload 119x133 px image to /usr/local/cpanel/base/frontend/paper_lantern/KuberDock/assets/images/ on cPanel server.

Change styles, specify new image file name (in bold):

*.preapp-plan-page form.palans .item .img-wrapper .price-wrapper{*

*    height: 133px;*

*    margin: 0 auto;*

*    position: relative;*

*    background: url('../images/***_price-area.png_***') 0 0 no-repeat;*

*}*

4. Package name spot. To change, edit the following classes:

![image alt text](screenshot_part2/image_135.png)

* Recommended package

*.preapp-plan-page form.palans .item.recommended .img-wrapper .plan-name{*

*    background-color: ***_#e65583_***;*

*}*

* Other packages:

*.preapp-plan-page form.palans .item .img-wrapper .plan-name{*

*    position: absolute;*

*    top: -10px;*

*    z-index: 1;*

*    min-width: 47px;*

*    padding: 0 10px;*

*    right: -15px;*

*    height: 47px;*

*    color: ***_#fffefe_***;*

*    font-size: 17px;*

*    line-height: 47px;*

*    text-align: center;*

*    background-color: ***_#3d8acd_***;*

*    display: inline-block;*

*    -webkit-border-radius: 50px;*

*    -moz-border-radius: 50px;*

*    border-radius: 50px;*

*}*

5. Changing fonts. Edit the following classes:

* Price:

![image alt text](screenshot_part2/image_136.png)

* Currency and period:

![image alt text](screenshot_part2/image_137.png)

* Most popular title view:

![image alt text](screenshot_part2/image_138.png)

*.preapp-plan-page form.palans .item.recommended .title{*

*    top: -12px;*

*    left: 0;*

*    padding: 3px 0;*

*    right: 0;*

*    color: #fff;*

*    margin: auto;*

*    width: 119px;*

*    font-size: 12px;*

*    font-weight: 800;*

*    position: absolute;*

*    text-align: center;*

*    text-transform: uppercase;*

*    background-color: #e65583;*

*}*

* Choose package button:

![image alt text](screenshot_part2/image_139.png)

.preapp-plan-page form.palans .item.recommended .margin-top a.btn.btn-primary -- for Choose package button in Recommended package

*.preapp-plan-page form.palans .item.recommended .margin-top a.btn.btn-primary{*

*    background-color: #e65583;*

*}*

*.preapp-plan-page form.palans .item.recommended .margin-top a.btn.btn-primary:hover{*

*    background-color: #CD3C6A;*

*}*

.preapp-install-page button.btn.btn-primary .preapp-install-page a.btn.btn-default .preapp-plan-page a.btn.btn-primary -- for other buttons Choose package

*.preapp-install-page button.btn.btn-primary,*

*.preapp-install-page a.btn.btn-default,*

*.preapp-plan-page a.btn.btn-primary{*

*    border-color: transparent;*

*    -webkit-transition: all 300ms;*

*    -moz-transition: all 300ms;*

*    -ms-transition: all 300ms;*

*    -o-transition: all 300ms;*

*    -webkit-box-shadow: 0px 2px 4px 0px rgba(0, 0, 0, 0.35);*

*    -moz-box-shadow: 0px 2px 4px 0px rgba(0, 0, 0, 0.35);*

*    box-shadow: 0px 2px 4px 0px rgba(0, 0, 0, 0.35);*

*    -webkit-border-radius: 0;*

*    -moz-border-radius: 0;*

*    border-radius: 0;*

*}*

*.preapp-install-page button.btn.btn-primary:hover,*

*.preapp-install-page a.btn.btn-default:hover,*

*.preapp-plan-page a.btn.btn-primary:hover{*

*    cursor: pointer;*

*    -webkit-box-shadow: 0 5px 11px 0 rgba(0, 0, 0, 0.18);*

*    -moz-box-shadow: 0 5px 11px 0 rgba(0, 0, 0, 0.18);*

*    box-shadow: 0 5px 11px 0 rgba(0, 0, 0, 0.18);*

*}*

* *Good for* section:

![image alt text](screenshot_part2/image_140.png)

"Good for" line:

*.preapp-plan-page form.palans .item .description{*

*    color: ***_#e65583_***;*

*    font-size: 14px;*

*    font-weight: 800;*

*    line-height: 14px;*

*    padding-bottom: 0;*

*    margin-bottom: 15px;*

*}*

Additionally you can change the line "regular use":

*.preapp-plan-page form.palans .item .description span{*

*    font-size: 19px;*

*    line-height: 19px;*

*}*

* Show details button:

![image alt text](screenshot_part2/image_141.png)

Show/hide details button

*.preapp-plan-page form.palans .item .show-details,*

*.preapp-plan-page form.palans .item .hide-details{*

*    color: #000000;*

*    font-size: 14px;*

*    cursor: pointer;*

*    padding-left: 27px;*

*    position: relative;*

*    margin-bottom: 15px;*

*    display: inline-block;*

*}*

Show/hide button icon

*.preapp-plan-page form.palans .item .show-details:before,*

*.preapp-plan-page form.palans .item .hide-details:before{*

*    top: 0;*

*    left: 0;*

*    bottom: 0;*

*    width: 18px;*

*    content: '';*

*    height: 18px;*

*    margin: auto;*

*    position: absolute;*

*    background: url('../images/item-arrow.png') 0 0 no-repeat;*

*}*

Show details section text:

*.preapp-plan-page form.palans .item .product-description{*

*    padding: 10px;*

*    font-size: 12px;*

*    text-align: left;*

*    margin-bottom: 20px;*

*    background-color: #f5f5f5;*

*    border: 1px solid #e0e0e0;*

*}*

Note that you can set icon rotation by clicking Show details in .plans .plan .show-more.rotate:before

Troubleshooting

	Known issues

* In some cases KuberDock doesn`t work properly on Amazon Web Services.

* Web-interface in KuberDock version 1.0 doesn`t work in Internet Explorer.

* If during KuberDock updating, upgrade log is frozen for more than 30 minutes on running docker pull action, for example: 

**[node_hostname] run: docker pull fluentd. **

Then go to this node console and run the command: 

systemctl restart docker.service.

Upgrade process should continue after these actions. If not, then stop upgrade process and run command to resume upgrade process:

kuberdock-upgrade resume-upgrade 

* If WHMCS does not send invoices to the customers then check prices in KuberDock package configuration. At least one value must equal more than zero.

* In some cases users' pods can be frozen in Pending status during container update or upgrade process, starting pod or other actions with pod and container. In this case you should restart docker on the node where this pod is allocated, performing the following steps:

* Copy pending pod UUID. (You can find UUID in browser address bar on pod page. For example: [https://masterip/#pods/bd1218c0-0321-4821-873f-8fc48638dfdc](https://masterip/#pods/bd1218c0-0321-4821-873f-8fc48638dfdc), where UUID is bd1218c0-0321-4821-873f-8fc48638dfdc).

* Run the command on master server to find a node with this pod: 

*kubectl get pods --namespace=UUID_HERE -o yaml*

You will get a YAML specification of this pod.

* Find "hostIP" parameter - which is node IP.

* Go to console of this node and run command systemctl restart docker.service

* In some cases container logs doesn`t appear for a long time.

* After adding memory to a node KuberDock web-interface does not show new value, but KuberDock core use it.

* In case when KuberDock server and WHMCS server have unsynchronized time and date then user will get an error "Link expired" after click on Pay & Start button. You need to follow [WHMCS installation guide](#bookmark=id.eqgtkcf797c)  step 3 and do synchronization between KuberDock master server and WHMCS server.

* After executing upgrade script the pods that were pending at the moment of upgrade may have no SSH access. Such pods should be restarted manually if SSH access is needed.

* If WHMCS doesn`t send invoices to your customers please follow [this instruction](#bookmark=id.3bkej1fa0b60) (step 3) to solve the problem .

* If you get the following error in WHMCS

*Exception with message 'DateTime::__construct(): Is not safe to rely on the system's time zone settings'*

Do the following:

1. Open your php.ini file on WHMCS server.

2. Find there a string which says:

*;date.timezone =*

3. Remove semicolon ";" in the beginning to uncomment it and add the appropriate timezone for you which can be selected from here: [http://php.net/manual/en/timezones.php](http://php.net/manual/en/timezones.php). For example: *date.timezone = America/New_York*

* If in WHMCS during KuberDock package edit or create process of Trial package input fields with prices are not hidden, then go to Standard package settings and click "Save changes". It must reactivate all the needed hooks in KuberDock plugin.

* If a user terminates pod in KuberDock, then this item will be deleted from user profile in billing system only the next day. Until the next day WHMCS admin will see this billable item in user profile. (AC-5029)

* For WHMCS plugin version 1.0.8.1 and lower where product setting in Module settings section is set to Automatically setup the product as soon as the first payment is received will cause a problem with manual mark of invoice as Mark Paid. The problem is that users` application will not be created. This will be solved with the upcoming version of WHMCS plugin. Note that there is no behavior to solve that problem at the moment.

* After establishing SFTP connection using our SFTP direct access feature, you may experience troubles copying local directories into container's file system.

*sftp> put -r localDirectory
Uploading localDirectory/ to /root/localDirectory
Couldn't canonicalize: No such file or directory
Unable to canonicalize path "/root/localDirectory"
*

This is a known issue of OpenSSH [https://bugzilla.mindrot.org/show_bug.cgi?id=2150](https://bugzilla.mindrot.org/show_bug.cgi?id=2150), which is not related to KuberDock itself.

One of the suggested workarounds is to create the target directory manually.

*sftp> mkdir localDirectory
sftp> put -r localDirectory
Uploading localDirectory/ to /root/localDirectory
Entering localDirectory/*

However in case of any subdirectories present, the command will fail again.

Other suggested workarounds are to use SCP instead.

* In WHMCS If user does not pay the invoice then this invoice will be canceled after suspended days configured in Automation settings. To generate new invoice a user should start unpaid pod in KuberDock.

* When Plesk is integrated with KuberDock plugin then there is a problem with pod accessibility via Service IP

This problem can be fixed by adding this line to /etc/sysconfig/flanneld config on remote *host FLANNEL_OPTIONS="--iface=eno16777728"*
Then restart Flanneld restart is required.

	This problem affects KuberDock versions below 1.5.0. You can just update KuberDock to 1.5.0 or higher to solve the problem

* If deploy KuberDock plugin on cPanel with kcli-deploy.sh from 1.5.0 , at the end of the deploy we take error "/opt/bin/calicoctl: error while loading shared libraries: libz.so.1: failed to map segment from shared object: Operation not permitted" error massage. Solution is:

before deploy, need to run "mount /tmp -o remount,exec"

* A node having unmounted Ceph Persistent Volume may hang up while rebooting. This situation is especially frequent during KuberDock upgrades and takes place due to Ceph known issue ([http://tracker.ceph.com/issues/15887](http://tracker.ceph.com/issues/15887)).

At the Ceph site, a forced unmount of the volume is recommended as a possible workaround. However, this issue usually results in the node unavailability which requires its forced reboot.

* Amazon Elastic Load Balancer doesn’t allow the UDP protocol traffic. This disables running those application which require the UDP protocol support (e.g. a pod containing the popular game *Counter Strike* cannot be run in KuberDock cluster deployed in Amazon Web Services).