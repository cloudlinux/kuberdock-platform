import os
import ConfigParser

from fabric.api import run, put, get
from copy import deepcopy

from kubedock.pods.models import PersistentDisk, Pod, db
from kubedock.kapi.podcollection import PodCollection
from kubedock.kapi import pstorage
from kubedock.billing.models import Kube
from kubedock.utils import POD_STATUSES
from kubedock.updates import helpers
from kubedock.settings import (
    MASTER_IP, KUBERDOCK_SETTINGS_FILE, CEPH, PD_NS_SEPARATOR)

#00084_update.py
old_version = "3.10.0-229.11.1.el7.centos"


#00085_update.py
def with_size(volumes, owner_id):
    volumes = deepcopy(volumes)
    for volume in volumes:
        pd = volume.get('persistentDisk')
        if pd and not pd.get('pdSize'):
            pd_in_db = PersistentDisk.query.filter_by(name=pd.get('pdName'),
                                                      owner_id=owner_id).first()
            pd['pdSize'] = pd_in_db.size if pd_in_db is not None else 1
    return volumes


#00086_update.py
SERVICE_FILE = \
"""
[Unit]
Description=KuberDock kubernetes to etcd events middleware
Before=kube-apiserver.service

[Service]
ExecStart=/usr/bin/env python2 /var/opt/kuberdock/k8s2etcd.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
"""

K8S_API_SERVICE_FILE = \
"""
[Unit]
Description=Kubernetes API Server
Documentation=https://github.com/GoogleCloudPlatform/kubernetes
After=etcd.service

[Service]
EnvironmentFile=-/etc/kubernetes/config
EnvironmentFile=-/etc/kubernetes/apiserver
User=kube
ExecStart=/usr/bin/kube-apiserver \
            $KUBE_LOGTOSTDERR \
            $KUBE_LOG_LEVEL \
            $KUBE_ETCD_SERVERS \
            $KUBE_API_ADDRESS \
            $KUBE_API_PORT \
            $KUBELET_PORT \
            $KUBE_ALLOW_PRIV \
            $KUBE_SERVICE_ADDRESSES \
            $KUBE_ADMISSION_CONTROL \
            $KUBE_API_ARGS
Restart=on-failure
Type=notify
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
"""

KUBE_API_SERVER_PATH = '/etc/kubernetes/apiserver'
KUBE_API_SERVER_ARG = 'KUBE_API_ARGS'
KUBE_API_WATCHCACHE_DISABLE = ' --watch-cache=false'

KUBELET_PATH = '/etc/kubernetes/kubelet'
KUBELET_ARG = 'KUBELET_ARGS'
KUBELET_CPUCFS_ENABLE = ' --cpu-cfs-quota=true'
KUBELET_TEMP_PATH = '/tmp/kubelet'

ETCD_SERVICE = 'etcd.service'

#00087_update.py
OLD_DEFAULT_CEPH_POOL = 'rbd'

#00088_update.py
PLUGIN_DIR = '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/'


def upgrade(upd, with_testing, *args, **kwargs):
    # 00085_update.py
    upd.print_log('Add default Persistent Disks size in pods config...')
    pods = Pod.query.all()
    for pod in pods:
        upd.print_log('Processing pod {0}'.format(pod.name))
        config = pod.get_dbconfig()
        config['volumes_public'] = with_size(config.get('volumes_original', []), pod.owner_id)
        pod.set_dbconfig(config, save=False)
    for pod in pods:
        config = pod.get_dbconfig()
        config.pop('volumes_original', None)
        pod.set_dbconfig(config, save=False)
    db.session.commit()

    # 00086_update.py
    upd.print_log('Update kubes to hard limits')
    internal = Kube.get_by_name('Internal service')
    if internal:
        internal.cpu = 0.05
        internal.save()
    small = Kube.get_by_name('Small')
    if small:
        small.cpu = 0.05
        small.save()
    standard = Kube.get_by_name('Standard')
    if standard:
        standard.cpu = 0.25
        standard.save()
    high = Kube.get_by_name('High memory')
    if high:
        high.cpu = 0.5
        high.save()
    upd.print_log('Setup k8s2etcd middleware service')
    upd.print_log(
        helpers.local(
            "cat > /etc/systemd/system/kuberdock-k8s2etcd.service << 'EOF' {0}"
            .format(SERVICE_FILE))
    )

    helpers.local('systemctl daemon-reload')
    upd.print_log(helpers.local('systemctl reenable kuberdock-k8s2etcd'))
    upd.print_log(helpers.local('systemctl restart kuberdock-k8s2etcd'))

    helpers.install_package('kubernetes-master-1.1.3', with_testing)
    upd.print_log('Add after etcd.service to kube-apiserver service file')
    upd.print_log(
        helpers.local(
            "cat > /etc/systemd/system/kube-apiserver.service << 'EOF' {0}"
            .format(K8S_API_SERVICE_FILE))
    )
    upd.print_log('Turn off watch-cache in kube_apiserver')
    lines = []
    with open(KUBE_API_SERVER_PATH) as f:
        lines = f.readlines()
    with open(KUBE_API_SERVER_PATH, 'w+') as f:
        for line in lines:
            if (KUBE_API_SERVER_ARG in line and
                not KUBE_API_WATCHCACHE_DISABLE in line):
                s = line.split('"')
                s[1] += KUBE_API_WATCHCACHE_DISABLE
                line = '"'.join(s)
            f.write(line)
    helpers.restart_master_kubernetes(with_enable=True)

    # 00087_update.py
    upd.print_log('Upgrade namespaces for PD...')
    config = ConfigParser.RawConfigParser()
    config.read(KUBERDOCK_SETTINGS_FILE)
    ns = MASTER_IP
    if not config.has_option('main', 'PD_NAMESPACE'):
        if CEPH:
            # Store default CEPH pool as namespace. It already was used
            # by KD cluster, so we will not change it.
            ns = OLD_DEFAULT_CEPH_POOL
        config.set('main', 'PD_NAMESPACE', ns)
        with open(KUBERDOCK_SETTINGS_FILE, 'wb') as fout:
            config.write(fout)

    if CEPH:
        # Set 'rbd' for all existing ceph drives, because it was a default pool
        PersistentDisk.query.filter(
            ~PersistentDisk.drive_name.contains(PD_NS_SEPARATOR)
        ).update(
            {PersistentDisk.drive_name: \
                OLD_DEFAULT_CEPH_POOL + PD_NS_SEPARATOR + \
                PersistentDisk.drive_name
            },
            synchronize_session=False
        )
        db.session.commit()
        try:
            pstorage.check_namespace_exists(namespace=ns)
        except pstorage.NoNodesError:
            # skip CEPH pool checking if there are no nodes with CEPH
            pass

    # Restart kuberdock to prevent loss of PD bind state, becuase fix for this
    # is in the new version.
    helpers.restart_service('emperor.uwsgi')


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    #00085_update.py
    upd.print_log('Set volumes_original back...')
    for pod in Pod.query.all():
        upd.print_log('Processing pod {0}'.format(pod.name))
        config = pod.get_dbconfig()
        if 'volumes_original' not in config:
            config['volumes_original'] = config.get('volumes_public', [])
        pod.set_dbconfig(config, save=False)
    db.session.commit()

    #00087_update.py
    if CEPH:
        for pd in PersistentDisk.query:
            parts = PersistentDisk.drive_name.split(PD_NS_SEPARATOR, 1)
            if len(parts) > 1:
                PersistentDisk.drive_name = parts[-1]
        db.session.commit()


def upgrade_node(upd, with_testing, *args, **kwargs):
    # 00084_update.py
    yum_base_no_kube = 'yum install --disablerepo=kube -y '

    run(yum_base_no_kube + 'kernel')
    run(yum_base_no_kube + 'kernel-tools')
    run(yum_base_no_kube + 'kernel-tools-libs')
    run(yum_base_no_kube + 'kernel-headers')
    run(yum_base_no_kube + 'kernel-devel')

    run('rpm -e -v --nodeps kernel-' + old_version)
    run('yum remove -y kernel-tools-' + old_version)
    run('yum remove -y kernel-tools-libs-' + old_version)
    run('yum remove -y kernel-headers-' + old_version)
    run('yum remove -y kernel-devel-' + old_version)

    # 00086_update.py
    helpers.remote_install('kubernetes-node-1.1.3', with_testing)
    upd.print_log("Turn on cpu-cfs-quota in kubelet")

    get(KUBELET_PATH, KUBELET_TEMP_PATH)
    lines = []
    with open(KUBELET_TEMP_PATH) as f:
        lines = f.readlines()
    with open(KUBELET_TEMP_PATH, 'w+') as f:
        for line in lines:
            if KUBELET_ARG in line and not KUBELET_CPUCFS_ENABLE in KUBELET_ARG:
                s = line.split('"')
                s[1] += KUBELET_CPUCFS_ENABLE
                line = '"'.join(s)
            f.write(line)
    put(KUBELET_TEMP_PATH, KUBELET_PATH)
    os.remove(KUBELET_TEMP_PATH)
    helpers.restart_node_kubernetes(with_enable=True)
    upd.print_log("Restart pods to apply new limits")
    pc = PodCollection()
    pods = pc.get(as_json=False)
    for pod in pods:
        if pod['status'] == POD_STATUSES.running:
            pc.update_container(pod['id'], None)

    # 00088_update.py
    put('/var/opt/kuberdock/node_network_plugin.sh', PLUGIN_DIR + 'kuberdock')
    put('/var/opt/kuberdock/node_network_plugin.py', PLUGIN_DIR + 'kuberdock.py')
    run('systemctl restart kuberdock-watcher')

    helpers.reboot_node(upd)


def downgrade_node(upd, with_testing,  exception, *args, **kwargs):
    # 00084_update.py
    helpers.install_package('kernel-'+old_version, action='upgrade')
    helpers.install_package('kernel-tools-'+old_version, action='upgrade')
    helpers.install_package('kernel-tools-libs-'+old_version, action='upgrade')
    helpers.install_package('kernel-headers-'+old_version, action='upgrade')
    helpers.install_package('kernel-devel-'+old_version, action='upgrade')
    helpers.reboot_node(upd)
